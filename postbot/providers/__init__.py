"""Provider chain: primary provider first, then fallbacks, with backoff on rate limits."""
from __future__ import annotations

import logging
import time

from ..config import secret
from .base import Provider, ProviderError, RateLimitError
from .gemini import GeminiProvider
from .groq import GroqProvider
from .ollama import OllamaProvider

log = logging.getLogger("providers")


def build_provider(name: str, ai_cfg: dict) -> Provider:
    if name == "gemini":
        return GeminiProvider(secret("GEMINI_API_KEY"), ai_cfg["gemini_model"])
    if name == "groq":
        return GroqProvider(secret("GROQ_API_KEY"), ai_cfg["groq_model"])
    if name == "ollama":
        return OllamaProvider(ai_cfg["ollama_url"], ai_cfg["ollama_model"])
    raise ValueError(f"unknown provider {name!r}")


class ProviderChain:
    def __init__(self, ai_cfg: dict, providers: list[Provider] | None = None,
                 attempts: int = 3, max_wait: float = 65, sleep=time.sleep):
        if providers is None:
            names = [ai_cfg["provider"]] + [n for n in ai_cfg.get("fallbacks", []) if n != ai_cfg["provider"]]
            providers = [build_provider(n, ai_cfg) for n in names]
        self.providers = providers
        self.temperature = ai_cfg.get("temperature", 0.9)
        self.attempts = attempts
        self.max_wait = max_wait
        self.sleep = sleep

    def generate(self, system: str, user: str) -> str:
        errors = []
        for provider in self.providers:
            if not provider.available():
                continue
            delay = 5.0
            for attempt in range(1, self.attempts + 1):
                try:
                    return provider.generate(system, user, self.temperature)
                except RateLimitError as exc:
                    wait = min(exc.retry_after or delay, self.max_wait)
                    log.warning("%s: %s — retry %d/%d in %.0fs", provider.name, exc, attempt, self.attempts, wait)
                    errors.append(f"{provider.name}: {exc}")
                    if attempt < self.attempts:
                        self.sleep(wait)
                        delay *= 2
                except ProviderError as exc:
                    log.warning("%s failed: %s", provider.name, exc)
                    errors.append(f"{provider.name}: {exc}")
                    break
        if not errors:
            raise ProviderError("No AI provider is configured — add GEMINI_API_KEY via `python setup.py`.")
        raise ProviderError("All AI providers failed: " + " | ".join(errors[-3:]))


__all__ = ["ProviderChain", "ProviderError", "RateLimitError", "build_provider"]
