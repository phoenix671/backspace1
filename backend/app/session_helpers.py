from sqlalchemy.orm import Session

from app.models import Attempt, Question, SolveSession


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

