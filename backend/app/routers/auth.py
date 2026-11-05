from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, get_current_user, role_from_email, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=200)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    expected_role = role_from_email(email)
    if expected_role is None:
        raise ApiError(401, "unauthorized", "Wrong email or password")

    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or user.role != expected_role:
        raise ApiError(401, "unauthorized", "Wrong email or password")

    if not verify_password(request.password, user.password_hash):
        raise ApiError(401, "unauthorized", "Wrong email or password")

    token = create_access_token(user.id, user.role)
    return LoginResponse(token=token, token_type="bearer", user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user

