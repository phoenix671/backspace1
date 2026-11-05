from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import ai_client
from app.ai_client import call_ai
from app.database import get_db
from app.errors import ApiError
from app.models import (
    Book,
    ClassStudent,
    ClassSubjectTeacher,
    Homework,
    MistakeHistory,
    Question,
    SchoolClass,
    SolveSession,
    User,
    utcnow,
)
from app.schemas import (
    BookSummary,
    ClassStatusResponse,
    HomeworkCompletionSummary,
    HomeworkCreateRequest,
    HomeworkDetail,
    HomeworkGraphResponse,
    HomeworkSummaryItem,
    RecentQueryItem,
    StrugglingTopicInfo,
    StudentCompletionInfo,
    StudentSummary,
    TeacherClassesResponse,
    TeacherClassInfo,
    TeacherHomeworkListResponse,
)
from app.security import require_role

router = APIRouter(prefix="/teacher", tags=["teacher"])


# ─── E18: GET /teacher/classes ──────────────────────────────────────────────

@router.get("/classes", response_model=TeacherClassesResponse)
def get_teacher_classes(
    user=Depends(require_role("teacher")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ClassSubjectTeacher, SchoolClass)
        .join(SchoolClass, ClassSubjectTeacher.class_id == SchoolClass.id)
        .filter(ClassSubjectTeacher.teacher_id == user.id)
        .order_by(SchoolClass.name.asc())
        .all()
    )
    res = []
    for cst, sc in rows:
        cnt = db.query(ClassStudent).filter_by(class_id=sc.id, is_active=True).count()
        res.append(
            TeacherClassInfo(
                class_id=sc.id,
                name=sc.name,
                subject=cst.subject,
                student_count=cnt,
            )
        )
    return TeacherClassesResponse(classes=res)


# ─── E19: POST /teacher/classes/{class_id}/homework ─────────────────────────

