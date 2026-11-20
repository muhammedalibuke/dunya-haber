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
VERSION = 3  # bump when the stored shape changes: the day's list is then made again
MAX_PEOPLE = 20
MAX_HOLIDAYS = 6
EXTRACT_SENTENCES, EXTRACT_MAX_CHARS = 3, 420
# saints' days fill the holiday list every day; keep observances the whole world can relate to
_SKIP_HOLIDAY = re.compile(r"feast day|liturgical|commemoration|^christian|^eastern orthodox", re.I)  # births/deaths are not curated by Wikipedia: keep the newest with a photo
_WIKI = re.compile(r"^https://[a-z\-]+\.wikipedia\.org/wiki/[^\s\"'<>]+$")
# "…, American songwriter (born 1952)": the years are shown apart, with a dash
_LIFE = re.compile(r"\s*\((born|died|b\.|d\.)\s+([^()]{1,30})\)\s*$", re.I)
_IMG = re.compile(r"^https://upload\.wikimedia\.org/[^\s\"'<>]+$")


def _first(pages: list, key) -> str | None:
    for p in pages or []:
        v = key(p)
        if v:
            return v
    return None


def _sentences(text: str) -> str:
    """Background for "Ne olmuştu?": the first sentences of the article's summary."""
    from .summarize import _SENT_SPLIT

    out = ""
    for sent in _SENT_SPLIT.split(" ".join(text.split()))[:EXTRACT_SENTENCES]:
        if out and len(out) + 1 + len(sent) > EXTRACT_MAX_CHARS:
            break
        out = f"{out} {sent}".strip()
    return out[:EXTRACT_MAX_CHARS]


def _item(raw: dict) -> dict:
    pages = raw.get("pages") or []
    url = _first(pages, lambda p: ((p.get("content_urls") or {}).get("desktop") or {}).get("page"))
    thumb = _first(pages, lambda p: (p.get("thumbnail") or {}).get("source"))
    url = url if url and _WIKI.match(url) else None
    thumb = thumb if thumb and _IMG.match(thumb) else None
    title = _first(pages, lambda p: (p.get("titles") or {}).get("normalized"))
    text = (raw.get("text") or "").strip()
    born = died = None
    m = _LIFE.search(text)
    if m:
        text = text[:m.start()].rstrip(" ,;")
        if m.group(1).lower().startswith("b"):
            born = m.group(2).strip()
        else:
            died = m.group(2).strip()
    extract = _first(pages, lambda p: p.get("extract"))
    return {
        "extract": _sentences(extract) if extract else None,
        "year": int(raw.get("year") or 0),
        "text": text,
        "born": born,
        "died": died,
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
    for items in people.values():  # background is shown for events only: don't spend translation time on it
        for i in items:
            i["extract"] = None
    holidays = [{"text": (r.get("text") or "").strip(), "url": _item(r)["url"]}
                for r in payload.get("holidays") or []
                if r.get("text") and not _SKIP_HOLIDAY.search(r["text"])][:MAX_HOLIDAYS]
    return {"events": events, **people, "holidays": holidays}


def refresh_history(current: dict | None, now: datetime, get_json: Callable[[str], dict],
                    translator, gaz=None) -> dict | None:
    """Today's list, fetched and translated when the Istanbul date changes; otherwise `current`.
    A failed fetch keeps `current`; a failed translation leaves the English text."""
    day = now.astimezone(DAY_ZONE).date()
    if current and current.get("date") == day.isoformat() and current.get("v") == VERSION:
        return current
    try:
        parsed = parse_onthisday(get_json(FEED.format(m=day.month, d=day.day)))
    except Exception as e:  # noqa: BLE001 - a missing day is not worth failing the news update for
        print(f"on this day: fetch failed: {e}", flush=True)
        return current
    cache: dict = {}

    def both(en: str | None) -> dict | None:
        if not en:
            return None
        try:
            tr = translate_cached(en, "en", "tr", cache, translator)
        except Exception:  # noqa: BLE001
            tr = en
        return {"tr": tr or en, "en": en}

    for items in parsed.values():
        for it in items:
            it["text"] = both(it["text"])
            if "extract" in it:
                it["extract"] = both(it["extract"])
    if gaz is not None:  # where it happened, for the map
        from dataclasses import asdict

        from .geo import locate_event

        for it in parsed["events"]:
            loc = locate_event([it["text"]["en"]], [], gaz)
            it["location"] = asdict(loc) if loc else None
    return {"date": day.isoformat(), "v": VERSION, **parsed}
