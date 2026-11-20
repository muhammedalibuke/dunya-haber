"""'Tarihte bugün': world events, births and deaths on today's date, from English Wikipedia's
"On this day" feed. Fetched and translated once a day (Istanbul date); the rest of the day the
stored copy is used."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from .translate import translate_cached

FEED = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{m:02d}/{d:02d}"
DAY_ZONE = ZoneInfo("Europe/Istanbul")
MAX_PEOPLE = 20  # births/deaths are not curated by Wikipedia: keep the newest with a photo
_WIKI = re.compile(r"^https://[a-z\-]+\.wikipedia\.org/wiki/[^\s\"'<>]+$")
_IMG = re.compile(r"^https://upload\.wikimedia\.org/[^\s\"'<>]+$")


def _first(pages: list, key) -> str | None:
    for p in pages or []:
        v = key(p)
        if v:
            return v
    return None


def _item(raw: dict) -> dict:
    pages = raw.get("pages") or []
    url = _first(pages, lambda p: ((p.get("content_urls") or {}).get("desktop") or {}).get("page"))
    thumb = _first(pages, lambda p: (p.get("thumbnail") or {}).get("source"))
    url = url if url and _WIKI.match(url) else None
    thumb = thumb if thumb and _IMG.match(thumb) else None
    title = _first(pages, lambda p: (p.get("titles") or {}).get("normalized"))
    return {
        "year": int(raw.get("year") or 0),
        "text": (raw.get("text") or "").strip(),
        "title": title,
        "url": url,
        "thumb": thumb,
        # Wikipedia thumbnails can be asked for at any width: a sharper one for the big photo
        "image": re.sub(r"/\d+px-", "/960px-", thumb) if thumb else None,
    }


def parse_onthisday(payload: dict) -> dict:
    def newest(items):
        return sorted(items, key=lambda x: x["year"], reverse=True)

    events = newest(_item(r) for r in payload.get("selected") or [] if r.get("text"))
    people = {k: newest(i for i in (_item(r) for r in payload.get(k) or [] if r.get("text")) if i["thumb"])[:MAX_PEOPLE]
              for k in ("births", "deaths")}
    return {"events": events, **people}


def refresh_history(current: dict | None, now: datetime, get_json: Callable[[str], dict],
                    translator) -> dict | None:
    """Today's list, fetched and translated when the Istanbul date changes; otherwise `current`.
    A failed fetch keeps `current`; a failed translation leaves the English text."""
    day = now.astimezone(DAY_ZONE).date()
    if current and current.get("date") == day.isoformat():
        return current
    try:
        parsed = parse_onthisday(get_json(FEED.format(m=day.month, d=day.day)))
    except Exception as e:  # noqa: BLE001 - a missing day is not worth failing the news update for
        print(f"on this day: fetch failed: {e}", flush=True)
        return current
    cache: dict = {}
    for items in parsed.values():
        for it in items:
            en = it["text"]
            try:
                tr = translate_cached(en, "en", "tr", cache, translator)
            except Exception:  # noqa: BLE001
                tr = en
            it["text"] = {"tr": tr or en, "en": en}
    return {"date": day.isoformat(), **parsed}
