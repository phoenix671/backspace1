import concurrent.futures
import functools
from pathlib import Path
import random
import sys
import time

from app.config import settings
from app.errors import ApiError

TOPICS = ["Kinematics", "Newton's laws of motion", "Work, energy and power"]

QUESTION_POOL = [
    {
        "text": "A car accelerates uniformly from rest to 20 m/s in 5 s. Find its acceleration and the distance it covers.",
        "topic": "Kinematics",
        "subject": "Physics",
    },
    {
        "text": "A ball is thrown vertically upward with a speed of 15 m/s. Find the maximum height it reaches. (g = 10 m/s^2)",
        "topic": "Kinematics",
        "subject": "Physics",
    },
    {
        "text": "A train slows uniformly from 30 m/s to 10 m/s in 8 s. Find the retardation and the distance travelled.",
        "topic": "Kinematics",
        "subject": "Physics",
    },
    {
        "text": "A 5 kg block is pulled on a smooth surface by a force of 20 N. Find its acceleration.",
        "topic": "Newton's laws of motion",
        "subject": "Physics",
    },
    {
        "text": "A 2 kg object is acted on by forces of 12 N east and 5 N north. Find the magnitude of its acceleration.",
        "topic": "Newton's laws of motion",
        "subject": "Physics",
    },
    {
        "text": "A lift of mass 500 kg accelerates upward at 2 m/s^2. Find the tension in the cable. (g = 10 m/s^2)",
        "topic": "Newton's laws of motion",
        "subject": "Physics",
    },
    {
        "text": "A 3 kg ball is lifted 4 m above the ground. Find its gain in potential energy. (g = 10 m/s^2)",
        "topic": "Work, energy and power",
        "subject": "Physics",
    },
    {
        "text": "A motor lifts a 100 kg load through 12 m in 20 s. Find the power developed. (g = 10 m/s^2)",
        "topic": "Work, energy and power",
        "subject": "Physics",
    },
    {
        "text": "A 2 kg body moving at 6 m/s is brought to rest by friction. Find the work done by friction.",
        "topic": "Work, energy and power",
        "subject": "Physics",
    },
]

FORMULAE = {
    "Kinematics": ["v = u + at", "s = ut + (1/2)at^2", "v^2 = u^2 + 2as"],
    "Newton's laws of motion": [
        "F = ma",
        "W = mg",
        "Net force = vector sum of all forces",
    ],
    "Work, energy and power": [
        "W = Fs cos(theta)",
        "KE = (1/2)mv^2",
        "PE = mgh",
        "P = W / t",
    ],
}

RELATED_TOPIC = {
    "Kinematics": "Equations of motion",
    "Newton's laws of motion": "Free body diagrams",
    "Work, energy and power": "Conservation of energy",
}

DIAGNOSIS_POOL = [
    {
        "step_number": 2,
        "student_wrote": "a = (u - v) / t = -4 m/s^2",
        "expected": "a = (v - u) / t = 4 m/s^2",
        "mistake_type": "sign_error",
        "description": "The sign flipped because initial and final velocity were swapped.",
    },
    {
        "step_number": 3,
        "student_wrote": "s = vt = 20 x 5 = 100 m",
        "expected": "s = ut + (1/2)at^2 = 50 m",
        "mistake_type": "formula_misuse",
        "description": "Used the constant-velocity formula for uniformly accelerated motion.",
    },
    {
        "step_number": 1,
        "student_wrote": "m = 500 g, F = 20 N, a = F/m = 0.04",
        "expected": "m = 0.5 kg, a = 40 m/s^2",
        "mistake_type": "unit_slip",
        "description": "Mass was not converted from grams to kilograms.",
    },
    {
        "step_number": 2,
        "student_wrote": "Weight acts upward, so T = mg",
        "expected": "T - mg = ma",
        "mistake_type": "concept_gap",
        "description": "Forgot that the cable tension must also supply the acceleration.",
    },
]

_VALID_CODES = {"ai_unavailable", "ai_timeout", "image_unreadable"}


class AIError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(message)


def _read_bytes(path: str | Path) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return b""


