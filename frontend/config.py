# Settings: API_BASE_URL, FILES_BASE_URL and the USE_MOCK flags (one per endpoint E1 to E30)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
FILES_BASE_URL = os.getenv("FILES_BASE_URL", "http://localhost:8000")

# Fixed subject list from API contract v0.2 section 0. Use st.selectbox(options=SUBJECTS) everywhere a subject is entered.
SUBJECTS = ["Mathematics", "Physics", "Chemistry", "Biology"]

USE_MOCK = {
    "E1": False,
    "E2": False,
    "E3": False,
    "E4": False,
    "E5": False,
    "E6": False,
    "E7": False,
    "E8": False,
    "E9": False,
    "E10": False,
    "E11": False,
    "E12": False,
    "E13": False,
    "E14": False,
    "E15": False,
    "E16": False,
    "E17": False,
    "E18": False,
    "E19": False,
    "E20": False,
    "E21": False,
    "E22": False,
    "E23": False,
    "E24": False,
    "E25": False,
    "E26": False,
    "E27": False,
    "E28": False,
    "E29": False,
    "E30": False,
}

# Request timeout in seconds per endpoint, from API contract v0.2.
TIMEOUTS = {
    "default": 15,
    "E3": 60,
    "E5": 60,
    "E7": 60,
    "E19": 30,
    "E24": 30,
    "E27": 20,
}


def is_mock(endpoint_id):
    return USE_MOCK.get(endpoint_id, False)


def get_timeout(endpoint_id):
    return TIMEOUTS.get(endpoint_id, TIMEOUTS["default"])


def file_url(path):
    if not path:
        return None
    if path.startswith("/"):
        return FILES_BASE_URL.rstrip("/") + path
    return FILES_BASE_URL.rstrip("/") + "/" + path
