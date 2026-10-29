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


def video_keyboard(cfg: dict, post_id: str, interactive: bool) -> dict:
    rows = [[{"text": "Open LinkedIn composer", "url": cfg["telegram"]["linkedin_url"]}]]
    if interactive:
        rows.append([{"text": "🎬 New video", "callback_data": f"vnew:{post_id}"},
                     {"text": "🎨 Another theme", "callback_data": f"vtheme:{post_id}"}])
    return {"inline_keyboard": rows}


def send_video_post(api: TelegramAPI, chat_id, cfg: dict, post: dict, interactive: bool = False) -> None:
    data = post["data"]
    first = post["videos"][0]
    lines = [f"🎬 Daily video · Topic: {data['topic']}",
             f"Theme: {post['theme']} · {first['duration']}s · " + ", ".join(v["format"] for v in post["videos"])]
    issues = [f"{v['format']}: {i}" for v in post["videos"] for i in v["qa"]["issues"]]
    if issues:
        lines.append("⚠️ QA notes: " + "; ".join(issues)[:500])
    lines.append("LinkedIn: Start a post → Add media → upload the MP4, then paste the text below.")
    api.send_message(chat_id, "\n".join(lines))
    for v in post["videos"]:
        api.send_video(chat_id, v["path"], caption=f"{v['format']} · {v['width']}×{v['height']}",
                       width=v["width"], height=v["height"], duration=v["duration"], thumbnail=None)
    send_text(api, chat_id, full_post_text(data), cfg, reply_markup=video_keyboard(cfg, post["id"], interactive))


def send_error(api: TelegramAPI | None, chat_id, message: str) -> None:
    log.error(message)
    if api is None:
        return
    try:
        api.send_message(chat_id, f"⚠️ {message[:900]}")
    except Exception as exc:  # noqa: BLE001 — reporting must never crash the caller
        log.error("could not deliver error message: %s", exc)
