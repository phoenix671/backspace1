import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app import ai_client
from app.config import settings
from app.database import get_db
from app.errors import ApiError
from app.models import Attempt, Question, SolveSession
from app.schemas import AttemptOut, SessionDetailOut, SessionOut
from app.security import get_current_user, require_role
from app.session_helpers import build_session_dict

router = APIRouter(prefix="/student", tags=["student"])

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_MAX_SIZE = 5 * 1024 * 1024  # 5 MB

_PNG_MAGIC = b"\x89PNG"
_JPEG_MAGIC = b"\xff\xd8\xff"


def _detect_ext(header: bytes) -> Optional[str]:
    if header[:4] == _PNG_MAGIC:
        return ".png"
    if header[:3] == _JPEG_MAGIC:
        return ".jpg"
    return None


def _extension_matches_magic(submitted_ext: str, detected_ext: Optional[str]) -> bool:
    """Return True if the submitted file extension is consistent with the magic bytes."""
    if detected_ext is None:
        return False
    if submitted_ext == ".png":
        return detected_ext == ".png"
    if submitted_ext in (".jpg", ".jpeg"):
        return detected_ext == ".jpg"
    return False


# ─── E3: POST /student/sessions/upload ───────────────────────────────────────

@router.post("/sessions/upload", status_code=201)
def upload_session(
    image: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("student")),
):
    # Validate that at least one of image or non-empty text was sent
    has_text = text is not None and text.strip() != ""
    has_image = image is not None and image.filename != ""

    if not has_image and not has_text:
        raise ApiError(422, "validation_error", "Provide an image or question text.")

    saved_path: Optional[Path] = None

    try:
        if has_image:
            # Read bytes
            raw = image.file.read()

            # Size check
            if len(raw) > _MAX_SIZE:
                raise ApiError(422, "validation_error", "Image exceeds 5 MB limit.")

            # Extension check
            suffix = Path(image.filename).suffix.lower()
            if suffix not in _ALLOWED_EXTENSIONS:
                raise ApiError(422, "validation_error", f"Unsupported file type: {suffix}.")

            # Magic bytes check — must also match the submitted extension
            detected_ext = _detect_ext(raw[:4])
            if not _extension_matches_magic(suffix, detected_ext):
                raise ApiError(422, "validation_error", "File header does not match a supported image type.")

            # Map detected extension to canonical ext
            if detected_ext == ".png":
                canonical_ext = ".png"
            else:
                canonical_ext = ".jpg"

            # Save file
            uploads_dir = settings.storage_path / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            filename = f"q_{secrets.token_hex(6)}{canonical_ext}"
            abs_path = uploads_dir / filename
            abs_path.write_bytes(raw)
            saved_path = abs_path
            # Relative to storage_path (the files root)
            rel_image_path = "uploads/" + filename

            # Call AI for extraction
            result = ai_client.call_ai(
                ai_client.extract_question_from_image,
                str(abs_path),
                timeout=60,
            )

            if not result.get("readable"):
                # Clean up and return 422
                abs_path.unlink(missing_ok=True)
                raise ApiError(422, "image_unreadable", "Could not extract a question from the image.")

            question_text = result.get("question_text") or ""
            topic = result.get("topic") or "General"
            subject = result.get("subject") or "Physics"
            image_path_for_db = rel_image_path

        else:
            # Text-only path
            question_text = text.strip()
            image_path_for_db = None

            # TODO: Temporary topic detection; replace with classify AI function when available
            topic = "General"
            subject = "Physics"
            q_lower = question_text.lower()
            for t in ai_client.TOPICS:
                if t.lower() in q_lower:
                    topic = t
                    subject = "Physics"
                    break

        # Insert Question
        question = Question(
            text=question_text,
            topic=topic,
            subject=subject,
            image_path=image_path_for_db,
            source_book_id=None,
            reference=None,
        )
        db.add(question)
        db.flush()

        # Insert Session
        session = SolveSession(
            student_id=current_user.id,
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

        return build_session_dict(db, session)

    except ApiError:
        # On any ApiError after file was saved, remove it
        if saved_path and saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        if saved_path and saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise


# ─── E4: GET /student/sessions/{session_id} ──────────────────────────────────

@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("student")),
):
    session: Optional[SolveSession] = db.get(SolveSession, session_id)
    if session is None:
        raise ApiError(404, "not_found", "Session not found.")
    if session.student_id != current_user.id:
        raise ApiError(403, "forbidden", "You do not have access to this session.")

    attempts = (
        db.query(Attempt)
        .filter(Attempt.session_id == session_id)
        .order_by(Attempt.trial_number, Attempt.id)
        .all()
    )

    def attempt_dict(a: Attempt) -> dict:
        img_url = None
        if a.image_path:
            img_url = "/files/" + a.image_path
        return {
            "id": a.id,
            "trial_number": a.trial_number,
            "image_url": img_url,
            "verdict": a.verdict,
            "stage": a.stage,
            "submitted_at": a.submitted_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    return {
        "session": build_session_dict(db, session),
        "attempts": [attempt_dict(a) for a in attempts],
    }
