"""Logging that never prints secrets (tokens can appear inside request URLs)."""
from __future__ import annotations

import logging
import os
import re

from .config import ROOT, SECRET_KEYS

_BOT_URL = re.compile(r"bot\d+:[A-Za-z0-9_-]{20,}")


def redact(text: str) -> str:
    text = _BOT_URL.sub("bot***", str(text))
    for key in SECRET_KEYS:
        value = os.environ.get(key, "")
        if len(value) >= 6 and key != "TELEGRAM_CHAT_ID":
            text = text.replace(value, "***")
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def setup_logging(verbose: bool = False) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for handler in (logging.StreamHandler(), logging.FileHandler(ROOT / "bot.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        handler.addFilter(RedactFilter())
        root.addHandler(handler)
    # urllib3 logs full URLs (with the bot token) at DEBUG level
    logging.getLogger("urllib3").setLevel(logging.WARNING)
