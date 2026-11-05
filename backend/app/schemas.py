from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


class QuestionOut(BaseModel):
    id: int
    text: str
    topic: str
    subject: str
    image_url: Optional[str]


class SessionOut(BaseModel):
    id: int
    source: str
    status: str
    question: QuestionOut
    homework_id: Optional[int]
    followup_of: Optional[int]
    followup_index: Optional[int]
    attempts_used: int
    max_attempts: int
    followup_triggered: bool
    created_at: str


class AttemptOut(BaseModel):
    id: int
    trial_number: int
    image_url: Optional[str]
    verdict: str
    stage: str
    submitted_at: str


class SessionDetailOut(BaseModel):
    session: SessionOut
    attempts: list[AttemptOut]

