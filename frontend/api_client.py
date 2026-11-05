# The ONLY file that talks to the backend: one function per endpoint, mock or real
from datetime import datetime, timezone
import requests
import streamlit as st
import config
from config import get_timeout


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details if details is not None else {}
        super().__init__(message)


def _headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": "Bearer " + token}
    return {}


def _raise_for_error(response):
    if response.status_code < 400:
        return
    try:
        error = response.json()["error"]
        code = error["code"]
        message = error["message"]
        details = error.get("details")
    except (ValueError, KeyError, TypeError):
        raise ApiError(
            response.status_code,
            "server_error",
            "Unexpected response from the server.",
        )
    raise ApiError(response.status_code, code, message, details)


def _request(method, path, json=None, data=None, files=None, params=None, timeout=30):
    url = config.API_BASE_URL.rstrip("/") + path
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(),
            json=json,
            data=data,
            files=files,
            params=params,
            timeout=timeout,
        )
    except requests.exceptions.ConnectionError:
        raise ApiError(
            0,
            "backend_unreachable",
            "Cannot reach the backend. Is it running on port 8000?",
        )
    except requests.exceptions.Timeout:
        raise ApiError(
            0,
            "client_timeout",
            "The request took too long. Please try again.",
        )
    _raise_for_error(response)
    if response.status_code == 204:
        return None
    return response.json()


_MOCK_USERS = {
    "asha.r@student.class.com": {
        "id": 12,
        "name": "Asha R",
        "email": "asha.r@student.class.com",
        "role": "student",
    },
    "kiran.s@student.class.com": {
        "id": 13,
        "name": "Kiran S",
        "email": "kiran.s@student.class.com",
        "role": "student",
    },
    "ravi.k@teacher.class.com": {
        "id": 3,
        "name": "Ravi K",
        "email": "ravi.k@teacher.class.com",
        "role": "teacher",
    },
    "admin@faculty.class.com": {
        "id": 1,
        "name": "Admin",
        "email": "admin@faculty.class.com",
        "role": "faculty",
    },
}


def login(email, password):
    if config.is_mock("E1"):
        key = email.strip().lower()
        if key in _MOCK_USERS and password == "mock1234":
            user = dict(_MOCK_USERS[key])
            return {
                "token": "mock-token-" + str(user["id"]),
                "token_type": "bearer",
                "user": user,
            }
        raise ApiError(401, "unauthorized", "Wrong email or password.")
    return _request("POST", "/auth/login", json={"email": email, "password": password})


def get_me():
    if config.is_mock("E2"):
        token = st.session_state.get("token")
        if not token or not token.startswith("mock-token-"):
            raise ApiError(401, "unauthorized", "Missing or invalid token.")
        try:
            user_id = int(token[len("mock-token-"):])
        except ValueError:
            raise ApiError(401, "unauthorized", "Missing or invalid token.")
        for user in _MOCK_USERS.values():
            if user["id"] == user_id:
                return dict(user)
        raise ApiError(401, "unauthorized", "Missing or invalid token.")
    return _request("GET", "/auth/me")


_MOCK_SESSIONS = {}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload_question(image=None, text=None):
    if config.is_mock("E3"):
        if image is None and (text is None or not text.strip()):
            raise ApiError(422, "validation_error", "Send an image or type the question.")
        if image is not None and image.type not in ("image/png", "image/jpeg"):
            raise ApiError(422, "validation_error", "Only png or jpg images are allowed.")
        if image is not None and len(image.getvalue()) > 5 * 1024 * 1024:
            raise ApiError(422, "validation_error", "Image is larger than 5 MB.")
        if image is not None and "bad" in image.name.lower():
            # For testing the image_unreadable error
            raise ApiError(422, "image_unreadable", "We could not read that image. Try a clearer photo.")

        session_id = 101 + len(_MOCK_SESSIONS)
        question_id = 55 + len(_MOCK_SESSIONS)

        if image is not None:
            question = {
                "id": question_id,
                "text": "Solve x^2 - 5x + 6 = 0",
                "topic": "Quadratic equations",
                "subject": "Mathematics",
                "image_url": "/files/uploads/q_" + str(question_id) + ".png",
            }
        else:
            question = {
                "id": question_id,
                "text": text.strip(),
                "topic": "Quadratic equations",
                "subject": "Mathematics",
                "image_url": None,
            }

        session = {
            "id": session_id,
            "source": "upload",
            "status": "awaiting_attempt",
            "question": question,
            "homework_id": None,
            "followup_of": None,
            "followup_index": None,
            "attempts_used": 0,
            "max_attempts": 3,
            "followup_triggered": False,
            "created_at": _now_iso(),
        }
        _MOCK_SESSIONS[session_id] = {"session": session, "attempts": []}
        return session

    files = {"image": (image.name, image.getvalue(), image.type)} if image is not None else None
    data = {"text": text} if text is not None else None
    return _request("POST", "/student/sessions/upload", data=data, files=files, timeout=get_timeout("E3"))


def get_session(session_id):
    if config.is_mock("E4"):
        if session_id not in _MOCK_SESSIONS:
            raise ApiError(404, "not_found", "Session not found.")
        entry = _MOCK_SESSIONS[session_id]
        return {"session": dict(entry["session"]), "attempts": list(entry["attempts"])}
    return _request("GET", "/student/sessions/" + str(session_id))


