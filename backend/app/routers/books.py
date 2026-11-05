from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import ApiError
from app.models import Book, ClassSubjectTeacher, Teacher, User
from app.schemas import BookInfo, BookListResponse
from app.security import get_current_user

router = APIRouter(prefix="/books", tags=["books"])


def _check_book_access(user: User, book: Book, db: Session) -> bool:
    if user.role == "faculty":
        return True
    elif user.role == "teacher":
        # Teacher can access books of their subject(s)
        t = db.get(Teacher, user.id)
        teacher_subjects = set()
        if t and t.subject:
            teacher_subjects.add(t.subject.lower())
        cst_subjects = db.query(ClassSubjectTeacher.subject).filter_by(teacher_id=user.id).all()
        for (sub,) in cst_subjects:
            if sub:
                teacher_subjects.add(sub.lower())
        return book.subject.lower() in teacher_subjects
    elif user.role == "student":
        # Student sees all books with status ready
        return book.status == "ready"
    return False


# ─── E15: GET /books ────────────────────────────────────────────────────────

@router.get("", response_model=BookListResponse)
def list_books(
    q: Optional[str] = None,
    type: Optional[str] = None,
    subject: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Book)

    if current_user.role == "student":
        query = query.filter(Book.status == "ready")
    elif current_user.role == "teacher":
        t = db.get(Teacher, current_user.id)
        teacher_subjects = set()
        if t and t.subject:
            teacher_subjects.add(t.subject.lower())
        cst_subjects = db.query(ClassSubjectTeacher.subject).filter_by(teacher_id=current_user.id).all()
        for (sub,) in cst_subjects:
            if sub:
                teacher_subjects.add(sub.lower())

        if not teacher_subjects:
            return BookListResponse(books=[])
        query = query.filter(or_(*[Book.subject.ilike(s) for s in teacher_subjects]))

    if q:
        query = query.filter(Book.name.ilike(f"%{q.strip()}%"))
    if type:
        query = query.filter(Book.type == type.strip())
    if subject:
        query = query.filter(Book.subject.ilike(subject.strip()))

    books = query.order_by(Book.id.asc()).all()
    res = [
        BookInfo(
            id=b.id,
            name=b.name,
            type=b.type,
            subject=b.subject,
            status=b.status,
            page_count=b.page_count,
            error=b.error,
        )
        for b in books
    ]
    return BookListResponse(books=res)


# ─── E16: GET /books/{book_id} ──────────────────────────────────────────────

@router.get("/{book_id}", response_model=BookInfo)
def get_book(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    b = db.get(Book, book_id)
    if not b:
        raise ApiError(404, "not_found", "Book not found")

    if not _check_book_access(current_user, b, db):
        raise ApiError(403, "forbidden", "You do not have access to this book")

    return BookInfo(
        id=b.id,
        name=b.name,
        type=b.type,
        subject=b.subject,
        status=b.status,
        page_count=b.page_count,
        error=b.error,
    )


# ─── E17: GET /books/{book_id}/file ─────────────────────────────────────────

@router.get("/{book_id}/file")
def get_book_file(
    book_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    b = db.get(Book, book_id)
    if not b:
        raise ApiError(404, "not_found", "Book not found")

    if not _check_book_access(current_user, b, db):
        raise ApiError(403, "forbidden", "You do not have access to this book")

    file_path = Path(b.file_path)
    if not file_path.exists():
        candidate = settings.private_books_path / b.file_path
        if candidate.exists():
            file_path = candidate
        else:
            raise ApiError(404, "not_found", "Book file not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=f"{b.name}.pdf",
    )
