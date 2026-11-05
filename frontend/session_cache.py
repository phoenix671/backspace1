# Saves each attempt result to disk so a student can resume a session and still see the last hints
import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache"


def save_result(session_id, session_created_at, result):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"session_{session_id}.json"
    data = None
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(loaded, dict)
                and loaded.get("created_at") == session_created_at
                and isinstance(loaded.get("results"), list)
            ):
                data = loaded
        except (ValueError, OSError):
            data = None
    if data is None:
        data = {"created_at": session_created_at, "results": []}
    data["results"].append(result)
    path.write_text(json.dumps(data), encoding="utf-8")


def load_results(session_id, session_created_at):
    path = CACHE_DIR / f"session_{session_id}.json"
    if not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if (
            isinstance(loaded, dict)
            and loaded.get("created_at") == session_created_at
            and isinstance(loaded.get("results"), list)
        ):
            return loaded["results"]
    except (ValueError, OSError):
        pass
    return []
