from sqlalchemy.orm import Session

from app.models import Attempt, MistakeHistory, Question, SolveSession


def build_session_dict(db: Session, session: SolveSession) -> dict:
    question: Question = db.get(Question, session.question_id)

    image_url = None
    if question.image_path:
        image_url = "/files/" + question.image_path

    followup_triggered = (session.attempts_used == 3) and (session.followup_of is None)

    created_at = session.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id": session.id,
        "source": session.source,
        "status": session.status,
        "question": {
            "id": question.id,
            "text": question.text,
            "topic": question.topic,
            "subject": question.subject,
            "image_url": image_url,
        },
        "homework_id": session.homework_id,
        "followup_of": session.followup_of,
        "followup_index": session.followup_index,
        "attempts_used": session.attempts_used,
        "max_attempts": 3,
        "followup_triggered": followup_triggered,
        "created_at": created_at,
    }



def get_mistake_history(db: Session, student_id: int, limit: int = 50) -> list[dict]:
    rows = (
        db.query(MistakeHistory)
        .filter(MistakeHistory.student_id == student_id)
        .order_by(MistakeHistory.created_at.desc(), MistakeHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "topic": r.topic,
            "mistake_type": r.mistake_type,
            "step_number": r.step_number,
            "description": r.description,
            "created_at": r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for r in rows
    ]


def is_valid_analysis(result) -> bool:
    try:
        if not isinstance(result, dict):
            return False

        verdict = result.get("verdict")
        if verdict not in ("correct", "incorrect", "unclear"):
            return False

        message = result.get("message")
        if not isinstance(message, str) or len(message) == 0:
            return False

        diagnosis = result.get("diagnosis")
        if not isinstance(diagnosis, list):
            return False

        if verdict in ("correct", "unclear"):
            if len(diagnosis) != 0:
                return False
        elif verdict == "incorrect":
            if len(diagnosis) < 1:
                return False

        valid_mistake_types = {"sign_error", "formula_misuse", "unit_slip", "concept_gap"}

        for item in diagnosis:
            if not isinstance(item, dict):
                return False

            step_number = item.get("step_number")
            if not isinstance(step_number, int) or isinstance(step_number, bool):
                return False

            student_wrote = item.get("student_wrote")
            if not isinstance(student_wrote, str):
                return False

            expected = item.get("expected")
            if not isinstance(expected, str):
                return False

            mistake_type = item.get("mistake_type")
            if mistake_type not in valid_mistake_types:
                return False

            description = item.get("description")
            if not isinstance(description, str):
                return False

        return True
    except Exception:
        return False