def submit_attempt(session_id, image):
    if config.is_mock("E5"):
        if session_id not in _MOCK_SESSIONS:
            raise ApiError(404, "not_found", "Session not found.")
        entry = _MOCK_SESSIONS[session_id]
        session = entry["session"]
        if session["status"] != "awaiting_attempt":
            raise ApiError(409, "conflict", "This session is already closed.")
        if image is None:
            raise ApiError(422, "validation_error", "Upload a photo of your solution.")
        if image.type not in ("image/png", "image/jpeg"):
            raise ApiError(422, "validation_error", "Only png or jpg images are allowed.")
        if len(image.getvalue()) > 5 * 1024 * 1024:
            raise ApiError(422, "validation_error", "Image is larger than 5 MB.")

        # Mock outcome is chosen by the file name (lowercase):
        # "unclear" -> unclear photo; "correct" -> correct answer; anything else -> wrong answer.
        name_lower = image.name.lower()
        attempt_id = 7 + sum(len(e["attempts"]) for e in _MOCK_SESSIONS.values())
        attempt_image_url = "/files/attempts/a_" + str(attempt_id) + ".png"
        used = session["attempts_used"]
        is_followup = session["followup_of"] is not None
        submitted_at = _now_iso()

        if "unclear" in name_lower:
            return {
                "attempt": {
                    "id": attempt_id,
                    "trial_number": used + 1,
                    "image_url": attempt_image_url,
                    "submitted_at": submitted_at,
                },
                "verdict": "unclear",
                "stage": "retry",
                "message": "That photo is hard to read. Please retake it and upload again.",
                "diagnosis": [],
                "topics_and_formulae": None,
                "simplified_question": None,
                "full_solution": None,
                "efficient_method": None,
                "attempts_used": used,
                "session_status": "awaiting_attempt",
                "followup_triggered": session["followup_triggered"],
            }

        n = used + 1
        session["attempts_used"] = n

        if "correct" in name_lower:
            session["status"] = "solved"
            session["followup_triggered"] = n == 3 and not is_followup
            verdict = "correct"
            stage = "solved"
            message = "Well done! That is correct."
            diagnosis = []
            topics_and_formulae = None
            simplified_question = None
            full_solution = None
            efficient_method = (
                {
                    "title": "Factorise directly",
                    "steps": ["(x - 2)(x - 3) = 0", "x = 2 or x = 3"],
                }
                if n == 1
                else None
            )
            session_status = "solved"
        else:
            diagnoses = [
                {
                    "step_number": 2,
                    "student_wrote": "x^2 - 5x = -6 -> x(x - 5) = 6",
                    "expected": "x(x - 5) = -6",
                    "mistake_type": "sign_error",
                    "description": "The sign flipped when moving a term across the equals sign.",
                },
                {
                    "step_number": 3,
                    "student_wrote": "x = 5 or x = 6",
                    "expected": "x = 2 or x = 3",
                    "mistake_type": "formula_misuse",
                    "description": "The sum and product of roots were mixed up.",
                },
                {
                    "step_number": 1,
                    "student_wrote": "x^2 - 5x + 6 = 0 -> x = -6",
                    "expected": "Split the middle term first",
                    "mistake_type": "concept_gap",
                    "description": "The equation was treated as linear instead of quadratic.",
                },
            ]
            verdict = "incorrect"
            diagnosis = [diagnoses[n - 1]]
            topics_and_formulae = None
            simplified_question = None
            full_solution = None
            efficient_method = None

            if n == 1:
                stage = "hints"
                message = "You are close. Check step 2."
                if session["source"] in ("pyq", "followup_pyq"):
                    topics_and_formulae = {
                        "topics": ["Factorisation", "Quadratic equations"],
                        "formulae": [
                            "ax^2 + bx + c = 0",
                            "x = (-b ± sqrt(b^2 - 4ac)) / 2a",
                        ],
                    }
                session_status = "awaiting_attempt"
            elif n == 2:
                stage = "simplified"
                message = "Let's break it down into a simpler problem."
                simplified_question = {
                    "text": "Find two numbers that multiply to 6 and add up to -5, then use them to split the middle term.",
                    "gif": {"status": "pending", "url": None},
                }
                session_status = "awaiting_attempt"
            else:
                stage = "revealed"
                message = "Here is the full solution."
                session["status"] = "revealed"
                session["followup_triggered"] = not is_followup
                full_solution = {
                    "steps": [
                        {"step_number": 1, "text": "Split the middle term: x^2 - 2x - 3x + 6 = 0"},
                        {"step_number": 2, "text": "Group: x(x - 2) - 3(x - 2) = 0"},
                        {"step_number": 3, "text": "Factor: (x - 2)(x - 3) = 0"},
                    ],
                    "final_answer": "x = 2 or x = 3",
                    "shortcuts": [
                        {"title": "Sum and product", "text": "Roots add to 5 and multiply to 6, so 2 and 3."}
                    ],
                    "efficient_method": {
                        "title": "Factorise directly",
                        "steps": ["(x - 2)(x - 3) = 0", "x = 2 or x = 3"],
                    },
                }
                session_status = "revealed"

        entry["attempts"].append(
            {
                "id": attempt_id,
                "trial_number": n,
                "image_url": attempt_image_url,
                "verdict": verdict,
                "stage": stage,
                "submitted_at": submitted_at,
            }
        )

        return {
            "attempt": {
                "id": attempt_id,
                "trial_number": n,
                "image_url": attempt_image_url,
                "submitted_at": submitted_at,
            },
            "verdict": verdict,
            "stage": stage,
            "message": message,
            "diagnosis": diagnosis,
            "topics_and_formulae": topics_and_formulae,
            "simplified_question": simplified_question,
            "full_solution": full_solution,
            "efficient_method": efficient_method,
            "attempts_used": n,
            "session_status": session_status,
            "followup_triggered": session["followup_triggered"],
        }

    files = {"image": (image.name, image.getvalue(), image.type)}
    return _request(
        "POST",
        "/student/sessions/" + str(session_id) + "/attempts",
        files=files,
        timeout=get_timeout("E5"),
    )


