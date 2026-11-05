import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Ensure backend .env is loaded if environment variable is not directly set
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from ai.exceptions import AIError

_client = None


def get_gemini_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AIError("ai_unavailable", "GEMINI_API_KEY environment variable is not configured.")

    try:
        from google import genai
        _client = genai.Client(api_key=api_key)
        return _client
    except Exception as exc:
        raise AIError("ai_unavailable", f"Failed to initialize Gemini GenAI Client: {exc}")


def get_default_model() -> str:
    # Allow user override via env var, default to gemini-2.5-flash
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

