"""Send a finished post to Telegram: header → album → PDF/original → copy-ready text with buttons."""
from __future__ import annotations

import html
import logging

from ..content.schema import full_post_text
from .api import TelegramAPI, split_text

log = logging.getLogger("delivery")

FORMAT_NAMES = {"carousel": "Carousel", "single": "Single image", "quote": "Quote card", "checklist": "Checklist"}


def keyboard(cfg: dict, post_id: str, theme: str, interactive: bool) -> dict:
    rows = [[{"text": "Open LinkedIn composer", "url": cfg["telegram"]["linkedin_url"]}]]
    if interactive:
        rows.append([{"text": "🔄 Regenerate", "callback_data": f"regen:{post_id}"},
                     {"text": "✂️ Make it shorter", "callback_data": f"short:{post_id}"}])
        rows.append([{"text": "🎲 Different topic", "callback_data": f"topic:{post_id}"},
                     {"text": "🎨 Another theme", "callback_data": f"theme:next:{post_id}"}])
    return {"inline_keyboard": rows}


def header_text(post: dict, index: int, total: int) -> str:
    data = post["data"]
    lines = [f"Post {index}/{total} · {FORMAT_NAMES.get(data['format'], data['format'])} · Topic: {data['topic']}"]
    lines.append(f"Theme: {post['theme']} · {len(post['images'])} image(s)")
    if data.get("alt_text"):
        lines.append(f"\nAlt text (paste into LinkedIn's “Add alt text”):\n{data['alt_text']}")
    return "\n".join(lines)


def send_text(api: TelegramAPI, chat_id, text: str, cfg: dict, reply_markup: dict | None = None) -> None:
    chunks = split_text(text)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        if cfg["telegram"].get("text_style", "code") == "code":
            # <pre> blocks are tap-to-copy in Telegram apps
            api.send_message(chat_id, f"<pre>{html.escape(chunk)}</pre>", parse_mode="HTML", reply_markup=markup)
        else:
            api.send_message(chat_id, chunk, reply_markup=markup)


def send_post(api: TelegramAPI, chat_id, cfg: dict, post: dict, index: int = 1, total: int = 1,
              interactive: bool = False, only_text: bool = False) -> None:
    if not only_text:
        api.send_message(chat_id, header_text(post, index, total))
        api.send_media_group(chat_id, post["images"])
        if post.get("pdf"):
            api.send_document(chat_id, post["pdf"], caption="LinkedIn: Start a post → Add a document → upload this PDF.")
        else:
            api.send_document(chat_id, post["images"][0], caption="Full-quality PNG (Telegram compresses photos).")
    send_text(api, chat_id, full_post_text(post["data"]), cfg,
              reply_markup=keyboard(cfg, post["id"], post["theme"], interactive))


def send_error(api: TelegramAPI | None, chat_id, message: str) -> None:
    log.error(message)
    if api is None:
        return
    try:
        api.send_message(chat_id, f"⚠️ {message[:900]}")
    except Exception as exc:  # noqa: BLE001 — reporting must never crash the caller
        log.error("could not deliver error message: %s", exc)
