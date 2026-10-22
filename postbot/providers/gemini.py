"""Google Gemini (free tier key from https://aistudio.google.com/apikey)."""
from __future__ import annotations

import logging
import re

import requests

from .base import Provider, ProviderError, RateLimitError

log = logging.getLogger("gemini")
API = "https://generativelanguage.googleapis.com/v1beta"


def list_models(api_key: str) -> list[str]:
    resp = requests.get(f"{API}/models", params={"pageSize": 200},
                        headers={"x-goog-api-key": api_key}, timeout=30)
    if resp.status_code != 200:
        raise ProviderError(f"Gemini rejected the key ({resp.status_code}): {_error_text(resp)}")
    return [m["name"].split("/", 1)[1] for m in resp.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def rank_models(models: list[str], preferred: str = "") -> list[str]:
    """Text models to try, best first: preferred, stable 'X.Y-flash' newest first, aliases, then lite."""
    stable, lite = [], []
    for m in models:
        match = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash(-lite)?", m)
        if match:
            (lite if match.group(2) else stable).append((float(match.group(1)), m))
    ranked = [m for _, m in sorted(stable, reverse=True)]
    ranked += [m for m in ("gemini-flash-latest",) if m in models]
    ranked += [m for _, m in sorted(lite, reverse=True)]
    if preferred in models:
        ranked = [preferred] + [m for m in ranked if m != preferred]
    return ranked


def pick_model(models: list[str], preferred: str = "") -> str:
    ranked = rank_models(models, preferred)
    if not ranked:
        raise ProviderError("No suitable Gemini text model available for this key.")
    return ranked[0]


def _error_text(resp: requests.Response) -> str:
    try:
        return resp.json().get("error", {}).get("message", "")[:300]
    except ValueError:
        return resp.text[:300]


class GeminiProvider(Provider):
    """Tries the configured model first; if it's retired, overloaded or rate-limited, moves on to
    other Flash models (free-tier quotas are per model, so this also stretches the free quota)."""
    name = "gemini"
    MAX_MODELS = 4

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._candidates: list[str] | None = None
        self._dead: set[str] = set()   # retired for this key (404)

    def available(self) -> bool:
        return bool(self.api_key)

    def _models(self) -> list[str]:
        if self._candidates is None:
            try:
                self._candidates = rank_models(list_models(self.api_key), self.model)
            except ProviderError as exc:
                log.warning("could not list models: %s", exc)
                self._candidates = [self.model]
        return [m for m in self._candidates if m not in self._dead][:self.MAX_MODELS]

    def generate(self, system: str, user: str, temperature: float = 0.9) -> str:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        busy, retry_after = [], None
        for model in [self.model] + [m for m in self._models() if m != self.model]:
            if model in self._dead:
                continue
            try:
                resp = requests.post(f"{API}/models/{model}:generateContent", json=body,
                                     headers={"x-goog-api-key": self.api_key}, timeout=120)
            except requests.RequestException as exc:
                raise ProviderError(f"gemini network error: {type(exc).__name__}") from None
            if resp.status_code == 404:
                log.warning("model %s is not available (%s) — trying another", model, _error_text(resp)[:80])
                self._dead.add(model)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                match = re.search(r'"retryDelay":\s*"(\d+)', resp.text)
                if match:
                    retry_after = min(retry_after or 1e9, float(match.group(1)))
                busy.append(f"{model} {resp.status_code}")
                log.info("%s busy (%s) — trying another model", model, resp.status_code)
                continue
            if resp.status_code != 200:
                raise ProviderError(f"gemini error {resp.status_code}: {_error_text(resp)}")
            if model != self.model:
                log.info("using %s (set ai.gemini_model in config.yaml to make it the default)", model)
                self.model = model  # stick with what works for the rest of this run
            data = resp.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError):
                raise ProviderError(f"gemini returned no content: {str(data)[:300]}") from None
            return "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if busy:
            raise RateLimitError("gemini busy/rate-limited: " + ", ".join(busy), retry_after or 15)
        raise ProviderError("no working Gemini model for this key")
