"""Event summaries. Default: the feed's own short description, trimmed."""
from __future__ import annotations

import re

_TAILS = [
    re.compile(r"\s*The post .{0,200} appeared first on .{0,100}$", re.I | re.S),
    re.compile(r"\s*(read more|continue reading|devamı için tıklayın|devamını oku|haberin devamı"
               r"|leer más|lire la suite|weiterlesen|saiba mais)\W*$", re.I),
]
_ELLIPSIS = re.compile(r"\s*(\[\s*(\.\.\.|…)\s*\]|\.\.\.|…)\s*$")
_SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")


def default_summary(description: str, max_sentences: int = 4, max_chars: int = 420) -> str:
    text = (description or "").strip()
    for _ in range(2):
        for pat in _TAILS:
            text = pat.sub("", text).strip()
    truncated = bool(_ELLIPSIS.search(text))
    text = _ELLIPSIS.sub("", text).strip()
    if not text:
        return ""
    out = ""
    for sent in _SENT_SPLIT.split(text)[:max_sentences]:
        candidate = f"{out} {sent}".strip()
        if len(candidate) > max_chars:
            break
        out = candidate
    if not out:  # first sentence alone is too long: cut at a word boundary
        cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:—- ")
        return cut + "…"
    return out + "…" if truncated else out
