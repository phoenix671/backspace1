import re
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app import ai_client
from app.config import settings
from app.database import SessionLocal, get_db
from app.errors import ApiError
from app.models import Book, ClassStudent, ClassSubjectTeacher, SchoolClass, Teacher, User
from app.schemas import (
    AddStudentRequest,
    AddStudentResponse,
    BookInfo,
    ClassCreateRequest,
    ClassCreateResponse,
    ClassDetailResponse,
    ClassInfo,
    ClassListResponse,
    StudentCredentials,
    StudentDetail,
    StudentSummary,
    SubjectTeacherAssignment,
    TeacherCreateRequest,
    TeacherCreateResponse,
    TeacherCredentials,
    TeacherInfo,
    TeacherListResponse,
    UpdateSubjectTeachersRequest,
)
from app.security import generate_initial_password, hash_password, require_role

router = APIRouter(prefix="/faculty", tags=["faculty"])

_MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB


def generate_unique_email(db: Session, name: str, domain: str) -> str:
    clean_parts = [re.sub(r"[^a-zA-Z0-9]", "", part).lower() for part in name.strip().split() if part]
    base = ".".join(clean_parts) if clean_parts else "user"
    candidate = f"{base}@{domain.lower()}"
    idx = 2
    while db.query(User).filter(User.email == candidate).first() is not None:
        candidate = f"{base}{idx}@{domain.lower()}"
        idx += 1
    return candidate


def _bg_ingest_book(book_id: int, abs_file_path: str, name: str, subject: str, b_type: str):
    try:
        res = ai_client.call_ai(
            ai_client.ingest_book,
            book_id,
            abs_file_path,
            name,
            subject,
            b_type,
            timeout=300,
        )
        with SessionLocal() as db:
            b = db.get(Book, book_id)
            if b:
                if res and res.get("status") == "ready":
                    b.status = "ready"
                    b.page_count = res.get("page_count")
                    b.error = None
                else:
                    b.status = "failed"
                    b.error = res.get("error") if res else "Failed to parse PDF"
                db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            b = db.get(Book, book_id)
            if b:
                b.status = "failed"
                b.error = str(exc)
                db.commit()


# ─── E9: POST /faculty/teachers ─────────────────────────────────────────────

@router.post("/teachers", response_model=TeacherCreateResponse, status_code=201)
def create_teacher(
    req: TeacherCreateRequest,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    if not req.name.strip() or not req.subject.strip():
        raise ApiError(422, "validation_error", "Name and subject are required")

    email = generate_unique_email(db, req.name, settings.TEACHER_DOMAIN)
    initial_password = generate_initial_password()
    pw_hash = hash_password(initial_password)

    u = User(
        name=req.name.strip(),
        email=email,
        password_hash=pw_hash,
        role="teacher",
        is_active=True,
    )
    db.add(u)
    db.flush()

    t = Teacher(
        user_id=u.id,
        subject=req.subject.strip(),
        phone=req.phone.strip() if req.phone else None,
    )
    db.add(t)
    db.commit()
    db.refresh(u)
    db.refresh(t)

    return TeacherCreateResponse(
        teacher=TeacherInfo(id=u.id, name=u.name, subject=t.subject),
        credentials=TeacherCredentials(email=u.email, initial_password=initial_password),
    )


# ─── E10: GET /faculty/teachers ─────────────────────────────────────────────

@router.get("/teachers", response_model=TeacherListResponse)
def list_teachers(
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Teacher, User)
        .join(User, Teacher.user_id == User.id)
        .filter(User.is_active == True)
        .order_by(User.id.asc())
        .all()
    )
    teachers = [
        TeacherInfo(id=u.id, name=u.name, subject=t.subject, email=u.email)
        for t, u in rows
    ]
    return TeacherListResponse(teachers=teachers)


# ─── E11: POST /faculty/classes ─────────────────────────────────────────────