_MOCK_GIF_POLLS = {}


def get_gif(session_id):
    if config.is_mock("E6"):
        count = _MOCK_GIF_POLLS.get(session_id, 0) + 1
        _MOCK_GIF_POLLS[session_id] = count
        if count <= 2:
            return {"status": "pending", "url": None, "error": None}
        return {"status": "ready", "url": "/files/gifs/q_55.gif", "error": None}
    return _request("GET", f"/student/sessions/{session_id}/gif", timeout=get_timeout("E6"))


_MOCK_FOLLOWUPS = {}


def get_followups(session_id):
    if config.is_mock("E7"):
        if session_id not in _MOCK_SESSIONS:
            raise ApiError(404, "not_found", "Session not found.")
        if session_id in _MOCK_FOLLOWUPS:
            return {
                "followups": [
                    dict(_MOCK_SESSIONS[fid]["session"])
                    for fid in _MOCK_FOLLOWUPS[session_id]
                ]
            }
        specs = [
            ("followup_pyq", "Solve x^2 - 7x + 12 = 0"),
            ("followup_pyq", "Solve x^2 + 2x - 15 = 0"),
            ("followup_generated", "Solve 2x^2 - 5x + 2 = 0"),
        ]
        followups = []
        followup_ids = []
        for idx, (source, text) in enumerate(specs, start=1):
            f_session_id = 101 + len(_MOCK_SESSIONS)
            f_question_id = 55 + len(_MOCK_SESSIONS)
            question = {
                "id": f_question_id,
                "text": text,
                "topic": "Quadratic equations",
                "subject": "Mathematics",
                "image_url": None,
            }
            f_session = {
                "id": f_session_id,
                "source": source,
                "status": "awaiting_attempt",
                "question": question,
                "homework_id": None,
                "followup_of": session_id,
                "followup_index": idx,
                "attempts_used": 0,
                "max_attempts": 3,
                "followup_triggered": False,
                "created_at": _now_iso(),
            }
            _MOCK_SESSIONS[f_session_id] = {"session": f_session, "attempts": []}
            followup_ids.append(f_session_id)
            followups.append(dict(f_session))
        _MOCK_FOLLOWUPS[session_id] = followup_ids
        return {"followups": followups}
    return _request("POST", f"/student/sessions/{session_id}/followups", timeout=get_timeout("E7"))


def skip_session(session_id):
    if config.is_mock("E8"):
        if session_id not in _MOCK_SESSIONS:
            raise ApiError(404, "not_found", "Session not found.")
        session = _MOCK_SESSIONS[session_id]["session"]
        if session.get("followup_of") is None:
            raise ApiError(403, "forbidden", "Only follow-up questions can be skipped.")
        session["status"] = "skipped"
        return dict(session)
    return _request("POST", f"/student/sessions/{session_id}/skip", timeout=get_timeout("E8"))


# ---------------------------------------------------------------------------
# Mock state for Faculty, Books, Teacher, and Student endpoints (E9 - E30)
# ---------------------------------------------------------------------------

_MOCK_TEACHERS = [
    {
        "id": 3,
        "name": "Ravi K",
        "subject": "Mathematics",
        "email": "ravi.k@teacher.class.com",
        "phone": "9876543210",
    },
    {
        "id": 5,
        "name": "Meena P",
        "subject": "Physics",
        "email": "meena.p@teacher.class.com",
        "phone": "9876501234",
    },
]

_MOCK_CLASSES = {
    2: {
        "id": 2,
        "name": "10-A",
        "students": [
            {
                "id": 12,
                "name": "Asha R",
                "roll_number": "1",
                "email": "asha.r@student.class.com",
            },
            {
                "id": 13,
                "name": "Kiran S",
                "roll_number": "2",
                "email": "kiran.s@student.class.com",
            },
        ],
        "subject_teachers": [
            {"subject": "Mathematics", "teacher_id": 3, "teacher_name": "Ravi K"},
            {"subject": "Physics", "teacher_id": 5, "teacher_name": "Meena P"},
        ],
    }
}

_MOCK_BOOKS = {
    4: {
        "id": 4,
        "name": "Maths Class 10 PYQs",
        "type": "pyq",
        "subject": "Mathematics",
        "status": "ready",
        "page_count": 120,
        "error": None,
    },
    5: {
        "id": 5,
        "name": "NCERT Mathematics Class 10",
        "type": "textbook",
        "subject": "Mathematics",
        "status": "ready",
        "page_count": 210,
        "error": None,
    },
    6: {
        "id": 6,
        "name": "Physics Formula & Question Bank",
        "type": "question_bank",
        "subject": "Physics",
        "status": "ready",
        "page_count": 95,
        "error": None,
    },
}

