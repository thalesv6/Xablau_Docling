from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable


_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s\-/&\.]", flags=re.UNICODE)


def stable_short_hash(text: str, length: int = 12) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return h[:length]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = _WS_RE.sub(" ", text)
    return text


def normalize_for_match(text: str) -> str:
    text = normalize_text(text)
    text = text.casefold()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def useful_char_count(texts: Iterable[str]) -> int:
    total = 0
    for t in texts:
        t = normalize_text(t)
        total += sum(1 for ch in t if ch.isalnum())
    return total


