import secrets
from pathlib import Path
from typing import Optional

from app.config import settings
from app.errors import ApiError

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
    if detected_ext is None:
        return False
    if submitted_ext == ".png":
        return detected_ext == ".png"
    if submitted_ext in (".jpg", ".jpeg"):
        return detected_ext == ".jpg"
    return False


def save_image(data: bytes, filename: str, folder: str, prefix: str) -> str:
    """Validate image extension, size, and magic bytes, save to storage, and return relative path."""
    if len(data) > _MAX_SIZE:
        raise ApiError(422, "validation_error", "Image exceeds 5 MB limit.")

    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise ApiError(422, "validation_error", f"Unsupported file type: {suffix}.")

    detected_ext = _detect_ext(data[:4])
    if not _extension_matches_magic(suffix, detected_ext):
        raise ApiError(422, "validation_error", "File header does not match a supported image type.")

    canonical_ext = ".png" if detected_ext == ".png" else ".jpg"

    target_dir = settings.storage_path / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    rand_hex = secrets.token_hex(6)
    out_name = f"{prefix}_{rand_hex}{canonical_ext}"
    abs_path = target_dir / out_name
    abs_path.write_bytes(data)

    return f"{folder}/{out_name}"


def absolute_path(rel: str | Path) -> Path:
    return settings.storage_path / rel


def delete_file(rel: Optional[str | Path]) -> None:
    if not rel:
        return
    try:
        abs_p = absolute_path(rel)
        if abs_p.exists():
            abs_p.unlink(missing_ok=True)
    except Exception:
        pass

