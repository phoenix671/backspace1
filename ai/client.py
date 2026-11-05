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
    # Default to gemini-3.1-flash-lite for ultra-fast responses (~1.3s) and highest stability
    return os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")


def generate_with_fallback(client, contents, config=None, models=None):
    if models is None:
        primary = get_default_model()
        candidates = [primary, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
        seen = set()
        models = [m for m in candidates if not (m in seen or seen.add(m))]

    last_exc = None
    for m in models:
        try:
            return client.models.generate_content(
                model=m,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            last_exc = exc
            continue

    raise last_exc

