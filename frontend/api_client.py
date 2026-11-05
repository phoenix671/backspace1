# The ONLY file that talks to the backend: one function per endpoint, mock or real
import requests
import streamlit as st
import config


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



