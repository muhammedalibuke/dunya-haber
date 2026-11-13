"""Event summaries. Default: the feed's own short description, trimmed."""
from __future__ import annotations

import re

import numpy as np

_TAILS = [
    re.compile(r"\s*The post .{0,200} appeared first on .{0,100}$", re.I | re.S),
    re.compile(r"\s*(read more|continue reading|devamı için tıklayın|devamını oku|haberin devamı"
               r"|leer más|lire la suite|weiterlesen|saiba mais)\W*$", re.I),
]
_ELLIPSIS = re.compile(r"\s*(\[\s*(\.\.\.|…)\s*\]|\.\.\.|…)\s*$")
_SENT_SPLIT = re.compile(r"(?:(?<=[.!?。！？])|(?<=[.!?。！？][\"'”’»)]))\s+")
_COMPLETE = re.compile(r"[.!?。！？][\"'”’»)]*$")


def _clean(description: str) -> tuple[str, bool]:
    text = (description or "").strip()
    for _ in range(2):
        for pat in _TAILS:
            text = pat.sub("", text).strip()
    truncated = bool(_ELLIPSIS.search(text))
    return _ELLIPSIS.sub("", text).strip(), truncated


def default_summary(description: str, max_sentences: int = 4, max_chars: int = 420) -> str:
    text, truncated = _clean(description)
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


SUMMARY_VERSION = 3  # bump to rebuild stored summaries once
DUPLICATE_SIM = 0.8


def combined_summary(items: list[tuple[str, str]], embedder, max_sentences: int = 6,
                     max_chars: int = 750) -> list[tuple[str, str]]:
    """Pick sentences from several outlets' descriptions (given in priority order),
    skipping sentences that say the same thing as one already picked (any language)."""
    cands: list[tuple[str, str]] = []
    for lang, desc in items:
        text, _ = _clean(desc)
        cands += [(lang, s.strip()) for s in _SENT_SPLIT.split(text)
                  if len(s.strip()) >= 3 and _COMPLETE.search(s.strip())]  # cut-off fragments dropped
    if not cands:
        return []
    vecs = embedder.encode([s for _, s in cands])
    chosen: list[tuple[str, str]] = []
    kept: list[np.ndarray] = []
    total = 0
    for (lang, sent), v in zip(cands, vecs):
        if any(float(np.dot(v, k)) >= DUPLICATE_SIM for k in kept):
            continue
        if total + len(sent) + 1 > max_chars + 1:
            break
        chosen.append((lang, sent))
        kept.append(v)
        total += len(sent) + 1
        if len(chosen) >= max_sentences:
            break
    return chosen


# ---- optional AI summaries (off unless GEMINI_API_KEY is set) ----

GEMINI_MODEL = "gemini-2.5-flash-lite"  # cheapest model with a free tier
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_TIMEOUT_S = 20

_PROMPT = (
    "You summarize one news event for a calm news reader. Below are headlines and short "
    "descriptions from several outlets about the same event. Write a neutral, factual summary "
    "of 4-5 sentences using only these facts. Return JSON: {{\"tr\": \"<Turkish>\", \"en\": \"<English>\"}}.\n\n"
    "{items}"
)


def gemini_summary(event_titles: list[str], descriptions: list[str], api_key: str,
                   post=None) -> tuple[str, str] | None:
    if post is None:
        import httpx

        post = httpx.post
    items = "\n".join(f"- {t} — {d[:300]}" for t, d in zip(event_titles, descriptions))[:6000]
    body = {
        "contents": [{"parts": [{"text": _PROMPT.format(items=items)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    try:
        r = post(GEMINI_URL.format(model=GEMINI_MODEL), json=body, timeout=GEMINI_TIMEOUT_S,
                 headers={"x-goog-api-key": api_key, "Content-Type": "application/json"})
        if r.status_code != 200:
            return None
        import json

        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        tr, en = str(data["tr"]).strip(), str(data["en"]).strip()
        return (tr, en) if tr and en else None
    except Exception:  # quota, timeout, bad JSON: fall back silently
        return None
