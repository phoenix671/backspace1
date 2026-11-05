from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Teacher(Base):
    __tablename__ = "teachers"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class SchoolClass(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class ClassStudent(Base):
    __tablename__ = "class_students"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    roll_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ClassSubjectTeacher(Base):
    __tablename__ = "class_subject_teachers"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(100), primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