@router.post("/classes", response_model=ClassCreateResponse, status_code=201)
def create_class(
    req: ClassCreateRequest,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    if not req.name.strip():
        raise ApiError(422, "validation_error", "Class name is required")

    if not req.students:
        raise ApiError(422, "validation_error", "Class requires at least 1 student")

    existing_class = db.query(SchoolClass).filter(SchoolClass.name == req.name.strip()).first()
    if existing_class:
        raise ApiError(409, "conflict", "Class name already exists")

    # Validate all teacher IDs exist
    for st in req.subject_teachers:
        t = db.query(Teacher).filter(Teacher.user_id == st.teacher_id).first()
        if not t:
            raise ApiError(422, "validation_error", f"Teacher ID {st.teacher_id} not found")

    sc = SchoolClass(name=req.name.strip())
    db.add(sc)
    db.flush()

    credentials = []
    for s_in in req.students:
        s_email = generate_unique_email(db, s_in.name, settings.STUDENT_DOMAIN)
        initial_pw = generate_initial_password()
        u_student = User(
            name=s_in.name.strip(),
            email=s_email,
            password_hash=hash_password(initial_pw),
            role="student",
            is_active=True,
        )
        db.add(u_student)
        db.flush()

        cs = ClassStudent(
            class_id=sc.id,
            student_id=u_student.id,
            roll_number=s_in.roll_number.strip() if s_in.roll_number else None,
            is_active=True,
        )
        db.add(cs)

        credentials.append(
            StudentCredentials(
                student_id=u_student.id,
                name=u_student.name,
                email=u_student.email,
                initial_password=initial_pw,
            )
        )

    for st in req.subject_teachers:
        cst = ClassSubjectTeacher(
            class_id=sc.id,
            subject=st.subject.strip(),
            teacher_id=st.teacher_id,
        )
        db.add(cst)

    db.commit()
    db.refresh(sc)

    return ClassCreateResponse(
        class_=ClassInfo(id=sc.id, name=sc.name, student_count=len(req.students)),
        credentials=credentials,
    )


# ─── E12: GET /faculty/classes ─────────────────────────────────────────────

@router.get("/classes", response_model=ClassListResponse)
def list_classes(
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    classes = db.query(SchoolClass).order_by(SchoolClass.id.asc()).all()
    res = []
    for c in classes:
        cnt = db.query(ClassStudent).filter(ClassStudent.class_id == c.id, ClassStudent.is_active == True).count()
        res.append(ClassInfo(id=c.id, name=c.name, student_count=cnt))
    return ClassListResponse(classes=res)


# ─── E13: GET /faculty/classes/{class_id} ───────────────────────────────────

@router.get("/classes/{class_id}", response_model=ClassDetailResponse)
def get_class(
    class_id: int,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    c = db.get(SchoolClass, class_id)
    if not c:
        raise ApiError(404, "not_found", "Class not found")

    student_rows = (
        db.query(ClassStudent, User)
        .join(User, ClassStudent.student_id == User.id)
        .filter(ClassStudent.class_id == class_id, ClassStudent.is_active == True)
        .order_by(User.id.asc())
        .all()
    )
    students = [
        StudentDetail(id=u.id, name=u.name, roll_number=cs.roll_number, email=u.email)
        for cs, u in student_rows
    ]

    st_rows = (
        db.query(ClassSubjectTeacher, User)
        .join(User, ClassSubjectTeacher.teacher_id == User.id)
        .filter(ClassSubjectTeacher.class_id == class_id)
        .order_by(ClassSubjectTeacher.subject.asc())
        .all()
    )
    subject_teachers = [
        SubjectTeacherAssignment(subject=cst.subject, teacher_id=cst.teacher_id, teacher_name=u.name)
        for cst, u in st_rows
    ]

    return ClassDetailResponse(
        id=c.id,
        name=c.name,
        students=students,
        subject_teachers=subject_teachers,
    )


# ─── E28: POST /faculty/classes/{class_id}/students ─────────────────────────

@router.post("/classes/{class_id}/students", response_model=AddStudentResponse, status_code=201)
def add_student_to_class(
    class_id: int,
    req: AddStudentRequest,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    c = db.get(SchoolClass, class_id)
    if not c:
        raise ApiError(404, "not_found", "Class not found")

    if not req.name.strip():
        raise ApiError(422, "validation_error", "Student name is required")

    email = generate_unique_email(db, req.name, settings.STUDENT_DOMAIN)
    initial_password = generate_initial_password()
    pw_hash = hash_password(initial_password)

    u = User(
        name=req.name.strip(),
        email=email,
        password_hash=pw_hash,
        role="student",
        is_active=True,
    )
    db.add(u)
    db.flush()

    cs = ClassStudent(
        class_id=c.id,
        student_id=u.id,
        roll_number=req.roll_number.strip() if req.roll_number else None,
        is_active=True,
    )
    db.add(cs)
    db.commit()
    db.refresh(u)

    return AddStudentResponse(
        student=StudentSummary(id=u.id, name=u.name),
        credentials=TeacherCredentials(email=u.email, initial_password=initial_password),
    )


# ─── E29: DELETE /faculty/classes/{class_id}/students/{student_id} ──────────

@router.delete("/classes/{class_id}/students/{student_id}", status_code=204)
def remove_student_from_class(
    class_id: int,
    student_id: int,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    c = db.get(SchoolClass, class_id)
    if not c:
        raise ApiError(404, "not_found", "Class not found")

    cs = db.query(ClassStudent).filter_by(class_id=class_id, student_id=student_id).first()
    if not cs:
        raise ApiError(404, "not_found", "Student not found in this class")

    cs.is_active = False
    u = db.get(User, student_id)
    if u:
        u.is_active = False

    db.commit()
    return Response(status_code=204)


# ─── E30: PUT /faculty/classes/{class_id}/subject-teachers ───────────────────

@router.put("/classes/{class_id}/subject-teachers", response_model=list[SubjectTeacherAssignment])
def update_subject_teachers(
    class_id: int,
    req: UpdateSubjectTeachersRequest,
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    c = db.get(SchoolClass, class_id)
    if not c:
        raise ApiError(404, "not_found", "Class not found")

    # Validate all teachers exist
    for st in req.subject_teachers:
        t = db.query(Teacher).filter(Teacher.user_id == st.teacher_id).first()
        if not t:
            raise ApiError(422, "validation_error", f"Teacher ID {st.teacher_id} not found")

    # Delete existing assignments
    db.query(ClassSubjectTeacher).filter_by(class_id=class_id).delete()

    for st in req.subject_teachers:
        cst = ClassSubjectTeacher(
            class_id=class_id,
            subject=st.subject.strip(),
            teacher_id=st.teacher_id,
        )
        db.add(cst)

    db.commit()

    st_rows = (
        db.query(ClassSubjectTeacher, User)
        .join(User, ClassSubjectTeacher.teacher_id == User.id)
        .filter(ClassSubjectTeacher.class_id == class_id)
        .order_by(ClassSubjectTeacher.subject.asc())
        .all()
    )
    return [
        SubjectTeacherAssignment(subject=cst.subject, teacher_id=cst.teacher_id, teacher_name=u.name)
        for cst, u in st_rows
    ]


# ─── E14: POST /faculty/books ───────────────────────────────────────────────

@router.post("/books", response_model=BookInfo, status_code=202)
def add_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    type: str = Form(...),
    subject: str = Form(...),
    user=Depends(require_role("faculty")),
    db: Session = Depends(get_db),
):
    name = name.strip()
    b_type = type.strip()
    subject = subject.strip()

    if not name or not b_type or not subject:
        raise ApiError(422, "validation_error", "Book name, type and subject are required")

    if b_type not in ("textbook", "pyq", "question_bank"):
        raise ApiError(422, "validation_error", "Type must be textbook, pyq, or question_bank")

    if not file.filename.lower().endswith(".pdf"):
        raise ApiError(422, "validation_error", "Only PDF files are supported")

    content = file.file.read()
    if len(content) > _MAX_PDF_SIZE:
        raise ApiError(422, "validation_error", "PDF file exceeds 50 MB limit")

    existing_book = db.query(Book).filter(Book.name == name).first()
    if existing_book:
        raise ApiError(409, "conflict", "A book with this name already exists")

    settings.private_books_path.mkdir(parents=True, exist_ok=True)
    out_filename = f"book_{secrets.token_hex(6)}.pdf"
    abs_path = settings.private_books_path / out_filename
    abs_path.write_bytes(content)

    b = Book(
        name=name,
        type=b_type,
        subject=subject,
        file_path=str(abs_path),
        status="processing",
        page_count=None,
        error=None,
    )
    db.add(b)
    db.commit()
    db.refresh(b)

    background_tasks.add_task(
        _bg_ingest_book,
        b.id,
        str(abs_path),
        b.name,
        b.subject,
        b.type,
    )

    return BookInfo(
        id=b.id,
        name=b.name,
        type=b.type,
        subject=b.subject,
        status="processing",
        page_count=None,
        error=None,
    )

