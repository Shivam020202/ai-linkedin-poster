"""Local Ollama (https://ollama.com) — fully offline fallback."""
from __future__ import annotations

import requests

from .base import Provider, ProviderError


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, url: str, model: str):
        self.url = url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        try:
            return requests.get(f"{self.url}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def generate(self, system: str, user: str, temperature: float = 0.9) -> str:
        body = {
            "model": self.model, "stream": False, "format": "json",
            "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            resp = requests.post(f"{self.url}/api/chat", json=body, timeout=600)
        except requests.RequestException as exc:
            raise ProviderError(f"ollama error: {type(exc).__name__}") from None
        if resp.status_code != 200:
            raise ProviderError(f"ollama error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["message"]["content"]
