import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.genai import types

from ai.client import generate_with_fallback, get_gemini_client
from ai.exceptions import AIError

VALID_MISTAKE_TYPES = {"sign_error", "formula_misuse", "unit_slip", "concept_gap"}


def _read_image_part(image_path: str | Path):
    path = Path(image_path)
    if not path.exists():
        raise AIError("image_unreadable", f"Image file not found: {image_path}")

    suffix = path.suffix.lower()
    mime_type = "image/jpeg"
    if suffix in (".png",):
        mime_type = "image/png"
    elif suffix in (".webp",):
        mime_type = "image/webp"

    try:
        with open(path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type=mime_type)
    except Exception as exc:
        raise AIError("image_unreadable", f"Could not read image: {exc}")


def extract_question_from_image(image_path: str | Path) -> Dict[str, Any]:
    client = get_gemini_client()
    image_part = _read_image_part(image_path)

    prompt = (
        "You are an expert educational AI. Inspect the provided image of a student's question.\n"
        "If the image is blurry, corrupted, unreadable, blank, or does not clearly contain a academic/science/math question, "
        "set readable to false, and set question_text, topic, and subject to null.\n"
        "Otherwise, extract the exact question text verbatim. Determine its specific academic topic (e.g. 'Kinematics', "
        "'Quadratic equations', 'Newton's laws of motion') and subject (e.g. 'Physics', 'Mathematics', 'Chemistry')."
    )

    schema = {
        "type": "OBJECT",
        "required": ["readable"],
        "properties": {
            "readable": {"type": "BOOLEAN"},
            "question_text": {"type": "STRING", "nullable": True},
            "topic": {"type": "STRING", "nullable": True},
            "subject": {"type": "STRING", "nullable": True},
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
        data = json.loads(response.text)
        if not data.get("readable") or not data.get("question_text"):
            return {
                "readable": False,
                "question_text": None,
                "topic": None,
                "subject": None,
            }
        return {
            "readable": True,
            "question_text": str(data["question_text"]).strip(),
            "topic": str(data.get("topic") or "General").strip(),
            "subject": str(data.get("subject") or "General").strip(),
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Vision question extraction failed: {exc}")


def analyze_attempt(
    question: Dict[str, Any],
    solution_image_path: str | Path,
    trial_number: int,
    mistake_history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    client = get_gemini_client()
    image_part = _read_image_part(solution_image_path)

    q_text = question.get("text", "")
    q_topic = question.get("topic", "")
    q_subject = question.get("subject", "")

    history_context = ""
    if mistake_history:
        history_context = "\nStudent's recent mistake patterns (use to tailor hint without giving away the answer):\n"
        for m in mistake_history[:5]:
            history_context += f"- In topic '{m.get('topic')}', made mistake '{m.get('mistake_type')}': {m.get('description')}\n"

    prompt = (
        f"You are a compassionate, rigorous expert STEM teacher.\n"
        f"Question text: {q_text}\n"
        f"Topic: {q_topic} | Subject: {q_subject}\n"
        f"Current Trial: {trial_number} of 3\n"
        f"{history_context}\n\n"
        "Evaluate the student's handwritten solution in the image:\n"
        "1. If the handwritten image is illegible, cutoff, or cannot be parsed, set verdict to 'unclear', "
        "message to a polite request to upload a clearer photo, and diagnosis to an empty list [].\n"
        "2. If the solution is mathematically correct and arrives at the right answer, set verdict to 'correct', "
        "message to an encouraging confirmation, and diagnosis to [].\n"
        "3. If the solution is incorrect:\n"
        "   - Set verdict to 'incorrect'.\n"
        "   - In message: give a clear, encouraging hint pointing to where things went off track WITHOUT revealing the final answer.\n"
        "   - In diagnosis: provide at least 1 item detailing the exact error.\n"
        "     Each diagnosis item MUST have:\n"
        "     - step_number (integer >= 1)\n"
        "     - student_wrote (exact text/formula of what the student wrote)\n"
        "     - expected (what should have been written)\n"
        "     - mistake_type: MUST be strictly one of: 'sign_error', 'formula_misuse', 'unit_slip', 'concept_gap'\n"
        "     - description: concise 1-line explanation of the mistake.\n"
    )

    schema = {
        "type": "OBJECT",
        "required": ["verdict", "message", "diagnosis"],
        "properties": {
            "verdict": {"type": "STRING", "enum": ["correct", "incorrect", "unclear"]},
            "message": {"type": "STRING"},
            "diagnosis": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "required": ["step_number", "student_wrote", "expected", "mistake_type", "description"],
                    "properties": {
                        "step_number": {"type": "INTEGER"},
                        "student_wrote": {"type": "STRING"},
                        "expected": {"type": "STRING"},
                        "mistake_type": {
                            "type": "STRING",
                            "enum": ["sign_error", "formula_misuse", "unit_slip", "concept_gap"],
                        },
                        "description": {"type": "STRING"},
                    },
                },
            },
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
            ),
        )
        res = json.loads(response.text)
        verdict = res.get("verdict")
        if verdict not in ("correct", "incorrect", "unclear"):
            verdict = "unclear"

        diagnosis = res.get("diagnosis", [])
        if verdict in ("correct", "unclear"):
            diagnosis = []
        elif verdict == "incorrect":
            # Sanitize mistake_types
            clean_diag = []
            for d in diagnosis:
                m_type = d.get("mistake_type")
                if m_type not in VALID_MISTAKE_TYPES:
                    m_type = "concept_gap"
                clean_diag.append({
                    "step_number": int(d.get("step_number") or 1),
                    "student_wrote": str(d.get("student_wrote") or ""),
                    "expected": str(d.get("expected") or ""),
                    "mistake_type": m_type,
                    "description": str(d.get("description") or ""),
                })
            if not clean_diag:
                clean_diag.append({
                    "step_number": 1,
                    "student_wrote": "Incorrect calculation",
                    "expected": "Review initial formula application",
                    "mistake_type": "concept_gap",
                    "description": "The solution deviated in the initial problem setup.",
                })
            diagnosis = clean_diag

        return {
            "verdict": verdict,
            "message": str(res.get("message") or "Solution analyzed."),
            "diagnosis": diagnosis,
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Attempt evaluation failed: {exc}")

