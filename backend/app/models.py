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


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(100))
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_book_id: Mapped[Optional[int]] = mapped_column(ForeignKey("books.id"), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class Homework(Base):
    __tablename__ = "homework"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    chapter: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    question_ref: Mapped[str] = mapped_column(String(200))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)



