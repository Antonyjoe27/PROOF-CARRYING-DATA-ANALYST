"""Classification of LLM API failures. Stdlib only, so it is importable (and testable) without the SDK.

Only TEMPORARY availability failures (HTTP 503 / "unavailable" / "high demand") may trigger a fallback model, and only if
OPENROUTER_FALLBACK_MODELS is configured. Bad credentials, credits, bad requests, rate limits and malformed output never fall back.
"""
from __future__ import annotations

import re

UNAVAILABLE = "unavailable"        # 503 -> eligible for fallback
AUTH = "auth"                      # 401/402/403 -> never fall back
BAD_REQUEST = "bad_request"        # 400/404/422 -> never fall back
OTHER = "other"                    # anything else (network, rate limit, ...) -> never fall back

USER_UNAVAILABLE_MSG = "AI service is temporarily unavailable. Please retry."
USER_FALLBACK_MSG = "The AI model is temporarily unavailable. Trying a fallback model..."


class AIServiceUnavailable(Exception):
    """Every configured model returned a temporary availability error. No code ever ran; nothing was verified."""

    def __init__(self, attempts=None):
        super().__init__(USER_UNAVAILABLE_MSG)
        self.attempts = list(attempts or [])


class LLMRequestError(Exception):
    """Non-retryable LLM failure (auth / bad request / other). Carries a safe, secret-free description."""

    def __init__(self, kind: str, http_status: int | None, error_type: str):
        super().__init__(f"AI request failed ({kind}, HTTP {http_status or 'n/a'}, {error_type})")
        self.kind, self.http_status, self.error_type = kind, http_status, error_type


def http_status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "code"):
        v = getattr(exc, attr, None)
        if isinstance(v, int) and 100 <= v <= 599:
            return v
    m = re.search(r"\b([45]\d\d)\b", str(exc)[:120])
    return int(m.group(1)) if m else None


def classify(exc: BaseException) -> tuple[str, int | None]:
    """-> (kind, http_status). Only the status and error class are ever surfaced, never the message."""
    status = http_status_of(exc)
    text = str(exc).lower()
    if status == 503 or "unavailable" in text[:200] or "high demand" in text[:300]:
        return UNAVAILABLE, status or 503
    if status in (401, 402, 403) or "api key" in text[:300]:
        return AUTH, status
    if status in (400, 404, 422):
        return BAD_REQUEST, status
    return OTHER, status