@router.post("/classes/{class_id}/homework", response_model=HomeworkDetail, status_code=201)
def assign_homework(
    class_id: int,
    req: HomeworkCreateRequest,
    user=Depends(require_role("teacher")),
    db: Session = Depends(get_db),
):
    cst = db.query(ClassSubjectTeacher).filter_by(class_id=class_id, teacher_id=user.id).first()
    if not cst:
        raise ApiError(403, "forbidden", "You do not teach this class")

    book = db.get(Book, req.book_id)
    if not book:
        raise ApiError(404, "not_found", "Book not found")
    if book.status != "ready":
        raise ApiError(409, "conflict", "Book is not ready")

    if not req.question_ref.strip():
        raise ApiError(422, "validation_error", "Question reference is required")

    # Extract question from book
    extract_res = call_ai(
        ai_client.extract_question_from_book,
        book.id,
        req.chapter,
        req.question_ref.strip(),
        timeout=30,
    )
    if not extract_res or not extract_res.get("found"):
        raise ApiError(404, "question_not_found", "Question could not be found in the book")

    q_text = extract_res.get("question_text") or ""
    q_topic = extract_res.get("topic") or "General"
    q_subject = extract_res.get("subject") or book.subject

    # Insert question
    question = Question(
        text=q_text,
        topic=q_topic,
        subject=q_subject,
        image_path=None,
        source_book_id=book.id,
        reference=req.question_ref.strip(),
    )
    db.add(question)
    db.flush()

    due_at_dt = None
    if req.due_at:
        try:
            due_at_dt = datetime.fromisoformat(req.due_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            due_at_dt = None

    assigned_at_dt = utcnow()

    hw = Homework(
        class_id=class_id,
        teacher_id=user.id,
        book_id=book.id,
        chapter=req.chapter.strip() if req.chapter else None,
        question_ref=req.question_ref.strip(),
        question_id=question.id,
        title=req.title.strip() if req.title else None,
        assigned_at=assigned_at_dt,
        due_at=due_at_dt,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)

    return HomeworkDetail(
        id=hw.id,
        class_id=hw.class_id,
        title=hw.title,
        book=BookSummary(id=book.id, name=book.name),
        chapter=hw.chapter,
        question_ref=hw.question_ref,
        question_text=question.text,
        topic=question.topic,
        assigned_at=hw.assigned_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        due_at=hw.due_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hw.due_at else None,
    )


# ─── E20: GET /teacher/classes/{class_id}/homework ─────────────────────────

@router.get("/classes/{class_id}/homework", response_model=TeacherHomeworkListResponse)
def list_class_homework(
    class_id: int,
    user=Depends(require_role("teacher")),
    db: Session = Depends(get_db),
):
    cst = db.query(ClassSubjectTeacher).filter_by(class_id=class_id, teacher_id=user.id).first()
    if not cst:
        raise ApiError(403, "forbidden", "You do not teach this class")

    total_students = db.query(ClassStudent).filter_by(class_id=class_id, is_active=True).count()

    hws = (
        db.query(Homework, Question)
        .join(Question, Homework.question_id == Question.id)
        .filter(Homework.class_id == class_id, Homework.teacher_id == user.id)
        .order_by(Homework.assigned_at.desc())
        .all()
    )

    items = []
    for hw, q in hws:
        completed = (
            db.query(SolveSession)
            .join(ClassStudent, SolveSession.student_id == ClassStudent.student_id)
            .filter(
                ClassStudent.class_id == class_id,
                SolveSession.homework_id == hw.id,
                SolveSession.status.in_(["solved", "revealed"]),
            )
            .distinct()
            .count()
        )
        items.append(
            HomeworkSummaryItem(
                id=hw.id,
                title=hw.title,
                topic=q.topic,
                assigned_at=hw.assigned_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                due_at=hw.due_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hw.due_at else None,
                completed=completed,
                total=total_students,
            )
        )

    return TeacherHomeworkListResponse(homework=items)


# ─── E21: GET /teacher/homework/{homework_id} ───────────────────────────────

@router.get("/homework/{homework_id}", response_model=HomeworkGraphResponse)
def get_homework_graph(
    homework_id: int,
    user=Depends(require_role("teacher")),
    db: Session = Depends(get_db),
):
    hw = db.get(Homework, homework_id)
    if not hw:
        raise ApiError(404, "not_found", "Homework not found")

    if hw.teacher_id != user.id:
        raise ApiError(403, "forbidden", "You did not assign this homework")

    question = db.get(Question, hw.question_id)

    students = (
        db.query(ClassStudent, User)
        .join(User, ClassStudent.student_id == User.id)
        .filter(ClassStudent.class_id == hw.class_id, ClassStudent.is_active == True)
        .order_by(User.name.asc())
        .all()
    )

    student_infos = []
    completed_count = 0
    for cs, u in students:
        sess = (
            db.query(SolveSession)
            .filter_by(homework_id=hw.id, student_id=u.id)
            .first()
        )
        is_comp = sess is not None and sess.status in ("solved", "revealed")
        comp_at = sess.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if (is_comp and sess) else None
        if is_comp:
            completed_count += 1
        student_infos.append(
            StudentCompletionInfo(
                student_id=u.id,
                name=u.name,
                completed=is_comp,
                completed_at=comp_at,
            )
        )

    return HomeworkGraphResponse(
        id=hw.id,
        title=hw.title,
        question_text=question.text,
        topic=question.topic,
        due_at=hw.due_at.strftime("%Y-%m-%dT%H:%M:%SZ") if hw.due_at else None,
        completion=HomeworkCompletionSummary(
            completed=completed_count,
            total=len(students),
            students=student_infos,
        ),
    )


# ─── E26: GET /teacher/classes/{class_id}/status ───────────────────────────

@router.get("/classes/{class_id}/status", response_model=ClassStatusResponse)
def get_class_status(
    class_id: int,
    user=Depends(require_role("teacher")),
    db: Session = Depends(get_db),
):
    cst = db.query(ClassSubjectTeacher).filter_by(class_id=class_id, teacher_id=user.id).first()
    if not cst:
        raise ApiError(403, "forbidden", "You do not teach this class")

    subject = cst.subject
    total_students = db.query(ClassStudent).filter_by(class_id=class_id, is_active=True).count()

    # Active students in class
    class_student_ids = [
        cs.student_id for cs in db.query(ClassStudent).filter_by(class_id=class_id, is_active=True).all()
    ]

    # Topics and struggling count
    # Find all topics with questions in this subject
    topics = [
        t[0] for t in db.query(Question.topic).filter(Question.subject.ilike(subject)).distinct().all()
    ]

    struggling_topics = []
    for topic in topics:
        weak_count = 0
        for sid in class_student_ids:
            # Last 5 sessions on this topic for this student
            s_rows = (
                db.query(SolveSession)
                .join(Question, SolveSession.question_id == Question.id)
                .filter(
                    SolveSession.student_id == sid,
                    Question.topic == topic,
                )
                .order_by(SolveSession.created_at.desc())
                .limit(5)
                .all()
            )
            if len(s_rows) >= 2:
                exhausted = sum(1 for s in s_rows if s.attempts_used >= 3 or s.status == "revealed")
                if exhausted >= len(s_rows) / 2:
                    weak_count += 1

        # Top mistake type for this topic among class students
        top_m = (
            db.query(MistakeHistory.mistake_type, func.count(MistakeHistory.id).label("cnt"))
            .filter(
                MistakeHistory.student_id.in_(class_student_ids) if class_student_ids else False,
                MistakeHistory.topic == topic,
            )
            .group_by(MistakeHistory.mistake_type)
            .order_by(func.count(MistakeHistory.id).desc())
            .first()
        )
        top_mistake = top_m[0] if top_m else None

        struggling_topics.append(
            StrugglingTopicInfo(
                topic=topic,
                struggling_students=weak_count,
                total_students=total_students,
                top_mistake_type=top_mistake,
            )
        )

    # Recent queries: latest 50 sessions for students in this class for questions in this subject
    recent_sessions = (
        db.query(SolveSession, Question, User)
        .join(Question, SolveSession.question_id == Question.id)
        .join(User, SolveSession.student_id == User.id)
        .filter(
            SolveSession.student_id.in_(class_student_ids) if class_student_ids else False,
            Question.subject.ilike(subject),
        )
        .order_by(SolveSession.created_at.desc())
        .limit(50)
        .all()
    )

    recent_queries = []
    for sess, q, u in recent_sessions:
        last_m = (
            db.query(MistakeHistory.mistake_type)
            .filter_by(session_id=sess.id)
            .order_by(MistakeHistory.created_at.desc(), MistakeHistory.id.desc())
            .first()
        )
        last_m_type = last_m[0] if last_m else None

        recent_queries.append(
            RecentQueryItem(
                student=StudentSummary(id=u.id, name=u.name),
                question_text=q.text,
                topic=q.topic,
                source=sess.source,
                attempts_used=sess.attempts_used,
                status=sess.status,
                last_mistake_type=last_m_type,
                at=sess.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )

    return ClassStatusResponse(
        class_id=class_id,
        subject=subject,
        struggling_topics=struggling_topics,
        recent_queries=recent_queries,
    )

