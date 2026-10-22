#!/usr/bin/env python3
"""First-run wizard: asks for everything, writes .env (secrets) and config.yaml (settings).

Run again any time — pressing Enter keeps the current value.
"""
from __future__ import annotations

import getpass
import re
import sys
import time

from postbot.config import ROOT, load_config, secret, write_config, write_env
from postbot.images.fonts import FAMILIES, download_fonts
from postbot.telegram.api import TelegramAPI, TelegramError

PALETTES = [
    ("Indigo & Amber", "#4F46E5", "#F59E0B"),
    ("Ocean & Coral", "#0369A1", "#F43F5E"),
    ("Forest & Sun", "#047857", "#FBBF24"),
    ("Grape & Aqua", "#6D28D9", "#22D3EE"),
    ("Ink & Tangerine", "#111827", "#FF6B4A"),
]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
HEX_ANY = re.compile(r"#[0-9a-fA-F]{6}\b")
TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def ask(prompt: str, default: str = "", validate=None) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"  {prompt}{suffix}: ").strip() or default
        if validate is None or validate(value):
            return value
        print("    ✗ That doesn't look right, try again.")


def ask_secret(prompt: str, current: str) -> str:
    hint = " (Enter keeps the saved one)" if current else ""
    value = getpass.getpass(f"  {prompt}{hint} (input hidden): ").strip()
    return value or current


