# The ONLY file that talks to the backend: one function per endpoint, mock or real
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


def _request(method, path, json=None, data=None, files=None, params=None, timeout=30, raw=False):
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
    if raw:
        return response.content
    return response.json()


# E1: POST /auth/login
def login(email, password):
    return _request(
        "POST",
        "/auth/login",
        json={"email": email.strip(), "password": password},
        timeout=get_timeout("E1"),
    )


# E2: GET /auth/me
def get_me():
    return _request("GET", "/auth/me", timeout=get_timeout("E2"))


# E3: POST /student/sessions/upload
def upload_question(image=None, text=None):
    files = {"image": (image.name, image.getvalue(), image.type)} if image is not None else None
    data = {"text": text} if text is not None else None
    return _request(
        "POST",
        "/student/sessions/upload",
        data=data,
        files=files,
        timeout=get_timeout("E3"),
    )


# E4: GET /student/sessions/{session_id}
def get_session(session_id):
    return _request("GET", f"/student/sessions/{session_id}", timeout=get_timeout("E4"))


# E5: POST /student/sessions/{session_id}/attempts
def submit_attempt(session_id, image):
    if image is None:
        raise ApiError(422, "validation_error", "Upload a photo of your solution.")
    files = {"image": (image.name, image.getvalue(), image.type)}
    return _request(
        "POST",
        f"/student/sessions/{session_id}/attempts",
        files=files,
        timeout=get_timeout("E5"),
    )


# E6: GET /student/sessions/{session_id}/gif
def get_gif(session_id):
    return _request("GET", f"/student/sessions/{session_id}/gif", timeout=get_timeout("E6"))


# E7: POST /student/sessions/{session_id}/followups
def get_followups(session_id):
    return _request("POST", f"/student/sessions/{session_id}/followups", timeout=get_timeout("E7"))


# E8: POST /student/sessions/{session_id}/skip
def skip_session(session_id):
    return _request("POST", f"/student/sessions/{session_id}/skip", timeout=get_timeout("E8"))


# E9: POST /faculty/teachers
def create_teacher(name, subject, phone=None):
    payload = {"name": name, "subject": subject}
    if phone:
        payload["phone"] = phone
    return _request("POST", "/faculty/teachers", json=payload, timeout=get_timeout("E9"))


# E10: GET /faculty/teachers
def list_teachers():
    return _request("GET", "/faculty/teachers", timeout=get_timeout("E10"))


# E11: POST /faculty/classes
def create_class(name, students, subject_teachers):
    return _request(
        "POST",
        "/faculty/classes",
        json={"name": name, "students": students, "subject_teachers": subject_teachers},
        timeout=get_timeout("E11"),
    )


# E12: GET /faculty/classes
def list_faculty_classes():
    return _request("GET", "/faculty/classes", timeout=get_timeout("E12"))


# E13: GET /faculty/classes/{class_id}
def get_class_detail(class_id):
    return _request("GET", f"/faculty/classes/{class_id}", timeout=get_timeout("E13"))


# E14: POST /faculty/books
def upload_book(file, name, book_type, subject):
    if file is None:
        raise ApiError(422, "validation_error", "Please select a PDF file.")
    files = {"file": (file.name, file.getvalue(), "application/pdf")}
    data = {"name": name, "type": book_type, "subject": subject}
    return _request("POST", "/faculty/books", data=data, files=files, timeout=get_timeout("E14"))


# E15: GET /books
def list_books(q=None, book_type=None, subject=None):
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
    return _request("GET", f"/books/{book_id}", timeout=get_timeout("E16"))


# E17: GET /books/{book_id}/file
def get_book_file(book_id):
    return _request("GET", f"/books/{book_id}/file", timeout=get_timeout("E17"), raw=True)


def get_book_file_url(book_id):
    return config.API_BASE_URL.rstrip("/") + f"/books/{book_id}/file"


# E18: GET /teacher/classes
def list_teacher_classes():
    return _request("GET", "/teacher/classes", timeout=get_timeout("E18"))


# E19: POST /teacher/classes/{class_id}/homework
def create_homework(class_id, book_id, chapter, question_ref, title=None, due_at=None):
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


# E20: GET /teacher/classes/{class_id}/homework
def list_class_homework(class_id):
    return _request("GET", f"/teacher/classes/{class_id}/homework", timeout=get_timeout("E20"))


# E21: GET /teacher/homework/{homework_id}
def get_homework_detail(homework_id):
    return _request("GET", f"/teacher/homework/{homework_id}", timeout=get_timeout("E21"))


# E22: GET /student/homework
def list_student_homework():
    return _request("GET", "/student/homework", timeout=get_timeout("E22"))


# E23: POST /student/sessions/homework
def start_homework_session(homework_id):
    return _request(
        "POST",
        "/student/sessions/homework",
        json={"homework_id": homework_id},
        timeout=get_timeout("E23"),
    )


# E24: POST /student/sessions/pyq
def start_pyq_session(book_id, question_ref, chapter=None):
    payload = {"book_id": book_id, "question_ref": question_ref}
    if chapter:
        payload["chapter"] = chapter
    return _request("POST", "/student/sessions/pyq", json=payload, timeout=get_timeout("E24"))


# E25: GET /student/stats
def get_student_stats():
    return _request("GET", "/student/stats", timeout=get_timeout("E25"))


# E26: GET /teacher/classes/{class_id}/status
def get_class_status(class_id):
    return _request("GET", f"/teacher/classes/{class_id}/status", timeout=get_timeout("E26"))


# E27: GET /student/sessions/{session_id}/videos
def get_session_videos(session_id):
    return _request("GET", f"/student/sessions/{session_id}/videos", timeout=get_timeout("E27"))


# E28: POST /faculty/classes/{class_id}/students
def add_class_student(class_id, name, roll_number=None):
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
    return _request(
        "DELETE",
        f"/faculty/classes/{class_id}/students/{student_id}",
        timeout=get_timeout("E29"),
    )


# E30: PUT /faculty/classes/{class_id}/subject-teachers
def update_class_subject_teachers(class_id, subject_teachers):
    return _request(
        "PUT",
        f"/faculty/classes/{class_id}/subject-teachers",
        json={"subject_teachers": subject_teachers},
        timeout=get_timeout("E30"),
    )
