from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    Book,
    ClassStudent,
    ClassSubjectTeacher,
    Homework,
    Question,
    SchoolClass,
    Teacher,
    User,
)
from app.security import generate_initial_password, hash_password


def create_minimal_pdf(file_path: Path, text: str = "Neura sample Physics PYQs") -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET"
    stream_len = len(content)

    body: list[bytes] = [b"%PDF-1.4\n"]
    offsets: dict[int, int] = {}

    def add_obj(num: int, data: str) -> None:
        offsets[num] = sum(len(x) for x in body)
        body.append(f"{num} 0 obj\n{data}\nendobj\n".encode("latin1"))

    add_obj(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_obj(
        3,
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
    )
    add_obj(4, f"<< /Length {stream_len} >>\nstream\n{content}\nendstream")
    add_obj(5, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    xref_offset = sum(len(x) for x in body)
    xref_lines = ["xref", "0 6", "0000000000 65535 f "]
    for i in range(1, 6):
        xref_lines.append(f"{offsets[i]:010d} 00000 n ")
    xref_str = "\n".join(xref_lines) + "\n"

    trailer = (
        "trailer\n"
        "<< /Size 6 /Root 1 0 R >>\n"
        "startxref\n"
        f"{xref_offset}\n"
        "%%EOF\n"
    )

    with open(file_path, "wb") as f:
        for chunk in body:
            f.write(chunk)
        f.write(xref_str.encode("latin1"))
        f.write(trailer.encode("latin1"))


def run_seed() -> list[dict[str, str]]:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    credentials: list[dict[str, str]] = []

    try:
        def upsert_user(name: str, email: str, role: str) -> tuple[User, str]:
            raw_password = generate_initial_password()
            pw_hash = hash_password(raw_password)
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(
                    name=name,
                    email=email,
                    password_hash=pw_hash,
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.flush()
            else:
                user.name = name
                user.password_hash = pw_hash
                user.role = role
                user.is_active = True
                db.flush()

            credentials.append(
                {
                    "role": role,
                    "name": name,
                    "email": email,
                    "password": raw_password,
                }
            )
            return user, raw_password

        # 1 Faculty
        faculty_email = f"faculty.admin@{settings.FACULTY_DOMAIN.lower()}"
        faculty_user, _ = upsert_user("Faculty Admin", faculty_email, "faculty")

        # 2 Teachers
        ravi_email = f"ravi.k@{settings.TEACHER_DOMAIN.lower()}"
        ravi_user, _ = upsert_user("Ravi K", ravi_email, "teacher")
        ravi_teacher = db.get(Teacher, ravi_user.id)
        if not ravi_teacher:
            db.add(Teacher(user_id=ravi_user.id, subject="Physics", phone="9876543210"))
        else:
            ravi_teacher.subject = "Physics"
            ravi_teacher.phone = "9876543210"

        meena_email = f"meena.s@{settings.TEACHER_DOMAIN.lower()}"
        meena_user, _ = upsert_user("Meena S", meena_email, "teacher")
        meena_teacher = db.get(Teacher, meena_user.id)
        if not meena_teacher:
            db.add(Teacher(user_id=meena_user.id, subject="Physics", phone=None))
        else:
            meena_teacher.subject = "Physics"
            meena_teacher.phone = None

        # 1 Class: 10-A
        class_10a = db.scalar(select(SchoolClass).where(SchoolClass.name == "10-A"))
        if not class_10a:
            class_10a = SchoolClass(name="10-A")
            db.add(class_10a)
            db.flush()

        # 5 Students
        student_specs = [
            ("Asha R", f"asha.r@{settings.STUDENT_DOMAIN.lower()}", "1"),
            ("Kiran S", f"kiran.s@{settings.STUDENT_DOMAIN.lower()}", "2"),
            ("Meera T", f"meera.t@{settings.STUDENT_DOMAIN.lower()}", "3"),
            ("Arjun P", f"arjun.p@{settings.STUDENT_DOMAIN.lower()}", "4"),
            ("Divya N", f"divya.n@{settings.STUDENT_DOMAIN.lower()}", "5"),
        ]

        for s_name, s_email, roll in student_specs:
            student_user, _ = upsert_user(s_name, s_email, "student")
            cs = db.get(ClassStudent, (class_10a.id, student_user.id))
            if not cs:
                db.add(
                    ClassStudent(
                        class_id=class_10a.id,
                        student_id=student_user.id,
                        roll_number=roll,
                        is_active=True,
                    )
                )
            else:
                cs.roll_number = roll
                cs.is_active = True

        # 1 ClassSubjectTeacher
        cst = db.get(ClassSubjectTeacher, (class_10a.id, "Physics"))
        if not cst:
            db.add(
                ClassSubjectTeacher(
                    class_id=class_10a.id,
                    subject="Physics",
                    teacher_id=ravi_user.id,
                )
            )
        else:
            cst.teacher_id = ravi_user.id

        # 1 Sample PDF
        pdf_path = settings.private_books_path / "seed_physics_pyqs.pdf"
        create_minimal_pdf(pdf_path, text="Neura sample Physics PYQs")

        # 1 Book
        book = db.scalar(select(Book).where(Book.name == "Physics Class 10 PYQs"))
        if not book:
            book = Book(
                name="Physics Class 10 PYQs",
                type="pyq",
                subject="Physics",
                file_path="seed_physics_pyqs.pdf",
                status="ready",
                page_count=1,
                error=None,
            )
            db.add(book)
            db.flush()
        else:
            book.type = "pyq"
            book.subject = "Physics"
            book.file_path = "seed_physics_pyqs.pdf"
            book.status = "ready"
            book.page_count = 1
            book.error = None
            db.flush()

        # 1 Question
        q_text = "A car accelerates uniformly from rest to 20 m/s in 5 s. Find its acceleration and the distance it covers."
        question = db.scalar(select(Question).where(Question.reference == "Exercise 1.1, Q1"))
        if not question:
            question = Question(
                text=q_text,
                topic="Kinematics",
                subject="Physics",
                source_book_id=book.id,
                reference="Exercise 1.1, Q1",
                image_path=None,
            )
            db.add(question)
            db.flush()
        else:
            question.text = q_text
            question.topic = "Kinematics"
            question.subject = "Physics"
            question.source_book_id = book.id
            question.image_path = None
            db.flush()

        # 1 Homework
        due = (datetime.now(timezone.utc) + timedelta(days=3)).replace(tzinfo=None)
        hw = db.scalar(select(Homework).where(Homework.title == "Kinematics practice"))
        if not hw:
            hw = Homework(
                class_id=class_10a.id,
                teacher_id=ravi_user.id,
                book_id=book.id,
                chapter="Kinematics",
                question_ref="Exercise 1.1, Q1",
                question_id=question.id,
                title="Kinematics practice",
                due_at=due,
            )
            db.add(hw)
        else:
            hw.class_id = class_10a.id
            hw.teacher_id = ravi_user.id
            hw.book_id = book.id
            hw.chapter = "Kinematics"
            hw.question_ref = "Exercise 1.1, Q1"
            hw.question_id = question.id
            hw.due_at = due

        db.commit()
        return credentials
    finally:
        db.close()


if __name__ == "__main__":
    creds = run_seed()
    print(f"{'Role':<10} {'Name':<16} {'Email':<35} {'Password':<10}")
    print("-" * 75)
    for c in creds:
        print(f"{c['role']:<10} {c['name']:<16} {c['email']:<35} {c['password']:<10}")
    print()
    print("Passwords are reset every time you run this script. Save this table.")

