"""Load config.yaml (non-secret settings) and secrets from .env / environment."""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
ENV_PATH = ROOT / ".env"
TOPICS_PATH = ROOT / "topics.yaml"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
FONTS_DIR = ROOT / "assets" / "fonts"

SECRET_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY", "GROQ_API_KEY")

DEFAULTS: dict = {
    "profile": {
        "name": "Your Name",
        "handle": "@yourhandle",
        "role": "UI/UX & Product Designer",
    },
    "brand": {
        "primary": "#4F46E5",    # indigo
        "secondary": "#F59E0B",  # amber
        "dark": "#0F172A",
        "light": "#F8FAFC",
    },
    "fonts": {"heading": "inter", "body": "inter", "serif": "dm-serif-display"},
    "image": {
        "width": 1080,
        "height": 1350,
        "themes": ["grid", "accent", "gradient", "glass", "tiles", "skeuo",
                   "aurora", "editorial", "brutal", "noir", "blueprint", "clay"],
    },
    "schedule": {
        "timezone": "Asia/Kolkata",
        "times": ["09:00", "18:30"],
        "posts_per_day": 2,
        # One entry per post slot of the day ("format:angle"); the list cycles if shorter.
        "format_plan": {
            "mon": ["carousel:tips", "single:do_dont"],
            "tue": ["single:bold_statement", "checklist:checklist"],
            "wed": ["checklist:quick_tip", "carousel:tips"],
            "thu": ["single:myth_vs_reality", "quote:insight"],
            "fri": ["carousel:breakdown", "single:before_after"],
            "sat": ["quote:reflective", "checklist:checklist"],
            "sun": ["quote:reflective", "single:bold_statement"],
        },
    },
    "content": {
        "no_repeat_days": 30,
        "dev_topic_ratio": 0.0,    # share of posts drawn from `dev: true` categories in topics.yaml
        "language": "English",
        "portfolio": [],           # [{name: ..., description: ...}]
    },
    "ai": {
        "provider": "gemini",
        "fallbacks": ["groq", "ollama"],
        "gemini_model": "gemini-3.6-flash",
        "groq_model": "openai/gpt-oss-120b",
        "ollama_model": "llama3.1",
        "ollama_url": "http://localhost:11434",
        "temperature": 0.9,
    },
    "telegram": {
        "linkedin_url": "https://www.linkedin.com/feed/",
        "text_style": "code",  # "code" = tap-to-copy block, "plain" = normal text
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_dotenv(path: Path = ENV_PATH) -> None:
    """Minimal .env reader. Real environment variables win over the file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and not os.environ.get(key.strip()):
            os.environ[key.strip()] = value


def load_config(path: Path = CONFIG_PATH) -> dict:
    load_dotenv()
    data = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return deep_merge(DEFAULTS, data)


def secret(name: str) -> str:
    return os.environ.get(name, "").strip()


def write_env(values: dict, path: Path = ENV_PATH) -> None:
    lines = ["# Secrets for the content bot. Never commit this file."]
    lines += [f"{k}={v}" for k, v in values.items() if v]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def write_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    header = "# Content bot settings (no secrets here — those live in .env).\n"
    path.write_text(header + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
