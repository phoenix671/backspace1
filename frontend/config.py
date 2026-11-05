# Settings: API_BASE_URL, FILES_BASE_URL and the USE_MOCK flags (one per endpoint E1 to E30)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
FILES_BASE_URL = os.getenv("FILES_BASE_URL", "http://localhost:8000")

USE_MOCK = {
    "E1": True,
    "E2": True,
    "E3": True,
    "E4": True,
    "E5": True,
    "E6": True,
    "E7": True,
    "E8": True,
    "E9": True,
    "E10": True,
    "E11": True,
    "E12": True,
    "E13": True,
    "E14": True,
    "E15": True,
    "E16": True,
    "E17": True,
    "E18": True,
    "E19": True,
    "E20": True,
    "E21": True,
    "E22": True,
    "E23": True,
    "E24": True,
    "E25": True,
    "E26": True,
    "E27": True,
    "E28": True,
    "E29": True,
    "E30": True,
}


def is_mock(endpoint_id):
    return USE_MOCK.get(endpoint_id, True)


def file_url(path):
    if not path:
        return None
    if path.startswith("/"):
        return FILES_BASE_URL.rstrip("/") + path
    return FILES_BASE_URL.rstrip("/") + "/" + path