_MOCK_HOMEWORK = {
    9: {
        "id": 9,
        "class_id": 2,
        "title": "Quadratics practice",
        "subject": "Mathematics",
        "teacher_name": "Ravi K",
        "book": {"id": 4, "name": "Maths Class 10 PYQs"},
        "chapter": "Quadratic Equations",
        "question_ref": "Exercise 4.2, Q3",
        "question_text": "Solve x^2 - 5x + 6 = 0",
        "topic": "Quadratic equations",
        "assigned_at": "2026-11-18T08:00:00Z",
        "due_at": "2026-11-22T18:00:00Z",
        "student_sessions": {},
    },
    10: {
        "id": 10,
        "class_id": 2,
        "title": "Roots and discriminant",
        "subject": "Mathematics",
        "teacher_name": "Ravi K",
        "book": {"id": 5, "name": "NCERT Mathematics Class 10"},
        "chapter": "Quadratic Equations",
        "question_ref": "Exercise 4.3, Q1",
        "question_text": "Find the roots of 2x^2 - 7x + 3 = 0 by factorisation.",
        "topic": "Quadratic equations",
        "assigned_at": "2026-11-19T09:00:00Z",
        "due_at": "2026-11-25T18:00:00Z",
        "student_sessions": {},
    },
}


def _slug_email(name, domain, existing_emails):
    parts = [p.lower() for p in name.strip().split() if p]
    base = ".".join(parts) if parts else "user"
    base = "".join(c for c in base if c.isalnum() or c == ".").strip(".") or "user"
    candidate = f"{base}@{domain}"
    counter = 2
    while candidate in existing_emails:
        candidate = f"{base}{counter}@{domain}"
        counter += 1
    return candidate


# E9: POST /faculty/teachers
def create_teacher(name, subject, phone=None):
    if config.is_mock("E9"):
        if not name or not name.strip():
            raise ApiError(422, "validation_error", "Teacher name is required.")
        if subject not in config.SUBJECTS:
            raise ApiError(422, "validation_error", "Invalid subject.")
        new_id = max([t["id"] for t in _MOCK_TEACHERS] + list( u["id"] for u in _MOCK_USERS.values() )) + 1
        existing_emails = set(_MOCK_USERS.keys()) | {t["email"] for t in _MOCK_TEACHERS}
        email = _slug_email(name, "teacher.class.com", existing_emails)
        teacher = {
            "id": new_id,
            "name": name.strip(),
            "subject": subject,
            "email": email,
            "phone": phone.strip() if phone else None,
        }
        _MOCK_TEACHERS.append(teacher)
        _MOCK_USERS[email] = {
            "id": new_id,
            "name": teacher["name"],
            "email": email,
            "role": "teacher",
        }
        return {
            "teacher": {"id": teacher["id"], "name": teacher["name"], "subject": teacher["subject"]},
            "credentials": {"email": email, "initial_password": "mock1234"},
        }
    payload = {"name": name, "subject": subject}
    if phone:
        payload["phone"] = phone
    return _request("POST", "/faculty/teachers", json=payload, timeout=get_timeout("E9"))


# E10: GET /faculty/teachers
def list_teachers():
    if config.is_mock("E10"):
        return {
            "teachers": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "subject": t["subject"],
                    "email": t["email"],
                }
                for t in _MOCK_TEACHERS
            ]
        }
    return _request("GET", "/faculty/teachers", timeout=get_timeout("E10"))


# E11: POST /faculty/classes
def create_class(name, students, subject_teachers):
    if config.is_mock("E11"):
        if not name or not name.strip():
            raise ApiError(422, "validation_error", "Class name is required.")
        clean_name = name.strip()
        for c in _MOCK_CLASSES.values():
            if c["name"].lower() == clean_name.lower():
                raise ApiError(409, "conflict", "A class with this name already exists.")
        valid_students = [s for s in (students or []) if s.get("name", "").strip()]
        if not valid_students:
            raise ApiError(422, "validation_error", "At least one student is required.")

        teacher_map = {t["id"]: t for t in _MOCK_TEACHERS}
        resolved_st = []
        for st_item in subject_teachers or []:
            subj = st_item.get("subject")
            tid = st_item.get("teacher_id")
            if subj not in config.SUBJECTS:
                raise ApiError(422, "validation_error", f"Invalid subject: {subj}")
            if tid not in teacher_map:
                raise ApiError(422, "validation_error", f"Unknown teacher id: {tid}")
            resolved_st.append(
                {
                    "subject": subj,
                    "teacher_id": tid,
                    "teacher_name": teacher_map[tid]["name"],
                }
            )

        class_id = max(list(_MOCK_CLASSES.keys()) + [1]) + 1
        next_uid = max(
            [u["id"] for u in _MOCK_USERS.values()]
            + [t["id"] for t in _MOCK_TEACHERS]
            + [s["id"] for c in _MOCK_CLASSES.values() for s in c["students"]]
            + [20]
        ) + 1
        existing_emails = set(_MOCK_USERS.keys())
        class_students = []
        credentials = []
        for idx, s in enumerate(valid_students, start=1):
            sid = next_uid
            next_uid += 1
            sname = s["name"].strip()
            roll = str(s.get("roll_number") or idx).strip()
            email = _slug_email(sname, "student.class.com", existing_emails)
            existing_emails.add(email)
            class_students.append(
                {"id": sid, "name": sname, "roll_number": roll, "email": email}
            )
            _MOCK_USERS[email] = {
                "id": sid,
                "name": sname,
                "email": email,
                "role": "student",
            }
            credentials.append(
                {
                    "student_id": sid,
                    "name": sname,
                    "email": email,
                    "initial_password": "mock1234",
                }
            )

        _MOCK_CLASSES[class_id] = {
            "id": class_id,
            "name": clean_name,
            "students": class_students,
            "subject_teachers": resolved_st,
        }
        return {
            "class": {
                "id": class_id,
                "name": clean_name,
                "student_count": len(class_students),
            },
            "credentials": credentials,
        }
    return _request(
        "POST",
        "/faculty/classes",
        json={"name": name, "students": students, "subject_teachers": subject_teachers},
        timeout=get_timeout("E11"),
    )