def _run_real(name: str, *args, **kwargs):
    repo_root = str(Path(__file__).resolve().parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        import ai
    except Exception as exc:
        raise AIError("ai_unavailable", f"Could not import ai package: {exc}")

    if not hasattr(ai, name):
        raise AIError("ai_unavailable", f"Function {name} not found in ai package")

    target_func = getattr(ai, name)
    try:
        res = target_func(*args, **kwargs)
    except AIError:
        raise
    except Exception as exc:
        if getattr(exc, "code", None) in _VALID_CODES:
            raise AIError(exc.code, str(exc))
        raise AIError("ai_unavailable", "AI call failed")

    if not isinstance(res, dict):
        raise AIError("ai_unavailable", "AI call did not return a dict")

    return res


def _switchable(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if settings.USE_REAL_AI:
            return _run_real(func.__name__, *args, **kwargs)
        return func(*args, **kwargs)

    return wrapper


_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)


def call_ai(func, *args, timeout: float = 60.0, **kwargs):
    future = _executor.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise ApiError(504, "ai_timeout", "The AI took too long to respond")
    except AIError as err:
        status_map = {
            "ai_unavailable": 503,
            "ai_timeout": 504,
            "image_unreadable": 422,
        }
        status_code = status_map.get(err.code, 503)
        raise ApiError(status_code, err.code, err.message)
    except Exception:
        raise ApiError(503, "ai_unavailable", "AI call failed")


@_switchable
def ingest_book(book_id, file_path, name, subject, type):
    time.sleep(1)
    if "FAILINGEST" in name:
        return {
            "status": "failed",
            "page_count": None,
            "chunk_count": 0,
            "error": "Could not parse the PDF",
        }
    page_count = random.randint(80, 200)
    chunk_count = page_count * random.randint(4, 7)
    return {
        "status": "ready",
        "page_count": page_count,
        "chunk_count": chunk_count,
        "error": None,
    }


@_switchable
def extract_question_from_book(book_id, chapter, question_ref):
    if "999" in str(question_ref):
        return {
            "found": False,
            "question_text": None,
            "topic": None,
            "subject": None,
            "confidence": 0.0,
        }

    pool = QUESTION_POOL
    if chapter is not None:
        ch_lower = str(chapter).strip().lower()
        matched = [q for q in QUESTION_POOL if q["topic"].lower() == ch_lower]
        if matched:
            pool = matched

    item = random.choice(pool)
    confidence = round(random.uniform(0.8, 0.99), 2)
    return {
        "found": True,
        "question_text": item["text"],
        "topic": item["topic"],
        "subject": "Physics",
        "confidence": confidence,
    }


@_switchable
def extract_question_from_image(image_path):
    raw = _read_bytes(image_path)
    if b"UNREADABLE" in raw:
        return {
            "readable": False,
            "question_text": None,
            "topic": None,
            "subject": None,
        }

    item = random.choice(QUESTION_POOL)
    return {
        "readable": True,
        "question_text": item["text"],
        "topic": item["topic"],
        "subject": item["subject"],
    }


@_switchable
def analyze_attempt(question, solution_image_path, trial_number, mistake_history):
    raw = _read_bytes(solution_image_path)
    if b"UNCLEAR" in raw:
        return {
            "verdict": "unclear",
            "message": "I could not read your photo clearly. Please retake it in good light.",
            "diagnosis": [],
        }

    if b"CORRECT" in raw:
        return {
            "verdict": "correct",
            "message": "Well done, that is correct.",
            "diagnosis": [],
        }

    k = random.choice([1, 2])
    chosen = random.sample(DIAGNOSIS_POOL, k)
    diagnosis = [dict(d) for d in chosen]

    n = diagnosis[0]["step_number"]
    if trial_number == 1:
        message = f"You are close. Check step {n}."
    elif trial_number == 2:
        message = f"Still not right. Re-read step {n} using the hints."
    else:
        message = "Let us go through the full solution together."

    first_type = diagnosis[0]["mistake_type"]
    has_prior_mistake = False
    for row in mistake_history or []:
        r_type = getattr(row, "mistake_type", None)
        if r_type is None and isinstance(row, dict):
            r_type = row.get("mistake_type")
        if r_type == first_type:
            has_prior_mistake = True
            break

    if has_prior_mistake:
        message += " You have made this kind of mistake before."

    return {
        "verdict": "incorrect",
        "message": message,
        "diagnosis": diagnosis,
    }


@_switchable
def get_topics_and_formulae(question_text, topic):
    topics = [topic, RELATED_TOPIC.get(topic, "Units and measurement")]
    formulae = list(FORMULAE.get(topic, ["No standard formula listed"]))
    return {"topics": topics, "formulae": formulae}