def yes(prompt: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    value = input(f"  {prompt} [{d}]: ").strip().lower()
    return default if not value else value.startswith("y")


def step(n: int, title: str) -> None:
    print(f"\n━━ Step {n}: {title} " + "━" * max(0, 50 - len(title)))


def setup_telegram(env: dict) -> None:
    step(1, "Telegram bot")
    print("  1. Open Telegram, search for @BotFather, send /newbot.")
    print("  2. Pick a name and a username ending in 'bot'.")
    print("  3. BotFather replies with a token like 123456789:AAH...  — paste it below.")
    while True:
        env["TELEGRAM_BOT_TOKEN"] = ask_secret("Bot token", env.get("TELEGRAM_BOT_TOKEN", ""))
        try:
            me = TelegramAPI(env["TELEGRAM_BOT_TOKEN"], retries=2).get_me()
            print(f"    ✓ Connected to @{me['username']}")
            break
        except TelegramError as exc:
            print(f"    ✗ Telegram rejected that token ({exc}). Paste it again.")
            env["TELEGRAM_BOT_TOKEN"] = ""

    api = TelegramAPI(env["TELEGRAM_BOT_TOKEN"])
    step(2, "Your chat ID")
    if env.get("TELEGRAM_CHAT_ID") and yes(f"Keep saved chat ID {env['TELEGRAM_CHAT_ID']}?"):
        pass
    else:
        print(f"  Open https://t.me/{me['username']} and send /start (waiting up to 3 minutes)…")
        api.call("deleteWebhook")
        offset, deadline = 0, time.time() + 180
        while time.time() < deadline:
            updates = api.get_updates(offset, timeout=20)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                if msg.get("chat", {}).get("type") == "private":
                    env["TELEGRAM_CHAT_ID"] = str(msg["chat"]["id"])
                    who = msg.get("from", {}).get("first_name", "")
                    print(f"    ✓ Found chat ID {env['TELEGRAM_CHAT_ID']} ({who})")
                    break
            if env.get("TELEGRAM_CHAT_ID"):
                api.get_updates(offset, timeout=0)  # acknowledge
                break
        else:
            env["TELEGRAM_CHAT_ID"] = ask("No message seen. Enter your chat ID manually",
                                          validate=lambda v: v.lstrip("-").isdigit())
    api.send_message(env["TELEGRAM_CHAT_ID"], "👋 Hello! Your content bot is connected. "
                     "Posts will arrive here.")
    print("    ✓ Test message sent — check Telegram.")


def setup_ai(env: dict, cfg: dict) -> None:
    from postbot.providers.base import ProviderError
    from postbot.providers.gemini import list_models, pick_model

    step(3, "Gemini API key (free)")
    print("  1. Go to https://aistudio.google.com/apikey and sign in with a Google account.")
    print("  2. Click 'Create API key' (no billing needed for the free tier).")
    print("  3. Copy the key and paste it below.")
    while True:
        env["GEMINI_API_KEY"] = ask_secret("Gemini API key", env.get("GEMINI_API_KEY", ""))
        try:
            model = pick_model(list_models(env["GEMINI_API_KEY"]), cfg["ai"]["gemini_model"])
            cfg["ai"]["gemini_model"] = model
            print(f"    ✓ Key works — using model {model}")
            break
        except ProviderError as exc:
            print(f"    ✗ {exc}")
            if not yes("Try again?"):
                print("    ! Key saved but not working yet — re-run `python setup.py` to fix it.")
                break
    if yes("Add an optional Groq key as a fallback? (free: https://console.groq.com/keys)", False):
        env["GROQ_API_KEY"] = ask_secret("Groq API key", env.get("GROQ_API_KEY", ""))


def setup_profile(cfg: dict) -> None:
    step(4, "You & your brand")
    p = cfg["profile"]
    p["name"] = ask("Your name (shown on images)", p["name"])
    p["handle"] = ask("Footer handle/text (e.g. @you or linkedin.com/in/you)", p["handle"])
    p["role"] = ask("Your role (used for the writing voice)", p["role"])

    print("\n  Brand colours — pick a palette or enter your own hex colours:")
    for i, (name, a, b) in enumerate(PALETTES, 1):
        print(f"    {i}. {name:<16} {a}  {b}")
    print("    6. Custom  (or just type two hex colours, e.g. #6A994E #53599A)")

    def valid(v):
        return v in {"1", "2", "3", "4", "5", "6"} or 2 <= len(HEX_ANY.findall(v)) <= 3
    choice = ask("Palette", "1", valid)
    typed = HEX_ANY.findall(choice)
    if typed:
        cfg["brand"]["primary"], cfg["brand"]["secondary"] = typed[0].upper(), typed[1].upper()
    elif choice == "6":
        cfg["brand"]["primary"] = ask("Primary colour", cfg["brand"]["primary"], HEX.match)
        cfg["brand"]["secondary"] = ask("Secondary/accent colour", cfg["brand"]["secondary"], HEX.match)
    else:
        _, cfg["brand"]["primary"], cfg["brand"]["secondary"] = PALETTES[int(choice) - 1]

    fonts = [f for f in FAMILIES if f != "dm-serif-display"]
    print(f"\n  Fonts available: {', '.join(fonts)}")
    cfg["fonts"]["heading"] = ask("Heading font", cfg["fonts"]["heading"], lambda v: v in fonts)
    cfg["fonts"]["body"] = ask("Body font", cfg["fonts"]["body"], lambda v: v in fonts)


def setup_schedule(cfg: dict) -> None:
    step(5, "Schedule & topics")
    s = cfg["schedule"]
    s["timezone"] = ask("Timezone", s["timezone"])
    times = ask("Posting times (comma separated, 24h)", ",".join(s["times"]),
                lambda v: all(TIME.match(t.strip()) for t in v.split(",")))
    s["times"] = [f"{int(t.split(':')[0]):02d}:{t.split(':')[1]}" for t in (x.strip() for x in times.split(","))]
    s["posts_per_day"] = int(ask("Posts per day", str(s["posts_per_day"]),
                                 lambda v: v.isdigit() and 1 <= int(v) <= 6))
    ratio = ask("Share of frontend/dev posts, 0–1 (0 = design only)", str(cfg["content"]["dev_topic_ratio"]),
                lambda v: re.fullmatch(r"0?\.\d+|0|1", v) is not None)
    cfg["content"]["dev_topic_ratio"] = float(ratio)
    print("  Topics live in topics.yaml (~60 seeded). Edit that file or use /add in Telegram.")

    step(6, "Portfolio projects (optional)")
    print("  Add your Figma projects so some posts can be case-study style.")
    print("  Only what you write here is used — the bot never invents results or clients.")
    portfolio = cfg["content"].get("portfolio") or []
    if portfolio and yes(f"Keep the {len(portfolio)} saved project(s)?"):
        return
    portfolio = []
    while len(portfolio) < 8 and yes("Add a project?" if not portfolio else "Add another?", not portfolio):
        name = ask("Project name")
        desc = ask("2–3 sentences: problem, what you designed, what you learned")
        if name:
            portfolio.append({"name": name, "description": desc})
    cfg["content"]["portfolio"] = portfolio


def main() -> None:
    print("\n✦ Daily Content Bot — setup")
    print("  Secrets go to .env (git-ignored). Settings go to config.yaml.")
    cfg = load_config()
    env = {k: secret(k) for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY", "GROQ_API_KEY")}
    try:
        setup_telegram(env)
        write_env(env)
        setup_ai(env, cfg)
        write_env(env)
        setup_profile(cfg)
        setup_schedule(cfg)
    except (KeyboardInterrupt, EOFError):
        print("\n  Setup cancelled — anything already confirmed was saved.")
        sys.exit(1)
    write_config(cfg)
    print("\n━━ Downloading fonts (free Google Fonts, OFL) ━━")
    present = download_fonts([cfg["fonts"]["heading"], cfg["fonts"]["body"], cfg["fonts"]["serif"]])
    print(f"    ✓ {len(present)} font file(s) in assets/fonts/")

    run = "run.bat" if sys.platform == "win32" else "./run.sh"
    print(f"""
✓ Setup complete. Saved {ROOT / '.env'} and {ROOT / 'config.yaml'}.

Next:
  {run} preview          → render sample carousels in every theme (see preview/)
  {run} now --dry-run    → generate one post locally without sending
  {run} now              → generate one post and send it to Telegram
  {run} run              → keep running: schedule + Telegram commands/buttons
""")


if __name__ == "__main__":
    main()
