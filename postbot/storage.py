"""History of generated posts + small runtime state, stored as JSON in data/.

JSON (not SQLite) so GitHub Actions can commit it back and diffs stay readable.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .config import DATA_DIR

_lock = threading.RLock()
MAX_HISTORY = 500

DEFAULT_STATE = {
    "paused": False,
    "skip_next": 0,
    "times": None,        # overrides config schedule.times when set via /times
    "theme": None,        # fixed theme via /theme; None = rotate
    "done_slots": {},     # {"2026-10-22": [0, 1]}
    "telegram_offset": 0,
}


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return json.loads(json.dumps(default))


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.history_path = data_dir / "history.json"
        self.state_path = data_dir / "state.json"

    # ---- history -------------------------------------------------------
    def history(self) -> list[dict]:
        with _lock:
            return _read(self.history_path, {"posts": []})["posts"]

    def add_post(self, entry: dict) -> None:
        with _lock:
            posts = self.history()
            posts.append(entry)
            _write(self.history_path, {"posts": posts[-MAX_HISTORY:]})

    def update_post(self, post_id: str, **fields) -> None:
        with _lock:
            posts = self.history()
            for p in posts:
                if p.get("id") == post_id:
                    p.update(fields)
            _write(self.history_path, {"posts": posts})

    def find_post(self, post_id: str) -> dict | None:
        return next((p for p in self.history() if p.get("id") == post_id), None)

    # ---- state ---------------------------------------------------------
    def state(self) -> dict:
        with _lock:
            return {**DEFAULT_STATE, **_read(self.state_path, DEFAULT_STATE)}

    def set_state(self, **fields) -> dict:
        with _lock:
            st = self.state()
            st.update(fields)
            _write(self.state_path, st)
            return st

    def mark_slot_done(self, day: str, slot: int) -> None:
        with _lock:
            st = self.state()
            done = st["done_slots"]
            done[day] = sorted(set(done.get(day, [])) | {slot})
            # keep only the last 14 days
            st["done_slots"] = {k: done[k] for k in sorted(done)[-14:]}
            _write(self.state_path, st)

    def slot_done(self, day: str, slot: int) -> bool:
        return slot in self.state()["done_slots"].get(day, [])
