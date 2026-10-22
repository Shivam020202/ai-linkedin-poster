"""Common provider interface: every provider turns (system, user) prompts into a JSON string."""
from __future__ import annotations


class ProviderError(Exception):
    pass


class RateLimitError(ProviderError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class Provider:
    name = "base"

    def available(self) -> bool:
        return True

    def generate(self, system: str, user: str, temperature: float = 0.9) -> str:
        raise NotImplementedError
