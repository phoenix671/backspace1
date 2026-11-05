from typing import Any, Dict, Optional

from app.models import Attempt, Question, SolveSession


def build_session_out(session: SolveSession, question: Question) -> Dict[str, Any]:
    image_url = f"/files/{question.image_path}" if question.image_path else None
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


def build_attempt_out(attempt: Attempt) -> Dict[str, Any]:
    image_url = f"/files/{attempt.image_path}" if attempt.image_path else None
    submitted_at = attempt.submitted_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "id": attempt.id,
        "trial_number": attempt.trial_number,
        "image_url": image_url,
        "verdict": attempt.verdict,
        "stage": attempt.stage,
        "submitted_at": submitted_at,
    }

