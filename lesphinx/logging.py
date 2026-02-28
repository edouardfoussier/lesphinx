"""JSONL logging for game events."""

import json
import time
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "game_events.jsonl"


def log_event(event_type: str, session_id: str = "", **data: object) -> None:
    entry = {
        "ts": time.time(),
        "event": event_type,
        "session_id": session_id,
        **data,
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass  # Never let logging crash the app
