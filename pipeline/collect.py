"""Fetch RSS/Atom feeds and turn entries into clean Article records."""
from __future__ import annotations

import calendar
import gzip
import hashlib
import html
import json
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser

from .models import Article, Source

USER_AGENT = "DunyaHaber/1.0 (+https://github.com/muhammedalibuke/dunya-haber)"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 10
FEED_DEADLINE_S = 20  # a slow-drip server may hold a worker at most this long
TRACKING_PARAMS = {"fbclid", "gclid", "ref"}
FUTURE_TOLERANCE = timedelta(minutes=10)

# script/style, and <ul>/<ol> lists (in feed descriptions these are "related stories" links)
_BLOCK_RE = re.compile(r"<(script|style|ul|ol)\b[^>]*>.*?</\1\s*>", re.I | re.S)
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


def safe_http_url(url: str | None, base: str) -> str | None:
    """Resolve against the feed URL; anything that is not http(s) is rejected."""
    if not url:
        return None
    full = urljoin(base, url.strip())
    return full if urlsplit(full).scheme.lower() in ("http", "https") else None


def _image(entry, base: str) -> str | None:
    candidates = []
    for m in entry.get("media_content") or []:
        kind = (m.get("medium") or m.get("type") or "image").lower()
        if kind.startswith("image"):
            candidates.append(m.get("url"))
    candidates += [m.get("url") for m in entry.get("media_thumbnail") or []]
    candidates += [
        link.get("href") for link in entry.get("links") or []
        if link.get("rel") == "enclosure" and (link.get("type") or "").startswith("image/")
    ]
    for c in candidates:
        safe = safe_http_url(c, base)
        if safe:
            return safe
    return None


def parse_feed(content: bytes, source: Source, fetched_at: datetime) -> list[Article]:
    parsed = feedparser.parse(content)
    if not parsed.entries and (parsed.get("bozo") or not parsed.get("version")):
        raise ValueError(f"not a feed: {parsed.get('bozo_exception')!r}")
    out: list[Article] = []
    for e in parsed.entries:
        title = clean_text(e.get("title", ""), max_chars=300)
        link = safe_http_url(e.get("link"), source.url)
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
            image_url=_image(e, source.url),
            tags=[t["term"].strip().lower() for t in e.get("tags") or [] if t.get("term")],
            source_tier=source.tier,
        ))
    return out


class NotModified(Exception):
    """The feed has not changed since the last run (HTTP 304)."""


class ConditionalGetter:
    """HTTP GET with ETag/Last-Modified memory, so unchanged feeds are not downloaded again."""

    def __init__(self, path: Path, client=None, deadline_s: float = FEED_DEADLINE_S):
        import httpx

        self.path = Path(path)
        self.deadline_s = deadline_s
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S, follow_redirects=True,
            limits=httpx.Limits(max_connections=64))
        self.cache: dict[str, dict] = {}
        if self.path.exists():
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                self.cache = json.load(f)

    def __call__(self, url: str) -> bytes:
        start = time.monotonic()
        headers = {}
        known = self.cache.get(url, {})
        if known.get("etag"):
            headers["If-None-Match"] = known["etag"]
        if known.get("last_modified"):
            headers["If-Modified-Since"] = known["last_modified"]
        with self.client.stream("GET", url, headers=headers) as r:
            if r.status_code == 304:
                raise NotModified()
            r.raise_for_status()
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    raise ValueError("feed larger than 5 MB")
                if time.monotonic() - start > self.deadline_s:
                    raise TimeoutError(f"feed slower than {self.deadline_s}s")
            if time.monotonic() - start > self.deadline_s:
                raise TimeoutError(f"feed slower than {self.deadline_s}s")
            validators = {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")}
            if any(validators.values()):
                self.cache[url] = validators
            else:
                self.cache.pop(url, None)
            return bytes(buf)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.path, "wt", encoding="utf-8") as f:
            json.dump(self.cache, f)


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
    workers: int = 32,
) -> tuple[list[Article], dict[str, str]]:
    def one(src: Source):
        try:
            return src, parse_feed(get(src.url), src, now), None
        except NotModified:
            return src, [], None
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
