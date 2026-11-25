"""Minimal secret redaction for persisted agent artifacts."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY = re.compile(r"(api[_-]?key|authorization|token|password|secret)", re.IGNORECASE)
_TOKEN_VALUE = re.compile(r"\b(?:sk|rk|ghp|github_pat)_[A-Za-z0-9_-]{12,}\b")
_BEARER_VALUE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~-]{12,}")


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact common credential keys and values before persistence."""
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): redact(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = _TOKEN_VALUE.sub("[REDACTED]", value)
        return _BEARER_VALUE.sub(r"\1[REDACTED]", value)
    return value
