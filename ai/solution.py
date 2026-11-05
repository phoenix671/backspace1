import json
from typing import Any, Dict, List, Optional

from google.genai import types

from ai.client import generate_with_fallback, get_gemini_client
from ai.exceptions import AIError


def get_topics_and_formulae(question_text: str, topic: str) -> Dict[str, Any]:
    client = get_gemini_client()

    prompt = (
        f"For the question below in topic '{topic}':\n"
        f"Question: {question_text}\n\n"
        "Identify:\n"
        "1. List of 1 to 3 core concepts/sub-topics required to solve it.\n"
        "2. List of essential standard mathematical or scientific formulae required to solve it.\n"
    )

    schema = {
        "type": "OBJECT",
        "required": ["topics", "formulae"],
        "properties": {
            "topics": {"type": "ARRAY", "items": {"type": "STRING"}},
            "formulae": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
            ),
        )
        data = json.loads(response.text)
        return {
            "topics": data.get("topics", [topic]),
            "formulae": data.get("formulae", []),
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Failed to get topics and formulae: {exc}")


def simplify_question(question_text: str, topic: str, diagnosis: List[Dict[str, Any]]) -> Dict[str, str]:
    client = get_gemini_client()

    diag_context = ""
    if diagnosis:
        diag_context = "The student made the following mistakes in earlier trials:\n" + "\n".join(
            f"- {d.get('description')}" for d in diagnosis
        )

    prompt = (
        f"You are a master teacher helping a struggling student on topic '{topic}'.\n"
        f"Original question: {question_text}\n"
        f"{diag_context}\n\n"
        "Break down this problem into simpler, intuitive terms without giving away the final answer. "
        "Frame it as an accessible conceptual analogy or a guided sub-goal so the student can grasp how to proceed."
    )

    schema = {
        "type": "OBJECT",
        "required": ["simplified_text"],
        "properties": {
            "simplified_text": {"type": "STRING"},
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.3,
            ),
        )
        data = json.loads(response.text)
        return {"simplified_text": str(data.get("simplified_text") or "Let's break down the problem step by step.")}
    except Exception as exc:
        raise AIError("ai_unavailable", f"Failed to simplify question: {exc}")


def solve_question(question_text: str, topic: str, diagnosis: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    client = get_gemini_client()

    prompt = (
        f"Provide the complete, rigorous solution for the following problem in topic '{topic}':\n"
        f"Question: {question_text}\n\n"
        "Requirements:\n"
        "1. Complete step-by-step breakdown (each step numbered starting from 1 with clear explanation).\n"
        "2. Exact final answer.\n"
        "3. 1 or 2 clever shortcuts or checks to verify the solution rapidly in exams.\n"
        "4. The single most efficient method to solve this class of problem.\n"
    )

    schema = {
        "type": "OBJECT",
        "required": ["steps", "final_answer", "shortcuts", "efficient_method"],
        "properties": {
            "steps": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "required": ["step_number", "text"],
                    "properties": {
                        "step_number": {"type": "INTEGER"},
                        "text": {"type": "STRING"},
                    },
                },
            },
            "final_answer": {"type": "STRING"},
            "shortcuts": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "required": ["title", "text"],
                    "properties": {
                        "title": {"type": "STRING"},
                        "text": {"type": "STRING"},
                    },
                },
            },
            "efficient_method": {
                "type": "OBJECT",
                "required": ["title", "steps"],
                "properties": {
                    "title": {"type": "STRING"},
                    "steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
            ),
        )
        data = json.loads(response.text)
        return {
            "steps": data.get("steps", []),
            "final_answer": str(data.get("final_answer") or ""),
            "shortcuts": data.get("shortcuts", []),
            "efficient_method": data.get("efficient_method", {"title": "Direct method", "steps": []}),
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Failed to solve question: {exc}")


def generate_question(topic: str, subject: str, mistake_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    client = get_gemini_client()

    hist_desc = ""
    if mistake_history:
        hist_desc = "Student struggled with: " + ", ".join(
            f"{m.get('mistake_type')}" for m in mistake_history[:3] if m.get("mistake_type")
        )

    prompt = (
        f"Generate a new practice question for subject '{subject}' on topic '{topic}'.\n"
        f"{hist_desc}\n\n"
        "Create an original, well-posed problem that tests conceptual clarity on this topic."
    )

    schema = {
        "type": "OBJECT",
        "required": ["question_text", "topic", "subject"],
        "properties": {
            "question_text": {"type": "STRING"},
            "topic": {"type": "STRING"},
            "subject": {"type": "STRING"},
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.7,
            ),
        )
        data = json.loads(response.text)
        return {
            "question_text": str(data.get("question_text") or f"Practice problem for {topic}"),
            "topic": str(data.get("topic") or topic),
            "subject": str(data.get("subject") or subject),
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Failed to generate question: {exc}")

