"""Thin Telegram Bot API client on top of `requests`, with retries and flood-limit handling."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import ExitStack
from pathlib import Path

import requests

log = logging.getLogger("telegram")

MAX_TEXT = 4096
SAFE_TEXT = 3900  # leave headroom for HTML tags / escaping


class TelegramError(Exception):
    pass


def split_text(text: str, limit: int = SAFE_TEXT) -> list[str]:
    """Split text into chunks <= limit, preferring paragraph, then line, then word boundaries."""
    text = text.strip()
    chunks: list[str] = []
    while len(text) > limit:
        window = text[:limit]
        cut = max(window.rfind("\n\n"), -1)
        if cut < limit * 0.5:
            cut = window.rfind("\n")
        if cut < limit * 0.5:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


class TelegramAPI:
    def __init__(self, token: str, retries: int = 4, base_url: str | None = None):
        if not token:
            raise TelegramError("TELEGRAM_BOT_TOKEN is missing — run `python setup.py`.")
        base_url = base_url or os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
        self._base = f"{base_url.rstrip('/')}/bot{token}/"
        self.retries = retries
        self.session = requests.Session()

    def call(self, method: str, data: dict | None = None, files: dict | None = None, timeout: float = 60):
        payload = {}
        for key, value in (data or {}).items():
            if value is None:
                continue
            payload[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
        delay = 2.0
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.post(self._base + method, data=payload, files=files, timeout=timeout)
                body = resp.json()
            except (requests.RequestException, ValueError) as exc:
                # never include the exception text verbatim: it can contain the token URL
                log.warning("%s: network error (%s), attempt %d", method, type(exc).__name__, attempt)
                if attempt == self.retries:
                    raise TelegramError(f"{method}: network error ({type(exc).__name__})") from None
                time.sleep(delay)
                delay *= 2
                if files:
                    for f in files.values():
                        f.seek(0)
                continue
            if body.get("ok"):
                return body["result"]
            code = body.get("error_code")
            desc = body.get("description", "unknown error")
            if code == 429:
                wait = int(body.get("parameters", {}).get("retry_after", 5)) + 1
                log.warning("%s: flood limit, waiting %ss", method, wait)
                time.sleep(wait)
            elif code and code >= 500 and attempt < self.retries:
                time.sleep(delay)
                delay *= 2
            else:
                raise TelegramError(f"{method}: {code} {desc}")
            if files:
                for f in files.values():
                    f.seek(0)
        raise TelegramError(f"{method}: gave up after {self.retries} attempts")

    # ---- convenience -------------------------------------------------
    def get_me(self) -> dict:
        return self.call("getMe")

    def send_message(self, chat_id, text: str, parse_mode: str | None = None, reply_markup: dict | None = None):
        return self.call("sendMessage", {
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
            "reply_markup": reply_markup, "link_preview_options": {"is_disabled": True},
        })

    def send_media_group(self, chat_id, paths: list[Path]) -> None:
        """Send images as albums of up to 10, in order."""
        for start in range(0, len(paths), 10):
            batch = paths[start:start + 10]
            if len(batch) == 1:
                self.send_photo(chat_id, batch[0])
                continue
            with ExitStack() as stack:
                files = {f"p{i}": stack.enter_context(open(p, "rb")) for i, p in enumerate(batch)}
                media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(batch))]
                self.call("sendMediaGroup", {"chat_id": chat_id, "media": media}, files=files, timeout=180)

    def send_photo(self, chat_id, path: Path, caption: str | None = None):
        with open(path, "rb") as fh:
            return self.call("sendPhoto", {"chat_id": chat_id, "caption": caption}, files={"photo": fh}, timeout=120)

    def send_document(self, chat_id, path: Path, caption: str | None = None):
        with open(path, "rb") as fh:
            return self.call("sendDocument", {"chat_id": chat_id, "caption": caption},
                             files={"document": fh}, timeout=180)

    def get_updates(self, offset: int = 0, timeout: int = 25) -> list[dict]:
        return self.call("getUpdates", {
            "offset": offset, "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }, timeout=timeout + 15)

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            self.call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
        except TelegramError as exc:
            log.debug("answerCallbackQuery failed: %s", exc)

    def set_commands(self, commands: list[tuple[str, str]]) -> None:
        self.call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in commands]})
