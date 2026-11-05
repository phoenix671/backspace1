import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import ai_client
from app.ai_client import call_ai
from app.database import SessionLocal, get_db
from app.errors import ApiError
from app.models import (
    Attempt,
    Book,
    ClassStudent,
    Homework,
    MistakeHistory,
    Question,
    SolveSession,
    User,
    VideoCache,
)
from app.schemas import (
    AttemptInfo,
    AttemptResponse,
    DiagnosisItem,
    EfficientMethod,
    FollowupsResponse,
    FullSolution,
    GifInfo,
    GifResponse,
    MistakeTypeStat,
    SessionDetailOut,
    SessionOut,
    SimplifiedQuestion,
    StartHomeworkSessionRequest,
    StartPyqSessionRequest,
    StudentHomeworkItem,
    StudentHomeworkListResponse,
    StudentStatsResponse,
    StudentTotals,
    TopicMistakeCounts,
    TopicStatInfo,
    TopicsAndFormulae,
    VideoItem,
    VideosResponse,
)
from app.security import require_role
from app.session_helpers import get_mistake_history, is_valid_analysis
from app.session_utils import build_attempt_out, build_session_out
from app.storage import absolute_path, delete_file, save_image

router = APIRouter(prefix="/student", tags=["student"])


def _bg_generate_gif(session_id: int, question_text: str, simplified_text: str, out_rel: str):
    abs_out = absolute_path(out_rel)
    abs_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        res = ai_client.call_ai(
            ai_client.generate_gif,
            question_text,
            simplified_text,
            str(abs_out),
            timeout=60,
        )
        with SessionLocal() as db:
            s = db.get(SolveSession, session_id)
            if s:
                if res and res.get("status") == "ready" and abs_out.exists():
                    s.gif_status = "ready"
                    s.gif_path = out_rel
                else:
                    s.gif_status = "failed"
                db.commit()
    except Exception:
        with SessionLocal() as db:
            s = db.get(SolveSession, session_id)
            if s:
                s.gif_status = "failed"
                db.commit()


# ─── E3: POST /student/sessions/upload ───────────────────────────────────────

