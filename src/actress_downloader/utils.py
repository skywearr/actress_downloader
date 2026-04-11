from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")
_NON_TAG_CHAR_RE = re.compile(r"[^\w\u4e00-\u9fff\-:]+", re.UNICODE)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    return _WHITESPACE_RE.sub(" ", normalized)


def normalize_tag(value: str) -> str:
    normalized = normalize_text(value).replace(" ", "-")
    cleaned = _NON_TAG_CHAR_RE.sub("-", normalized)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def extract_year(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"(?P<year>\d{4})", value)
    if match:
        return match.group("year")
    return None