# E12: GET /faculty/classes
def list_faculty_classes():
    if config.is_mock("E12"):
        return {
            "classes": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "student_count": len(c["students"]),
                }
                for c in _MOCK_CLASSES.values()
            ]
        }
    return _request("GET", "/faculty/classes", timeout=get_timeout("E12"))


# E13: GET /faculty/classes/{class_id}
def get_class_detail(class_id):
    if config.is_mock("E13"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        c = _MOCK_CLASSES[class_id]
        return {
            "id": c["id"],
            "name": c["name"],
            "students": [dict(s) for s in c["students"]],
            "subject_teachers": [dict(st_item) for st_item in c["subject_teachers"]],
        }
    return _request("GET", f"/faculty/classes/{class_id}", timeout=get_timeout("E13"))


# E14: POST /faculty/books
def upload_book(file, name, book_type, subject):
    if config.is_mock("E14"):
        if file is None:
            raise ApiError(422, "validation_error", "Please select a PDF file.")
        if not name or not name.strip():
            raise ApiError(422, "validation_error", "Book name is required.")
        if book_type not in ("textbook", "pyq", "question_bank"):
            raise ApiError(422, "validation_error", "Invalid book type.")
        if subject not in config.SUBJECTS:
            raise ApiError(422, "validation_error", "Invalid subject.")
        fname = getattr(file, "name", "").lower()
        if not fname.endswith(".pdf"):
            raise ApiError(422, "validation_error", "Only PDF files are allowed.")
        if len(file.getvalue()) > 50 * 1024 * 1024:
            raise ApiError(422, "validation_error", "PDF is larger than 50 MB.")
        clean_name = name.strip()
        for b in _MOCK_BOOKS.values():
            if b["name"].lower() == clean_name.lower():
                raise ApiError(409, "conflict", "A book with this name already exists.")
        book_id = max(list(_MOCK_BOOKS.keys()) + [3]) + 1
        book = {
            "id": book_id,
            "name": clean_name,
            "type": book_type,
            "subject": subject,
            "status": "ready",
            "page_count": 80,
            "error": None,
        }
        _MOCK_BOOKS[book_id] = book
        return {
            "id": book["id"],
            "name": book["name"],
            "type": book["type"],
            "subject": book["subject"],
            "status": book["status"],
        }
    files = {"file": (file.name, file.getvalue(), "application/pdf")}
    data = {"name": name, "type": book_type, "subject": subject}
    return _request("POST", "/faculty/books", data=data, files=files, timeout=get_timeout("E14"))


# E15: GET /books
def list_books(q=None, book_type=None, subject=None):
    if config.is_mock("E15"):
        user = st.session_state.get("user") or {}
        role = user.get("role")
        teacher_subjects = None
        if role == "teacher":
            teacher_subjects = {
                t["subject"] for t in _MOCK_TEACHERS if t["id"] == user.get("id")
            }
            if not teacher_subjects:
                teacher_subjects = {"Mathematics"}

        items = []
        for b in _MOCK_BOOKS.values():
            if role == "student" and b["status"] != "ready":
                continue
            if teacher_subjects is not None and b["subject"] not in teacher_subjects:
                continue
            if q and q.strip().lower() not in b["name"].lower():
                continue
            if book_type and b["type"] != book_type:
                continue
            if subject and b["subject"] != subject:
                continue
            items.append(
                {
                    "id": b["id"],
                    "name": b["name"],
                    "type": b["type"],
                    "subject": b["subject"],
                    "status": b["status"],
                    "page_count": b["page_count"],
                }
            )
        return {"books": items}
    params = {}
    if q:
        params["q"] = q
    if book_type:
        params["type"] = book_type
    if subject:
        params["subject"] = subject
    return _request("GET", "/books", params=params or None, timeout=get_timeout("E15"))


# E16: GET /books/{book_id}
def get_book(book_id):
    if config.is_mock("E16"):
        if book_id not in _MOCK_BOOKS:
            raise ApiError(404, "not_found", "Book not found.")
        return dict(_MOCK_BOOKS[book_id])
    return _request("GET", f"/books/{book_id}", timeout=get_timeout("E16"))


# E17: GET /books/{book_id}/file
def get_book_file_url(book_id):
    return config.API_BASE_URL.rstrip("/") + f"/books/{book_id}/file"


# E18: GET /teacher/classes
def list_teacher_classes():
    if config.is_mock("E18"):
        user = st.session_state.get("user") or {}
        tid = user.get("id", 3)
        rows = []
        for c in _MOCK_CLASSES.values():
            for st_item in c["subject_teachers"]:
                if st_item["teacher_id"] == tid:
                    rows.append(
                        {
                            "class_id": c["id"],
                            "name": c["name"],
                            "subject": st_item["subject"],
                            "student_count": len(c["students"]),
                        }
                    )
        if not rows:
            for c in _MOCK_CLASSES.values():
                rows.append(
                    {
                        "class_id": c["id"],
                        "name": c["name"],
                        "subject": "Mathematics",
                        "student_count": len(c["students"]),
                    }
                )
        return {"classes": rows}
    return _request("GET", "/teacher/classes", timeout=get_timeout("E18"))


# E19: POST /teacher/classes/{class_id}/homework
def create_homework(class_id, book_id, chapter, question_ref, title=None, due_at=None):
    if config.is_mock("E19"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        if book_id not in _MOCK_BOOKS:
            raise ApiError(404, "not_found", "Book not found.")
        book = _MOCK_BOOKS[book_id]
        if book["status"] != "ready":
            raise ApiError(409, "conflict", "Book is still processing.")
        if not question_ref or not question_ref.strip():
            raise ApiError(422, "validation_error", "Question reference is required.")
        if "notfound" in question_ref.lower():
            raise ApiError(404, "question_not_found", "Could not find that question in the book.")

        hw_id = max(list(_MOCK_HOMEWORK.keys()) + [8]) + 1
        clean_chapter = (chapter or "").strip() or "Quadratic Equations"
        clean_ref = question_ref.strip()
        clean_title = (title or "").strip() or f"{clean_chapter} - {clean_ref}"
        user = st.session_state.get("user") or {}
        hw = {
            "id": hw_id,
            "class_id": class_id,
            "title": clean_title,
            "subject": book["subject"],
            "teacher_name": user.get("name", "Ravi K"),
            "book": {"id": book["id"], "name": book["name"]},
            "chapter": clean_chapter,
            "question_ref": clean_ref,
            "question_text": f"Solve x^2 - 5x + 6 = 0 (from {book['name']}, {clean_ref})",
            "topic": clean_chapter.capitalize(),
            "assigned_at": _now_iso(),
            "due_at": due_at,
            "student_sessions": {},
        }
        _MOCK_HOMEWORK[hw_id] = hw
        return {
            "id": hw["id"],
            "class_id": hw["class_id"],
            "title": hw["title"],
            "book": hw["book"],
            "chapter": hw["chapter"],
            "question_ref": hw["question_ref"],
            "question_text": hw["question_text"],
            "topic": hw["topic"],
            "assigned_at": hw["assigned_at"],
            "due_at": hw["due_at"],
        }
    payload = {
        "book_id": book_id,
        "chapter": chapter,
        "question_ref": question_ref,
        "title": title,
        "due_at": due_at,
    }
    return _request(
        "POST",
        f"/teacher/classes/{class_id}/homework",
        json=payload,
        timeout=get_timeout("E19"),
    )


def _is_hw_completed_for_student(hw, student_id):
    sess_id = hw.get("student_sessions", {}).get(student_id)
    if sess_id and sess_id in _MOCK_SESSIONS:
        status = _MOCK_SESSIONS[sess_id]["session"]["status"]
        if status in ("solved", "revealed"):
            return True, _MOCK_SESSIONS[sess_id]["session"]["created_at"]
    if hw["id"] == 9 and student_id == 12:
        return True, "2026-11-19T10:00:00Z"
    return False, None


# E20: GET /teacher/classes/{class_id}/homework
def list_class_homework(class_id):
    if config.is_mock("E20"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        students = _MOCK_CLASSES[class_id]["students"]
        items = []
        for hw in sorted(_MOCK_HOMEWORK.values(), key=lambda x: x["id"], reverse=True):
            if hw["class_id"] != class_id:
                continue
            completed_count = sum(
                1 for s in students if _is_hw_completed_for_student(hw, s["id"])[0]
            )
            items.append(
                {
                    "id": hw["id"],
                    "title": hw["title"],
                    "topic": hw["topic"],
                    "assigned_at": hw["assigned_at"],
                    "due_at": hw["due_at"],
                    "completed": completed_count,
                    "total": len(students),
                }
            )
        return {"homework": items}
    return _request("GET", f"/teacher/classes/{class_id}/homework", timeout=get_timeout("E20"))


# E21: GET /teacher/homework/{homework_id}
def get_homework_detail(homework_id):
    if config.is_mock("E21"):
        if homework_id not in _MOCK_HOMEWORK:
            raise ApiError(404, "not_found", "Homework not found.")
        hw = _MOCK_HOMEWORK[homework_id]
        cls = _MOCK_CLASSES.get(hw["class_id"], {"students": []})
        student_rows = []
        completed_count = 0
        for s in cls["students"]:
            done, done_at = _is_hw_completed_for_student(hw, s["id"])
            if done:
                completed_count += 1
            student_rows.append(
                {
                    "student_id": s["id"],
                    "name": s["name"],
                    "completed": done,
                    "completed_at": done_at,
                }
            )
        return {
            "id": hw["id"],
            "title": hw["title"],
            "question_text": hw["question_text"],
            "topic": hw["topic"],
            "due_at": hw["due_at"],
            "completion": {
                "completed": completed_count,
                "total": len(cls["students"]),
                "students": student_rows,
            },
        }
    return _request("GET", f"/teacher/homework/{homework_id}", timeout=get_timeout("E21"))


# E22: GET /student/homework
def list_student_homework():
    if config.is_mock("E22"):
        user = st.session_state.get("user") or {}
        sid = user.get("id", 12)
        items = []
        for hw in _MOCK_HOMEWORK.values():
            sess_id = hw.get("student_sessions", {}).get(sid)
            if sess_id and sess_id in _MOCK_SESSIONS:
                s_status = _MOCK_SESSIONS[sess_id]["session"]["status"]
                status = "completed" if s_status in ("solved", "revealed") else "in_progress"
            else:
                status = "not_started"
                sess_id = None
            items.append(
                {
                    "homework_id": hw["id"],
                    "title": hw["title"],
                    "subject": hw["subject"],
                    "topic": hw["topic"],
                    "teacher_name": hw["teacher_name"],
                    "assigned_at": hw["assigned_at"],
                    "due_at": hw["due_at"],
                    "status": status,
                    "session_id": sess_id,
                }
            )
        items.sort(key=lambda x: (x["due_at"] is None, x["due_at"] or ""))
        return {"homework": items}
    return _request("GET", "/student/homework", timeout=get_timeout("E22"))


# E23: POST /student/sessions/homework
def start_homework_session(homework_id):
    if config.is_mock("E23"):
        if homework_id not in _MOCK_HOMEWORK:
            raise ApiError(404, "not_found", "Homework not found.")
        hw = _MOCK_HOMEWORK[homework_id]
        user = st.session_state.get("user") or {}
        sid = user.get("id", 12)
        existing_sid = hw["student_sessions"].get(sid)
        if existing_sid and existing_sid in _MOCK_SESSIONS:
            return dict(_MOCK_SESSIONS[existing_sid]["session"])

        session_id = 101 + len(_MOCK_SESSIONS)
        question_id = 55 + len(_MOCK_SESSIONS)
        question = {
            "id": question_id,
            "text": hw["question_text"],
            "topic": hw["topic"],
            "subject": hw["subject"],
            "image_url": None,
        }
        session = {
            "id": session_id,
            "source": "homework",
            "status": "awaiting_attempt",
            "question": question,
            "homework_id": homework_id,
            "followup_of": None,
            "followup_index": None,
            "attempts_used": 0,
            "max_attempts": 3,
            "followup_triggered": False,
            "created_at": _now_iso(),
        }
        _MOCK_SESSIONS[session_id] = {"session": session, "attempts": []}
        hw["student_sessions"][sid] = session_id
        return dict(session)
    return _request(
        "POST",
        "/student/sessions/homework",
        json={"homework_id": homework_id},
        timeout=get_timeout("E23"),
    )


# E24: POST /student/sessions/pyq
def start_pyq_session(book_id, question_ref, chapter=None):
    if config.is_mock("E24"):
        if book_id not in _MOCK_BOOKS:
            raise ApiError(404, "not_found", "Book not found.")
        book = _MOCK_BOOKS[book_id]
        if book["status"] != "ready":
            raise ApiError(409, "conflict", "Book is not ready yet.")
        if not question_ref or not question_ref.strip():
            raise ApiError(422, "validation_error", "Enter a question reference.")
        if "notfound" in question_ref.lower():
            raise ApiError(404, "question_not_found", "Question not found in the selected book.")

        session_id = 101 + len(_MOCK_SESSIONS)
        question_id = 55 + len(_MOCK_SESSIONS)
        clean_topic = (chapter or "").strip().capitalize() or "Quadratic equations"
        question = {
            "id": question_id,
            "text": f"Solve x^2 - 5x + 6 = 0 ({book['name']} · {question_ref.strip()})",
            "topic": clean_topic,
            "subject": book["subject"],
            "image_url": None,
        }
        session = {
            "id": session_id,
            "source": "pyq",
            "status": "awaiting_attempt",
            "question": question,
            "homework_id": None,
            "followup_of": None,
            "followup_index": None,
            "attempts_used": 0,
            "max_attempts": 3,
            "followup_triggered": False,
            "created_at": _now_iso(),
        }
        _MOCK_SESSIONS[session_id] = {"session": session, "attempts": []}
        return dict(session)
    payload = {"book_id": book_id, "question_ref": question_ref}
    if chapter:
        payload["chapter"] = chapter
    return _request("POST", "/student/sessions/pyq", json=payload, timeout=get_timeout("E24"))


# E25: GET /student/stats
def get_student_stats():
    if config.is_mock("E25"):
        extra_sessions = len(_MOCK_SESSIONS)
        extra_solved = sum(
            1 for e in _MOCK_SESSIONS.values() if e["session"]["status"] == "solved"
        )
        return {
            "totals": {
                "sessions": 24 + extra_sessions,
                "solved": 20 + extra_solved,
                "avg_attempts": 1.8,
            },
            "topics": [
                {
                    "topic": "Quadratic equations",
                    "subject": "Mathematics",
                    "status": "weak",
                    "sessions": 5 + extra_sessions,
                    "mistake_counts": {
                        "sign_error": 3,
                        "formula_misuse": 1,
                        "unit_slip": 0,
                        "concept_gap": 0,
                    },
                },
                {
                    "topic": "Linear equations",
                    "subject": "Mathematics",
                    "status": "strong",
                    "sessions": 8,
                    "mistake_counts": {
                        "sign_error": 1,
                        "formula_misuse": 0,
                        "unit_slip": 0,
                        "concept_gap": 0,
                    },
                },
                {
                    "topic": "Kinematics",
                    "subject": "Physics",
                    "status": "learning",
                    "sessions": 6,
                    "mistake_counts": {
                        "sign_error": 0,
                        "formula_misuse": 1,
                        "unit_slip": 2,
                        "concept_gap": 1,
                    },
                },
            ],
            "mistake_types": [
                {"type": "sign_error", "count": 4},
                {"type": "formula_misuse", "count": 2},
                {"type": "unit_slip", "count": 2},
                {"type": "concept_gap", "count": 1},
            ],
        }
    return _request("GET", "/student/stats", timeout=get_timeout("E25"))


# E26: GET /teacher/classes/{class_id}/status
def get_class_status(class_id):
    if config.is_mock("E26"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        cls = _MOCK_CLASSES[class_id]
        total_students = len(cls["students"])
        recent = []
        for sid, entry in sorted(_MOCK_SESSIONS.items(), reverse=True):
            s = entry["session"]
            recent.append(
                {
                    "student": {"id": 12, "name": "Asha R"},
                    "question_text": s["question"]["text"],
                    "topic": s["question"]["topic"],
                    "source": s["source"],
                    "attempts_used": s["attempts_used"],
                    "status": s["status"],
                    "last_mistake_type": "sign_error" if s["attempts_used"] > 0 else None,
                    "at": s["created_at"],
                }
            )
        recent.extend(
            [
                {
                    "student": {"id": 12, "name": "Asha R"},
                    "question_text": "Solve x^2 - 5x + 6 = 0",
                    "topic": "Quadratic equations",
                    "source": "upload",
                    "attempts_used": 3,
                    "status": "revealed",
                    "last_mistake_type": "sign_error",
                    "at": "2026-11-19T10:00:00Z",
                },
                {
                    "student": {"id": 13, "name": "Kiran S"},
                    "question_text": "Find the roots of 2x^2 - 7x + 3 = 0",
                    "topic": "Quadratic equations",
                    "source": "homework",
                    "attempts_used": 2,
                    "status": "solved",
                    "last_mistake_type": "formula_misuse",
                    "at": "2026-11-19T09:15:00Z",
                },
            ]
        )
        return {
            "class_id": class_id,
            "subject": "Mathematics",
            "struggling_topics": [
                {
                    "topic": "Quadratic equations",
                    "struggling_students": min(2, total_students),
                    "total_students": total_students,
                    "top_mistake_type": "sign_error",
                },
                {
                    "topic": "Trigonometric identities",
                    "struggling_students": min(1, total_students),
                    "total_students": total_students,
                    "top_mistake_type": "formula_misuse",
                },
            ],
            "recent_queries": recent[:50],
        }
    return _request("GET", f"/teacher/classes/{class_id}/status", timeout=get_timeout("E26"))


# E27: GET /student/sessions/{session_id}/videos
def get_session_videos(session_id):
    if config.is_mock("E27"):
        if session_id not in _MOCK_SESSIONS:
            raise ApiError(404, "not_found", "Session not found.")
        q = _MOCK_SESSIONS[session_id]["session"]["question"]
        return {
            "videos": [
                {
                    "title": f"{q['topic']} - Complete Concept Explainer",
                    "url": "https://www.youtube.com/watch?v=IlNAJl36-10",
                    "channel": "Khan Academy",
                    "kind": "topic_explainer",
                },
                {
                    "title": f"Step-by-step: {q['text']}",
                    "url": "https://www.youtube.com/watch?v=qeByhTF8WEw",
                    "channel": "Math Tutorials",
                    "kind": "question_solution",
                },
            ]
        }
    return _request("GET", f"/student/sessions/{session_id}/videos", timeout=get_timeout("E27"))


# E28: POST /faculty/classes/{class_id}/students
def add_class_student(class_id, name, roll_number=None):
    if config.is_mock("E28"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        if not name or not name.strip():
            raise ApiError(422, "validation_error", "Student name is required.")
        cls = _MOCK_CLASSES[class_id]
        next_uid = max(
            [u["id"] for u in _MOCK_USERS.values()]
            + [s["id"] for c in _MOCK_CLASSES.values() for s in c["students"]]
            + [20]
        ) + 1
        existing_emails = set(_MOCK_USERS.keys())
        sname = name.strip()
        email = _slug_email(sname, "student.class.com", existing_emails)
        roll = str(roll_number).strip() if roll_number else str(len(cls["students"]) + 1)
        student_row = {"id": next_uid, "name": sname, "roll_number": roll, "email": email}
        cls["students"].append(student_row)
        _MOCK_USERS[email] = {
            "id": next_uid,
            "name": sname,
            "email": email,
            "role": "student",
        }
        return {
            "student": {"id": next_uid, "name": sname},
            "credentials": {"email": email, "initial_password": "mock1234"},
        }
    payload = {"name": name}
    if roll_number:
        payload["roll_number"] = roll_number
    return _request(
        "POST",
        f"/faculty/classes/{class_id}/students",
        json=payload,
        timeout=get_timeout("E28"),
    )


# E29: DELETE /faculty/classes/{class_id}/students/{student_id}
def remove_class_student(class_id, student_id):
    if config.is_mock("E29"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        cls = _MOCK_CLASSES[class_id]
        before = len(cls["students"])
        cls["students"] = [s for s in cls["students"] if s["id"] != student_id]
        if len(cls["students"]) == before:
            raise ApiError(404, "not_found", "Student not found in this class.")
        return None
    return _request(
        "DELETE",
        f"/faculty/classes/{class_id}/students/{student_id}",
        timeout=get_timeout("E29"),
    )


# E30: PUT /faculty/classes/{class_id}/subject-teachers
def update_class_subject_teachers(class_id, subject_teachers):
    if config.is_mock("E30"):
        if class_id not in _MOCK_CLASSES:
            raise ApiError(404, "not_found", "Class not found.")
        teacher_map = {t["id"]: t for t in _MOCK_TEACHERS}
        resolved = []
        for item in subject_teachers or []:
            subj = item.get("subject")
            tid = item.get("teacher_id")
            if subj not in config.SUBJECTS:
                raise ApiError(422, "validation_error", f"Invalid subject: {subj}")
            if tid not in teacher_map:
                raise ApiError(422, "validation_error", f"Unknown teacher id: {tid}")
            resolved.append(
                {
                    "subject": subj,
                    "teacher_id": tid,
                    "teacher_name": teacher_map[tid]["name"],
                }
            )
        _MOCK_CLASSES[class_id]["subject_teachers"] = resolved
        return [dict(r) for r in resolved]
    return _request(
        "PUT",
        f"/faculty/classes/{class_id}/subject-teachers",
        json={"subject_teachers": subject_teachers},
        timeout=get_timeout("E30"),
    )