@router.post("/sessions/upload", response_model=SessionOut, status_code=201)
def upload_session(
    image: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    # 1. Image and text presence check
    has_image = image is not None and bool(image.filename)
    has_text = text is not None and bool(text.strip())

    if not has_image and not has_text:
        raise ApiError(422, "validation_error", "Send an image or a text question")

    # 2. Image path
    if has_image:
        data = image.file.read()
        rel = save_image(data, image.filename, "uploads", "q")
        try:
            result = call_ai(
                ai_client.extract_question_from_image,
                str(absolute_path(rel)),
                timeout=60,
            )
        except Exception:
            delete_file(rel)
            raise

        q_text = result.get("question_text") if result else None
        if not result or result.get("readable") is not True or not q_text:
            delete_file(rel)
            raise ApiError(422, "image_unreadable", "The question image could not be read")

        question_text = q_text
        topic = result.get("topic") or "General"
        subject = result.get("subject") or "Physics"
    else:
        # 3. Text path
        question_text = text.strip()
        rel = None
        # TODO temporary: the contract has no AI function to classify typed text
        topic = "General"
        subject = "Physics"
        q_lower = question_text.lower()
        for t in ai_client.TOPICS:
            if t.lower() in q_lower:
                topic = t
                break

    # 4. Insert question and session rows
    try:
        question = Question(
            text=question_text,
            topic=topic,
            subject=subject,
            image_path=rel,
            source_book_id=None,
            reference=None,
        )
        db.add(question)
        db.flush()

        session = SolveSession(
            student_id=user.id,
            question_id=question.id,
            source="upload",
            status="awaiting_attempt",
            attempts_used=0,
            homework_id=None,
            followup_of=None,
            followup_index=None,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        delete_file(rel)
        raise

    # 5. Return serialized session
    return build_session_out(session, question)


# ─── E4: GET /student/sessions/{session_id} ─────────────────────────────────

@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session(
    session_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")

    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    question = db.get(Question, session.question_id)
    attempts = (
        db.query(Attempt)
        .filter(Attempt.session_id == session.id)
        .order_by(Attempt.trial_number.asc(), Attempt.id.asc())
        .all()
    )

    return {
        "session": build_session_out(session, question),
        "attempts": [build_attempt_out(a) for a in attempts],
    }


# ─── E5: POST /student/sessions/{session_id}/attempts ───────────────────────

@router.post("/sessions/{session_id}/attempts", response_model=AttemptResponse)
def submit_attempt(
    session_id: int,
    background_tasks: BackgroundTasks,
    image: Optional[UploadFile] = File(None),
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    # 1. Guards
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")

    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    if session.status != "awaiting_attempt":
        raise ApiError(409, "conflict", "This session is already closed")

    # 2. Image validation & save
    if image is None or not image.filename:
        raise ApiError(422, "validation_error", "Upload a photo of your solution")

    data = image.file.read()
    rel = save_image(data, image.filename, "attempts", "a")

    # 3. Preparation
    trial_number = session.attempts_used + 1
    history = get_mistake_history(db, user.id)
    question = db.get(Question, session.question_id)
    question_dict = {
        "text": question.text,
        "topic": question.topic,
        "subject": question.subject,
    }

    # 4. AI call
    try:
        result = call_ai(
            ai_client.analyze_attempt,
            question_dict,
            str(absolute_path(rel)),
            trial_number,
            history,
            timeout=60,
        )
    except Exception:
        delete_file(rel)
        raise

    # 5. Result validation
    if not is_valid_analysis(result):
        delete_file(rel)
        raise ApiError(503, "ai_unavailable", "The AI returned an invalid response")

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 6. Unclear case
    if result["verdict"] == "unclear":
        delete_file(rel)
        # unclear photos do not use a trial (contract assumption 8); attempt id 0 means no attempt was saved.
        return AttemptResponse(
            attempt=AttemptInfo(
                id=0,
                trial_number=trial_number,
                image_url=None,
                submitted_at=now_iso,
            ),
            verdict="unclear",
            stage="retry",
            message=result["message"],
            diagnosis=[],
            topics_and_formulae=None,
            simplified_question=None,
            full_solution=None,
            efficient_method=None,
            attempts_used=session.attempts_used,
            session_status=session.status,
            followup_triggered=False,
        )

    # 7. Verdict & stage mapping
    if result["verdict"] == "correct":
        stage = "solved"
    elif trial_number == 1:
        stage = "hints"
    elif trial_number == 2:
        stage = "simplified"
    else:
        stage = "revealed"

    try:
        attempt = Attempt(
            session_id=session.id,
            trial_number=trial_number,
            image_path=rel,
            verdict=result["verdict"],
            stage=stage,
            submitted_at=now,
        )
        db.add(attempt)
        db.flush()

        # 8. If verdict is incorrect: insert mistake_history rows
        if result["verdict"] == "incorrect":
            for item in result["diagnosis"]:
                m = MistakeHistory(
                    student_id=user.id,
                    session_id=session.id,
                    attempt_id=attempt.id,
                    question_id=question.id,
                    topic=question.topic,
                    subject=question.subject,
                    mistake_type=item["mistake_type"],
                    step_number=item.get("step_number"),
                    description=item["description"],
                    created_at=now,
                )
                db.add(m)

        # 9. Verdict logic for additional data
        efficient_method = None
        topics_and_formulae = None
        simplified_question = None
        full_solution = None

        if result["verdict"] == "correct":
            session.status = "solved"
            if trial_number == 1:
                sol = call_ai(
                    ai_client.solve_question,
                    question.text,
                    question.topic,
                    [],
                    timeout=60,
                )
                if sol and sol.get("efficient_method"):
                    efficient_method = EfficientMethod(**sol["efficient_method"])
        else:
            # incorrect cases
            if trial_number == 1:
                session.status = "awaiting_attempt"
                if session.source in ("pyq", "followup_pyq"):
                    tf = call_ai(
                        ai_client.get_topics_and_formulae,
                        question.text,
                        question.topic,
                        timeout=60,
                    )
                    if tf:
                        topics_and_formulae = TopicsAndFormulae(**tf)
            elif trial_number == 2:
                session.status = "awaiting_attempt"
                simp_res = call_ai(
                    ai_client.simplify_question,
                    question.text,
                    question.topic,
                    result["diagnosis"],
                    timeout=60,
                )
                simplified_text = simp_res.get("simplified_text", "")
                gif_rel = f"gifs/q_{session.question_id}.gif"
                session.gif_status = "pending"
                session.gif_path = gif_rel
                background_tasks.add_task(
                    _bg_generate_gif,
                    session.id,
                    question.text,
                    simplified_text,
                    gif_rel,
                )
                simplified_question = SimplifiedQuestion(
                    text=simplified_text,
                    gif=GifInfo(status="pending", url=None),
                )
            elif trial_number == 3:
                session.status = "revealed"
                sol = call_ai(
                    ai_client.solve_question,
                    question.text,
                    question.topic,
                    result["diagnosis"],
                    timeout=60,
                )
                if sol:
                    full_solution = FullSolution(**sol)

        # 10. In every saved case
        session.attempts_used = trial_number
        db.commit()
        db.refresh(session)
        db.refresh(attempt)
    except Exception:
        db.rollback()
        delete_file(rel)
        raise

    # 11. followup_triggered: true when student needed all 3 attempts
    followup_triggered = bool(
        session.attempts_used == 3 and session.followup_of is None
    )
    session_status = session.status

    # 12. Build AttemptResponse
    submitted_at_str = attempt.submitted_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return AttemptResponse(
        attempt=AttemptInfo(
            id=attempt.id,
            trial_number=trial_number,
            image_url=f"/files/{rel}",
            submitted_at=submitted_at_str,
        ),
        verdict=result["verdict"],
        stage=stage,
        message=result["message"],
        diagnosis=[DiagnosisItem(**item) for item in result["diagnosis"]],
        topics_and_formulae=topics_and_formulae,
        simplified_question=simplified_question,
        full_solution=full_solution,
        efficient_method=efficient_method,
        attempts_used=session.attempts_used,
        session_status=session_status,
        followup_triggered=followup_triggered,
    )


# ─── E6: GET /student/sessions/{session_id}/gif ──────────────────────────────

@router.get("/sessions/{session_id}/gif", response_model=GifResponse)
def get_session_gif(
    session_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")
    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    status = session.gif_status or "pending"
    url = f"/files/{session.gif_path}" if status == "ready" and session.gif_path else None
    error = "GIF generation failed" if status == "failed" else None
    return GifResponse(status=status, url=url, error=error)


# ─── E7: POST /student/sessions/{session_id}/followups ───────────────────────

@router.post("/sessions/{session_id}/followups", response_model=FollowupsResponse, status_code=201)
def create_followups(
    session_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")
    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    if not (session.attempts_used == 3 and session.followup_of is None):
        raise ApiError(409, "conflict", "Follow-ups are only allowed when all 3 attempts were used")

    # Idempotent: return existing if already created
    existing = (
        db.query(SolveSession)
        .filter(SolveSession.followup_of == session.id)
        .order_by(SolveSession.followup_index.asc())
        .all()
    )
    if len(existing) == 3:
        return FollowupsResponse(
            followups=[build_session_out(s, db.get(Question, s.question_id)) for s in existing]
        )

    question = db.get(Question, session.question_id)
    pyqs_res = call_ai(
        ai_client.find_pyqs,
        question.topic,
        question.subject,
        2,
        [question.text],
        timeout=60,
    )
    pyqs = pyqs_res.get("questions", [])

    needed_gen = 3 - len(pyqs)
    history = get_mistake_history(db, user.id)

    items = []
    for p in pyqs:
        items.append({
            "text": p["question_text"],
            "topic": p["topic"],
            "subject": p.get("subject") or question.subject,
            "source": "followup_pyq",
            "book_id": p.get("book_id"),
            "reference": p.get("reference"),
        })

    for _ in range(needed_gen):
        g = call_ai(
            ai_client.generate_question,
            question.topic,
            question.subject,
            history,
            timeout=60,
        )
        items.append({
            "text": g["question_text"],
            "topic": g["topic"],
            "subject": g.get("subject") or question.subject,
            "source": "followup_generated",
            "book_id": None,
            "reference": None,
        })

    created_sessions = []
    for idx, item in enumerate(items):
        q = Question(
            text=item["text"],
            topic=item["topic"],
            subject=item["subject"],
            image_path=None,
            source_book_id=item["book_id"] if (item.get("book_id") is not None and db.get(Book, item["book_id"]) is not None) else None,
            reference=item["reference"],
        )
        db.add(q)
        db.flush()

        fs = SolveSession(
            student_id=user.id,
            question_id=q.id,
            source=item["source"],
            status="awaiting_attempt",
            attempts_used=0,
            homework_id=None,
            followup_of=session.id,
            followup_index=idx + 1,
        )
        db.add(fs)
        db.flush()
        created_sessions.append((fs, q))

    db.commit()
    for s, q in created_sessions:
        db.refresh(s)

    return FollowupsResponse(
        followups=[build_session_out(s, q) for s, q in created_sessions]
    )


# ─── E8: POST /student/sessions/{session_id}/skip ────────────────────────────

@router.post("/sessions/{session_id}/skip", response_model=SessionOut)
def skip_followup(
    session_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")
    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    # Only follow-up sessions can be skipped
    if session.followup_of is None:
        raise ApiError(403, "forbidden", "Only follow-up sessions can be skipped")

    session.status = "skipped"
    db.commit()
    db.refresh(session)

    question = db.get(Question, session.question_id)
    return build_session_out(session, question)


# ─── E22: GET /student/homework ──────────────────────────────────────────────

@router.get("/homework", response_model=StudentHomeworkListResponse)
def get_student_homework(
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    class_ids = [
        cs.class_id
        for cs in db.query(ClassStudent.class_id).filter(ClassStudent.student_id == user.id).all()
    ]
    if not class_ids:
        return StudentHomeworkListResponse(homework=[])

    homework_rows = (
        db.query(Homework)
        .filter(Homework.class_id.in_(class_ids))
        .all()
    )

    items = []
    for hw in homework_rows:
        question = db.get(Question, hw.question_id)
        teacher = db.get(User, hw.teacher_id)
        teacher_name = teacher.name if teacher else "Unknown"

        # Check for existing session
        solve_session = (
            db.query(SolveSession)
            .filter(SolveSession.student_id == user.id, SolveSession.homework_id == hw.id)
            .first()
        )

        if solve_session is None:
            status = "not_started"
            session_id = None
        elif solve_session.status in ("solved", "revealed"):
            status = "completed"
            session_id = solve_session.id
        else:
            status = "in_progress"
            session_id = solve_session.id

        assigned_at_str = hw.assigned_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        due_at_str = hw.due_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hw.due_at else None

        items.append(
            StudentHomeworkItem(
                homework_id=hw.id,
                title=hw.title,
                subject=question.subject if question else "General",
                topic=question.topic if question else "General",
                teacher_name=teacher_name,
                assigned_at=assigned_at_str,
                due_at=due_at_str,
                status=status,
                session_id=session_id,
            )
        )

    # Sorted by due_at ascending, nulls last
    items.sort(key=lambda x: (x.due_at is None, x.due_at or ""))

    return StudentHomeworkListResponse(homework=items)


# ─── E23: POST /student/sessions/homework ─────────────────────────────────────

@router.post("/sessions/homework", response_model=SessionOut)
def start_or_resume_homework_session(
    payload: StartHomeworkSessionRequest,
    response: Response,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    hw = db.get(Homework, payload.homework_id)
    if hw is None:
        raise ApiError(404, "not_found", "Homework not found")

    is_enrolled = (
        db.query(ClassStudent)
        .filter(ClassStudent.class_id == hw.class_id, ClassStudent.student_id == user.id)
        .first()
    )
    if not is_enrolled:
        raise ApiError(403, "forbidden", "This homework is not assigned to your class")

    existing = (
        db.query(SolveSession)
        .filter(SolveSession.student_id == user.id, SolveSession.homework_id == hw.id)
        .first()
    )
    if existing:
        q = db.get(Question, existing.question_id)
        response.status_code = 200
        return build_session_out(existing, q)

    session = SolveSession(
        student_id=user.id,
        question_id=hw.question_id,
        source="homework",
        status="awaiting_attempt",
        attempts_used=0,
        homework_id=hw.id,
        followup_of=None,
        followup_index=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    q = db.get(Question, hw.question_id)
    response.status_code = 201
    return build_session_out(session, q)


# ─── E24: POST /student/sessions/pyq ──────────────────────────────────────────

@router.post("/sessions/pyq", response_model=SessionOut, status_code=201)
def start_pyq_session(
    payload: StartPyqSessionRequest,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    book = db.get(Book, payload.book_id)
    if book is None:
        raise ApiError(404, "not_found", "Book not found")
    if book.status != "ready":
        raise ApiError(409, "conflict", "Book is not ready")

    extract_res = call_ai(
        ai_client.extract_question_from_book,
        payload.book_id,
        payload.chapter.strip() if payload.chapter else None,
        payload.question_ref.strip(),
        timeout=30,
    )
    if not extract_res or not extract_res.get("found"):
        raise ApiError(404, "question_not_found", "Question could not be found in the book")

    q_text = extract_res.get("question_text") or ""
    q_topic = extract_res.get("topic") or "General"
    q_subject = extract_res.get("subject") or book.subject

    q = Question(
        text=q_text,
        topic=q_topic,
        subject=q_subject,
        image_path=None,
        source_book_id=book.id,
        reference=payload.question_ref.strip(),
    )
    db.add(q)
    db.flush()

    session = SolveSession(
        student_id=user.id,
        question_id=q.id,
        source="pyq",
        status="awaiting_attempt",
        attempts_used=0,
        homework_id=None,
        followup_of=None,
        followup_index=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return build_session_out(session, q)


# ─── E25: GET /student/stats ──────────────────────────────────────────────────

@router.get("/stats", response_model=StudentStatsResponse)
def get_student_stats(
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(SolveSession)
        .filter(SolveSession.student_id == user.id)
        .all()
    )
    total_sessions = len(sessions)
    solved_sessions = sum(1 for s in sessions if s.status == "solved")
    avg_attempts = (
        round(sum(s.attempts_used for s in sessions) / total_sessions, 1)
        if total_sessions > 0
        else 0.0
    )
    totals = StudentTotals(
        sessions=total_sessions,
        solved=solved_sessions,
        avg_attempts=avg_attempts,
    )

    topic_subject_pairs = (
        db.query(Question.topic, Question.subject)
        .join(SolveSession, SolveSession.question_id == Question.id)
        .filter(SolveSession.student_id == user.id)
        .distinct()
        .all()
    )

    topic_stats = []
    for topic, subject in topic_subject_pairs:
        top_sessions = (
            db.query(SolveSession)
            .join(Question, SolveSession.question_id == Question.id)
            .filter(SolveSession.student_id == user.id, Question.topic == topic)
            .order_by(SolveSession.created_at.desc())
            .all()
        )
        last_5 = top_sessions[:5]
        n_last = len(last_5)

        if n_last >= 2 and (sum(1 for s in last_5 if s.attempts_used >= 3 or s.status == "revealed") >= n_last / 2):
            status_val = "weak"
        elif n_last >= 3 and (sum(1 for s in last_5 if s.status == "solved" and s.attempts_used <= 2) >= 0.7 * n_last):
            status_val = "strong"
        else:
            status_val = "learning"

        m_rows = (
            db.query(MistakeHistory.mistake_type, func.count(MistakeHistory.id))
            .filter(MistakeHistory.student_id == user.id, MistakeHistory.topic == topic)
            .group_by(MistakeHistory.mistake_type)
            .all()
        )
        counts_map = dict(m_rows)
        topic_mistakes = TopicMistakeCounts(
            sign_error=counts_map.get("sign_error", 0),
            formula_misuse=counts_map.get("formula_misuse", 0),
            unit_slip=counts_map.get("unit_slip", 0),
            concept_gap=counts_map.get("concept_gap", 0),
        )

        topic_stats.append(
            TopicStatInfo(
                topic=topic,
                subject=subject or "General",
                status=status_val,
                sessions=len(top_sessions),
                mistake_counts=topic_mistakes,
            )
        )

    all_m_rows = (
        db.query(MistakeHistory.mistake_type, func.count(MistakeHistory.id))
        .filter(MistakeHistory.student_id == user.id)
        .group_by(MistakeHistory.mistake_type)
        .all()
    )
    all_counts = {
        "sign_error": 0,
        "formula_misuse": 0,
        "unit_slip": 0,
        "concept_gap": 0,
    }
    for m_type, cnt in all_m_rows:
        if m_type in all_counts:
            all_counts[m_type] = cnt

    mistake_types_list = [
        MistakeTypeStat(type=k, count=v)
        for k, v in sorted(all_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    return StudentStatsResponse(
        totals=totals,
        topics=topic_stats,
        mistake_types=mistake_types_list,
    )


# ─── E27: GET /student/sessions/{session_id}/videos ──────────────────────────

@router.get("/sessions/{session_id}/videos", response_model=VideosResponse)
def get_session_videos(
    session_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    session = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found")
    if session.student_id != user.id:
        raise ApiError(403, "forbidden", "This session belongs to someone else")

    question = db.get(Question, session.question_id)
    if question is None:
        raise ApiError(404, "not_found", "Question not found")

    cache = db.query(VideoCache).filter(VideoCache.question_id == question.id).first()
    if cache:
        try:
            videos = json.loads(cache.videos_json)
        except Exception:
            videos = []
    else:
        result = call_ai(
            ai_client.find_videos,
            question.topic,
            question.text,
            timeout=20,
        )
        videos = result.get("videos", []) if result else []
        new_cache = VideoCache(
            question_id=question.id,
            videos_json=json.dumps(videos),
        )
        db.add(new_cache)
        db.commit()

    return VideosResponse(
        videos=[
            VideoItem(
                title=v.get("title", ""),
                url=v.get("url", ""),
                channel=v.get("channel", ""),
                kind=v.get("kind", "topic_explainer"),
            )
            for v in videos
        ]
    )

