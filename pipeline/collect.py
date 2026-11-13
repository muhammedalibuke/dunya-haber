"""Fetch RSS/Atom feeds and turn entries into clean Article records."""
from __future__ import annotations

import calendar
import hashlib
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from .models import Article, Source

USER_AGENT = "DunyaHaber/1.0 (+https://github.com/muhammedalibuke/dunya-haber)"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 15
TRACKING_PARAMS = {"fbclid", "gclid", "ref"}
FUTURE_TOLERANCE = timedelta(minutes=10)

_BLOCK_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme.lower() in ("http", "https") else parts.scheme.lower()
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, parts.netloc.lower(), path, urlencode(query), ""))


def clean_text(text: str, max_chars: int = 600) -> str:
    text = _BLOCK_RE.sub(" ", text or "")
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    # a second pass catches markup that was entity-escaped in the feed
    text = _BLOCK_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars].rstrip()


def article_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _published(entry, fetched_at: datetime) -> datetime:
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    if not st:
        return fetched_at
    dt = datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    if dt > fetched_at + FUTURE_TOLERANCE:
        return fetched_at
    return dt


def _image(entry) -> str | None:
    for m in entry.get("media_content") or []:
        url = m.get("url")
        kind = (m.get("medium") or m.get("type") or "image").lower()
        if url and kind.startswith("image"):
            return url
    for m in entry.get("media_thumbnail") or []:
        if m.get("url"):
            return m["url"]
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and (link.get("type") or "").startswith("image/"):
            return link.get("href")
    return None


def parse_feed(content: bytes, source: Source, fetched_at: datetime) -> list[Article]:
    parsed = feedparser.parse(content)
    if not parsed.entries and (parsed.get("bozo") or not parsed.get("version")):
        raise ValueError(f"not a feed: {parsed.get('bozo_exception')!r}")
    out: list[Article] = []
    for e in parsed.entries:
        title = clean_text(e.get("title", ""), max_chars=300)
        link = e.get("link") or ""
        if not title or not link:
            continue
        url = canonical_url(link)
        out.append(Article(
            id=article_id(url),
            url=url,
            title=title,
            description=clean_text(e.get("summary") or e.get("description") or ""),
            source_id=source.id,
            source_name=source.name,
            country=source.country,
            lang=source.lang,
            published=_published(e, fetched_at),
            image_url=_image(e),
            tags=[t["term"].strip().lower() for t in e.get("tags") or [] if t.get("term")],
        ))
    return out


def http_get(url: str) -> bytes:
    import httpx

    headers = {"User-Agent": USER_AGENT}
    with httpx.stream("GET", url, headers=headers, timeout=TIMEOUT_S, follow_redirects=True) as r:
        r.raise_for_status()
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                raise ValueError("feed larger than 5 MB")
        return bytes(buf)


def fetch_all(
    sources: list[Source],
    get: Callable[[str], bytes],
    now: datetime,
    workers: int = 16,
) -> tuple[list[Article], dict[str, str]]:
    def one(src: Source):
        try:
            return src, parse_feed(get(src.url), src, now), None
        except Exception as exc:  # one bad feed must never stop the run
            return src, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, sources))

    articles: dict[str, Article] = {}
    failures: dict[str, str] = {}
    for src, arts, err in results:
        if err:
            failures[src.id] = err
        for a in arts:
            articles.setdefault(a.id, a)
    return list(articles.values()), failures
