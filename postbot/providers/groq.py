"""Groq free tier (https://console.groq.com/keys) — OpenAI-compatible endpoint."""
from __future__ import annotations

import logging

import requests

from .base import Provider, ProviderError, RateLimitError

log = logging.getLogger("groq")


class GroqProvider(Provider):
    name = "groq"
    URL = "https://api.groq.com/openai/v1/chat/completions"

    PREFERRED = ("openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b")

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self._switched = False

    def _discover(self) -> str | None:
        """Configured model was retired: pick a capable chat model from the account's list."""
        try:
            resp = requests.get("https://api.groq.com/openai/v1/models", timeout=30,
                                headers={"Authorization": f"Bearer {self.api_key}"})
            ids = [m["id"] for m in resp.json().get("data", [])]
        except (requests.RequestException, ValueError, KeyError):
            return None
        for m in self.PREFERRED:
            if m in ids:
                return m
        chat = [m for m in ids if not any(x in m for x in ("whisper", "guard", "orpheus", "tts", "safeguard"))]
        return chat[0] if chat else None

    def available(self) -> bool:
        return bool(self.api_key)

    def generate(self, system: str, user: str, temperature: float = 0.9) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = requests.post(self.URL, json=body, timeout=120,
                                 headers={"Authorization": f"Bearer {self.api_key}"})
        except requests.RequestException as exc:
            raise ProviderError(f"groq network error: {type(exc).__name__}") from None
        if resp.status_code == 429:
            retry = resp.headers.get("retry-after")
            raise RateLimitError("groq rate limit", float(retry) if retry else None)
        if resp.status_code == 404 and not self._switched:
            self._switched = True
            new = self._discover()
            if new and new != self.model:
                log.warning("groq model %s is gone, switching to %s (update ai.groq_model)", self.model, new)
                self.model = new
                return self.generate(system, user, temperature)
        if resp.status_code != 200:
            raise ProviderError(f"groq error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]
