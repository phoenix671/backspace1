from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import string

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import ApiError
from app.models import User


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def generate_initial_password() -> str:
    digits = f"{secrets.randbelow(10000):04d}"
    return f"mock{digits}"


def role_from_email(email: str) -> str | None:
    cleaned = email.strip().lower()
    if "@" not in cleaned:
        return None
    domain = cleaned.rsplit("@", 1)[1]
    if domain == settings.FACULTY_DOMAIN.lower():
        return "faculty"
    if domain == settings.TEACHER_DOMAIN.lower():
        return "teacher"
    if domain == settings.STUDENT_DOMAIN.lower():
        return "student"
    return None


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise ApiError(401, "unauthorized", "Missing or invalid token")
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise ApiError(401, "unauthorized", "Missing or invalid token")
    user_id_str = payload.get("sub")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise ApiError(401, "unauthorized", "Missing or invalid token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise ApiError(401, "unauthorized", "Missing or invalid token")
    return user


def require_role(*roles: str):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ApiError(403, "forbidden", "You do not have access to this resource")
        return user

    return role_checker

