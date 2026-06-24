"""Utilitaires de normalisation de codes."""

from __future__ import annotations

import re
import unicodedata


def slug_code(value: str | None, max_len: int = 20, prefix: str = "") -> str:
    if not value or not str(value).strip():
        return f"{prefix}INCONNU"[:max_len]
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")
    if prefix:
        text = f"{prefix}{text}"
    if not text:
        text = "INCONNU"
    return text[:max_len]


def text_key(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s.upper() if s else None
