"""Turn pipeline state into the static JSON the site reads."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from .geo import country_of_event
from .models import Article, Event, State

OPEN_WINDOW = timedelta(hours=48)
ALL_MAX = 300
MAX_SOURCES_SHOWN = 5  # most widely read outlets only; the rest still count toward ranking
MAX_IMAGES = 4
MIN_SOURCES_ALL = 2


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
        out.append({"url": a.image_url, "source": a.source_name})
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
        "topic": event.topic,
        "location": _location(event),
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
        "images": _images(arts),
        "location": s["location"],
        "sources": _source_rows(arts),
        "source_total": s["source_count"],
    }


def build_site_data(state: State, today_ids: list[str], now: datetime) -> dict[str, object]:
    arts = state.articles
    listed = [
        e for e in state.events.values()
        if e.updated_at >= now - OPEN_WINDOW
        and len({arts[a].source_id for a in e.article_ids if a in arts}) >= MIN_SOURCES_ALL
    ]
    listed.sort(key=lambda e: (e.updated_at, e.id), reverse=True)
    listed = listed[:ALL_MAX]
    detail_ids = {e.id for e in listed} | set(today_ids)
    stamp = now.isoformat()
    files: dict[str, object] = {
        "today.json": {"generated_at": stamp,
                       "events": [event_summary(state.events[i], arts) for i in today_ids]},
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
