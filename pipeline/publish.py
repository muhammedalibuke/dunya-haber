"""Turn pipeline state into the static JSON the site reads."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from .geo import country_of_event
from .images import upgrade_image_url
from .models import Article, Event, State
from .text import is_garbled

OPEN_WINDOW = timedelta(hours=48)
LATEST_WINDOW = timedelta(hours=3)  # "Son haberler": stories that first appeared this recently
LATEST_MIN = 30  # quiet hours: fill up with older stories
LATEST_MAX = 150
SINGLE_SOURCE_MAX_TIER = 2  # breaking news seen in one outlet is listed only if it's a big one
MAX_SOURCES_SHOWN = 5  # most widely read outlets only; the rest still count toward ranking
MAX_IMAGES = 4
MAX_DEVELOPMENTS = 3
DETAIL_MAX_CHARS = 240
DEVELOPMENT_WINDOW = timedelta(hours=12)


@lru_cache(maxsize=512)
def country_name(code: str) -> dict:
    if not code:
        return {"tr": "", "en": ""}
    from babel import Locale

    return {
        lang: Locale(lang).territories.get(code, code)
        for lang in ("tr", "en")
    }


def _arts(event: Event, articles: dict[str, Article]) -> list[Article]:
    return sorted((articles[a] for a in event.article_ids if a in articles), key=lambda a: a.published)


def lead_article(event: Event, articles: dict[str, Article]) -> Article:
    arts = _arts(event, articles)
    english = [a for a in arts if a.lang == "en"]
    return (english or arts)[0]


def _title(a: Article) -> dict:
    return {"tr": a.title_tr or a.title, "en": a.title_en or a.title}


def _source_rows(arts: list[Article]) -> list[dict]:
    seen, rows = set(), []
    for a in sorted(arts, key=lambda a: (a.source_tier, a.published)):
        if len(rows) >= MAX_SOURCES_SHOWN:
            break
        if a.source_id in seen:
            continue
        seen.add(a.source_id)
        rows.append({
            "name": a.source_name,
            "url": a.url,
            "published": a.published.isoformat(),
            "title": {"orig": a.title, "tr": a.title_tr or a.title, "en": a.title_en or a.title},
        })
    return rows


def _images(arts: list[Article]) -> list[dict]:
    out, sources, urls = [], set(), set()
    for a in sorted(arts, key=lambda a: (a.source_tier, a.published)):
        if not a.image_url or a.source_id in sources or a.image_url in urls:
            continue
        sources.add(a.source_id)
        urls.add(a.image_url)
        out.append({"url": upgrade_image_url(a.image_url), "source": a.source_name, "small": a.image_url})
        if len(out) >= MAX_IMAGES:
            break
    return out


def _location(event: Event) -> dict | None:
    l = event.location
    return {"level": l.level, "name": l.name, "lat": l.lat, "lon": l.lon, "country": l.country} if l else None


def event_summary(event: Event, articles: dict[str, Article]) -> dict:
    arts = _arts(event, articles)
    cc = country_of_event(event.location, [a.country for a in arts])
    return {
        "id": event.id,
        "title": _title(lead_article(event, articles)),
        "country": {"code": cc, "name": country_name(cc)},
        "source_count": len({a.source_id for a in arts}),
        "updated_at": event.updated_at.isoformat(),
        "created_at": event.created_at.isoformat(),
        "topic": event.topic,
        "location": _location(event),
        "thumb": next((i["small"] for i in _images(arts)), None),
    }


def event_detail(event: Event, articles: dict[str, Article]) -> dict:
    arts = _arts(event, articles)
    s = event_summary(event, articles)
    return {
        "id": event.id,
        "title": s["title"],
        "country": s["country"],
        "created_at": event.created_at.isoformat(),
        "updated_at": s["updated_at"],
        "summary": {"tr": event.summary_tr, "en": event.summary_en, "ai": event.summary_ai},
        "images": [{"url": i["url"], "source": i["source"]} for i in _images(arts)],
        "location": s["location"],
        "sources": _source_rows(arts),
        "source_total": s["source_count"],
    }


def _words(title: str) -> set[str]:
    return {w for w in re.findall(r"\w+", title.lower()) if len(w) >= 3}


def developments(event: Event, articles: dict[str, Article], max_n: int = MAX_DEVELOPMENTS) -> list[Article]:
    """Latest news within a story: one per outlet, no near-repeat headlines, widely read outlets
    of the last 12 hours first, then the newest of the rest; shown newest first."""
    arts = sorted(_arts(event, articles), key=lambda a: a.published, reverse=True)
    if not arts:
        return []
    recent = arts[0].published - DEVELOPMENT_WINDOW
    popular = [a for a in arts if a.source_tier <= 2 and a.published >= recent]
    out, sources, seen_words = [], set(), []
    for a in popular + arts:
        if len(out) >= max_n:
            break
        if a.source_id in sources or is_garbled(a.title) or is_garbled(a.title_en):
            continue
        w = _words(a.title_en or a.title)
        if any(w and s and len(w & s) / min(len(w), len(s)) >= 0.5 for s in seen_words):
            continue
        sources.add(a.source_id)
        seen_words.append(w)
        out.append(a)
    return sorted(out, key=lambda a: a.published, reverse=True)


def lead_sentences(text: str, n: int = 2, max_chars: int = DETAIL_MAX_CHARS) -> str:
    from .summarize import _SENT_SPLIT

    out = ""
    for sent in _SENT_SPLIT.split(text.strip())[:n]:
        candidate = f"{out} {sent}".strip()
        if len(candidate) > max_chars:
            break
        out = candidate
    if not out:
        out = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:—- ") + "…"
    return out


def featured_block(event: Event, articles: dict[str, Article], translations: dict, now: datetime) -> dict:
    from .summarize import default_summary
    from .translate import cached_pair

    devs = []
    for a in developments(event, articles):
        text = default_summary(a.description)
        detail = None
        if text:
            tr, en = cached_pair(text, a.lang, translations)
            detail = {"tr": lead_sentences(tr), "en": lead_sentences(en)}
        devs.append({"published": a.published.isoformat(), "source": a.source_name, "url": a.url,
                     "title": _title(a), "detail": detail})
    return {**event_summary(event, articles),
            "days": (now.date() - event.created_at.date()).days + 1,
            "developments": devs}


def listable(event: Event, articles: dict[str, Article], now: datetime) -> bool:
    """Open, and either covered by ≥2 outlets or by one widely read outlet."""
    if event.updated_at < now - OPEN_WINDOW:
        return False
    arts = [articles[a] for a in event.article_ids if a in articles]
    n = len({a.source_id for a in arts})
    return n >= 2 or (n == 1 and min(a.source_tier for a in arts) <= SINGLE_SOURCE_MAX_TIER)


def latest_events(state: State, now: datetime) -> list[Event]:
    cands = [e for e in state.events.values() if listable(e, state.articles, now)]
    cands.sort(key=lambda e: (e.created_at, e.id), reverse=True)
    fresh = [e for e in cands if e.created_at >= now - LATEST_WINDOW]
    if len(fresh) < LATEST_MIN:
        fresh = cands[:LATEST_MIN]
    return fresh[:LATEST_MAX]


def published_events(state: State, today_ids: list[str], now: datetime) -> list[Event]:
    """Every event the site shows (today's list + latest news): the only ones worth translating."""
    out = [state.events[i] for i in today_ids if i in state.events]
    seen = {e.id for e in out}
    return out + [e for e in latest_events(state, now) if e.id not in seen]


def build_site_data(state: State, today_ids: list[str], now: datetime,
                    featured_id: str | None = None) -> dict[str, object]:
    arts = state.articles
    listed = latest_events(state, now)
    featured = state.events.get(featured_id) if featured_id else None
    detail_ids = {e.id for e in listed} | set(today_ids) | ({featured.id} if featured else set())
    stamp = now.isoformat()
    # importance decides WHICH events are in today's list; they are shown newest first.
    # The featured story has its own box, so it is not repeated in the list.
    today = sorted((state.events[i] for i in today_ids if i != featured_id),
                   key=lambda e: (e.updated_at, e.id), reverse=True)
    files: dict[str, object] = {
        "today.json": {"generated_at": stamp,
                       "featured": featured_block(featured, arts, state.translations, now) if featured else None,
                       "events": [event_summary(e, arts) for e in today]},
        "all.json": {"generated_at": stamp, "events": [event_summary(e, arts) for e in listed]},
    }
    for eid in sorted(detail_ids):
        files[f"events/{eid}.json"] = event_detail(state.events[eid], arts)
    return files


def write_site_data(out_dir: Path, files: dict[str, object]) -> None:
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir / "events", ignore_errors=True)
    (out_dir / "events").mkdir(parents=True, exist_ok=True)
    for rel, obj in files.items():
        p = out_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
