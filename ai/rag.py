import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from google.genai import types

from ai.client import generate_with_fallback, get_gemini_client
from ai.exceptions import AIError


def _get_rag_storage_dir() -> Path:
    # Resolves to backend/storage/rag
    p = Path(__file__).resolve().parent.parent / "backend" / "storage" / "rag"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ingest_book(
    book_id: int,
    file_path: str | Path,
    name: str,
    subject: str,
    book_type: str,
) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        return {
            "status": "failed",
            "page_count": None,
            "chunk_count": 0,
            "error": f"Book file not found: {file_path}",
        }

    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        page_count = len(reader.pages)

        chunks = []
        for p_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                chunks.append({
                    "page": p_idx + 1,
                    "text": text,
                })

        chunk_count = len(chunks)
        # Save index locally
        index_data = {
            "book_id": book_id,
            "name": name,
            "subject": subject,
            "type": book_type,
            "page_count": page_count,
            "chunks": chunks,
        }
        index_file = _get_rag_storage_dir() / f"book_{book_id}.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)

        return {
            "status": "ready",
            "page_count": page_count,
            "chunk_count": chunk_count,
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "page_count": None,
            "chunk_count": 0,
            "error": f"PDF indexing failed: {exc}",
        }


def extract_question_from_book(
    book_id: int,
    chapter: Optional[str],
    question_ref: str,
) -> Dict[str, Any]:
    index_file = _get_rag_storage_dir() / f"book_{book_id}.json"
    if not index_file.exists():
        return {
            "found": False,
            "question_text": None,
            "topic": None,
            "subject": None,
            "confidence": 0.0,
        }

    with open(index_file, "r", encoding="utf-8") as f:
        book_data = json.load(f)

    chunks = book_data.get("chunks", [])
    subject = book_data.get("subject", "General")

    # Filter most relevant chunks
    ref_clean = question_ref.lower().strip()
    chap_clean = (chapter or "").lower().strip()

    candidate_texts = []
    for c in chunks:
        c_text = c["text"]
        c_lower = c_text.lower()
        if ref_clean in c_lower or (chap_clean and chap_clean in c_lower):
            candidate_texts.append(c_text)

    if not candidate_texts:
        # Fallback to first few pages if no exact substring
        candidate_texts = [c["text"] for c in chunks[:5]]

    combined_context = "\n---\n".join(candidate_texts[:6])

    client = get_gemini_client()
    prompt = (
        f"You are a RAG indexing engine. Given the book excerpts below:\n\n"
        f"{combined_context}\n\n"
        f"Search for the specific question referenced as '{question_ref}' in chapter '{chapter or 'Any'}'.\n"
        "If you find the exact question, extract its full question text, identify its specific topic, "
        "and set found to true with your confidence (0.0 to 1.0).\n"
        "If the question cannot be found with high confidence in the provided text, set found to false."
    )

    schema = {
        "type": "OBJECT",
        "required": ["found"],
        "properties": {
            "found": {"type": "BOOLEAN"},
            "question_text": {"type": "STRING", "nullable": True},
            "topic": {"type": "STRING", "nullable": True},
            "confidence": {"type": "NUMBER"},
        },
    }

    try:
        response = generate_with_fallback(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
        res = json.loads(response.text)
        if not res.get("found") or not res.get("question_text"):
            return {
                "found": False,
                "question_text": None,
                "topic": None,
                "subject": None,
                "confidence": 0.0,
            }
        return {
            "found": True,
            "question_text": str(res["question_text"]).strip(),
            "topic": str(res.get("topic") or chapter or "General").strip(),
            "subject": subject,
            "confidence": float(res.get("confidence") or 0.9),
        }
    except Exception as exc:
        raise AIError("ai_unavailable", f"Book question search failed: {exc}")


def find_pyqs(
    topic: str,
    subject: str,
    n: int = 2,
    exclude_question_texts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    exclude = set(exclude_question_texts or [])
    rag_dir = _get_rag_storage_dir()
    index_files = list(rag_dir.glob("book_*.json"))

    matching_questions = []

    # Try to find questions from indexed books
    for f in index_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                b_data = json.load(fp)
            if b_data.get("subject", "").lower() == subject.lower():
                b_id = b_data.get("book_id")
                chunks = b_data.get("chunks", [])
                for idx, c in enumerate(chunks[:10]):
                    if topic.lower() in c["text"].lower():
                        q_text = c["text"][:120].strip()
                        if q_text not in exclude:
                            matching_questions.append({
                                "question_text": q_text,
                                "topic": topic,
                                "subject": subject,
                                "book_id": b_id,
                                "reference": f"Page {c.get('page', idx+1)}",
                            })
                            if len(matching_questions) >= n:
                                break
        except Exception:
            continue

    # If fewer than n found from index, use Gemini to generate/retrieve canonical PYQs
    if len(matching_questions) < n:
        client = get_gemini_client()
        needed = n - len(matching_questions)
        prompt = (
            f"Generate {needed} real or authentic-style Past Year Exam Questions (PYQ) for {subject} on topic '{topic}'.\n"
            f"Do not include these questions: {list(exclude)}\n"
            "Include year or exam reference (e.g. '2023 Q4', '2022 Q2')."
        )
        schema = {
            "type": "OBJECT",
            "required": ["questions"],
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "required": ["question_text", "reference"],
                        "properties": {
                            "question_text": {"type": "STRING"},
                            "reference": {"type": "STRING"},
                        },
                    },
                },
            },
        }
        try:
            resp = generate_with_fallback(
                client,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.3,
                ),
            )
            data = json.loads(resp.text)
            for q in data.get("questions", []):
                matching_questions.append({
                    "question_text": q["question_text"],
                    "topic": topic,
                    "subject": subject,
                    "book_id": None,
                    "reference": q.get("reference", "PYQ"),
                })
        except Exception:
            pass

    return {"questions": matching_questions[:n]}

