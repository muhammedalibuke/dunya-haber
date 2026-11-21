"""'Tarihte bugün': world events and deaths on today's date, from English Wikipedia's
"On this day" feed. Fetched and translated once a day (Istanbul date); the rest of the day the
stored copy is used."""
from __future__ import annotations

import html as htmllib
import re
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from .translate import translate_cached

FEED = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{m:02d}/{d:02d}"
# quote of the day: each language from its own Wikiquote (not translated)
QUOTE_SOURCES = {
    "tr": ("https://tr.wikiquote.org", "Anasayfa", "Günün Sözü"),
    "en": ("https://en.wikiquote.org", "Main_Page", "Quote of the day"),
}
QUOTE_API = "{base}/w/api.php?action=parse&page={page}&prop=text&redirects=1&format=json&formatversion=2"
QUOTE_MAX_CHARS = 400
# a person's best-known works ("notable work", P800) from Wikidata: a few, not all
WIKIDATA = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids={ids}&props={props}&format=json"
MAX_WORKS = 3
_QID = re.compile(r"^Q\d+$")
QUOTE_RETRY = timedelta(hours=1)
_QUOTE_URL = re.compile(r"^https://[a-z]+\.wikiquote\.org/wiki/[^\s\"'<>]+$")
_AUTHOR_LINE = re.compile(r"^[—–~\-]+\s*")
_MARKS = "“”„\"«»‹›·' "
DAY_ZONE = ZoneInfo("Europe/Istanbul")
VERSION = 9  # bump when the stored shape changes: the day's list is then made again
MAX_PEOPLE = 20  # deaths are not curated by Wikipedia: keep the best known (see pick_people)
MAX_HOLIDAYS = 6
EXTRACT_SENTENCES, EXTRACT_MAX_CHARS = 3, 420
# saints' days fill the holiday list every day; keep observances the whole world can relate to
_SKIP_HOLIDAY = re.compile(r"feast day|liturgical|commemoration|^christian|^eastern orthodox", re.I)
_WIKI = re.compile(r"^https://[a-z\-]+\.wikipedia\.org/wiki/[^\s\"'<>]+$")
# "…, American songwriter (born 1952)": the years are shown apart, with a dash
_LIFE = re.compile(r"\s*\((born|died|b\.?|d\.?)\s+([^()]{1,30})\)\s*$", re.I)
_IMG = re.compile(r"^https://upload\.wikimedia\.org/[^\s\"'<>]+$")


def _first(pages: list, key) -> str | None:
    for p in pages or []:
        v = key(p)
        if v:
            return v
    return None


def _sentences(text: str, n: int = EXTRACT_SENTENCES, max_chars: int = EXTRACT_MAX_CHARS) -> str:
    """Background for "Ne olmuştu?": the first sentences of the article's summary."""
    from .summarize import _SENT_SPLIT

    out = ""
    for sent in _SENT_SPLIT.split(" ".join(text.split()))[:n]:
        if out and len(out) + 1 + len(sent) > max_chars:
            break
        out = f"{out} {sent}".strip()
    return out[:max_chars]


def _item(raw: dict) -> dict:
    pages = raw.get("pages") or []
    url = _first(pages, lambda p: ((p.get("content_urls") or {}).get("desktop") or {}).get("page"))
    thumb = _first(pages, lambda p: (p.get("thumbnail") or {}).get("source"))
    url = url if url and _WIKI.match(url) else None
    thumb = thumb if thumb and _IMG.match(thumb) else None
    title = _first(pages, lambda p: (p.get("titles") or {}).get("normalized"))
    qid = pages[0].get("wikibase_item") if pages else None
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
        "wikidata": qid if qid and _QID.match(qid) else None,
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
    people = {k: newest(i for i in (_item(r) for r in payload.get(k) or [] if r.get("text")) if i["thumb"])
              for k in ("deaths",)}
    for items in people.values():  # background is shown for events only: don't spend translation time on it
        for i in items:
            i["extract"] = None
    holidays = [{"text": (r.get("text") or "").strip(), "url": _item(r)["url"],
                 "extract": _sentences(x, 2, 220) if (x := _first(r.get("pages") or [], lambda p: p.get("extract"))) else None}
                for r in payload.get("holidays") or []
                if r.get("text") and not _SKIP_HOLIDAY.search(r["text"])][:MAX_HOLIDAYS]
    return {"events": events, **people, "holidays": holidays}


def parse_quote(page_html: str, heading: str, base: str) -> dict | None:
    """The quote under `heading` on a Wikiquote main page: {text, author, url}, or None."""
    # the box title is a heading on some wikis and a styled <div> on others: find it as element text
    m = re.search(r">(?:\s|&#32;|&nbsp;|<[^>]+>)*" + re.escape(heading) + r"(?:\s|&#32;|&nbsp;)*<", page_html, re.I)
    if not m:
        return None
    rest = page_html[m.end() - 1:]
    nxt = re.search(r"<h[1-6][\s>]", rest)
    block = rest[:nxt.start() if nxt else 6000][:6000]
    text = re.sub(r"<br\s*/?>|</(p|td|tr|div|li|dd|dt|blockquote)>", "\n", block, flags=re.I)
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [" ".join(line.split()) for line in text.split("\n")]
    lines = [line for line in lines if line]
    author_at = next((i for i, line in enumerate(lines) if _AUTHOR_LINE.match(line)), None)
    if not author_at:
        return None
    quote = " ".join(lines[:author_at]).strip(_MARKS)
    author = _AUTHOR_LINE.sub("", lines[author_at]).strip(" ~—–-")
    if not quote or not author or len(quote) > QUOTE_MAX_CHARS:
        return None
    url = None
    for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
        if " ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", inner)).split()) == author:
            full = href if href.startswith("http") else base + href
            url = full if _QUOTE_URL.match(full) else None
            break
    return {"text": quote, "author": author, "url": url}


def _wikidata(get_json: Callable[[str], dict], ids: list[str], props: str) -> dict:
    out: dict = {}
    for i in range(0, len(ids), 50):  # the API takes 50 ids at a time
        out.update(get_json(WIKIDATA.format(ids="|".join(ids[i:i + 50]), props=props)).get("entities") or {})
    return out


def people_facts(get_json: Callable[[str], dict], qids: list[str]) -> dict[str, dict]:
    """{person qid: {"fame": how many Wikipedias have an article on them,
                     "works": up to MAX_WORKS best-known works as [{tr, en}], in Wikidata's order}}"""
    people = _wikidata(get_json, qids, "claims%7Csitelinks")
    picked: dict[str, list[str]] = {}
    fame: dict[str, int] = {}
    for qid in qids:
        ent = people.get(qid) or {}
        fame[qid] = sum(1 for k in (ent.get("sitelinks") or {}) if k.endswith("wiki"))
        claims = (ent.get("claims") or {}).get("P800") or []
        works = [((c.get("mainsnak") or {}).get("datavalue") or {}).get("value", {}).get("id")
                 for c in claims if c.get("rank") != "deprecated"]
        picked[qid] = [w for w in works if w and _QID.match(w)][:MAX_WORKS]
    all_works = list(dict.fromkeys(w for ws in picked.values() for w in ws))
    labels = _wikidata(get_json, all_works, "labels&languages=en%7Ctr") if all_works else {}
    out = {}
    for qid, works in picked.items():
        named = []
        for w in works:
            lab = (labels.get(w) or {}).get("labels") or {}
            en = (lab.get("en") or {}).get("value")
            if en:
                named.append({"tr": (lab.get("tr") or {}).get("value") or en, "en": en})
        out[qid] = {"fame": fame[qid], "works": named}
    return out


def pick_people(people: list[dict], facts: dict[str, dict]) -> list[dict]:
    """The MAX_PEOPLE best known (by Wikidata) or, without that, the newest; newest first."""
    if facts:
        people = sorted(people, key=lambda d: -(facts.get(d.get("wikidata")) or {}).get("fame", 0))
    kept = people[:MAX_PEOPLE]
    for d in kept:
        d["works"] = (facts.get(d.get("wikidata")) or {}).get("works", [])
    return sorted(kept, key=lambda d: d["year"], reverse=True)


def fetch_quotes(get_json: Callable[[str], dict], skip: set[str] = frozenset()) -> dict:
    out = {}
    for lang, (base, page, heading) in QUOTE_SOURCES.items():
        if lang in skip:
            continue
        try:
            page_html = get_json(QUOTE_API.format(base=base, page=page))["parse"]["text"]
            q = parse_quote(page_html, heading, base)
        except Exception as e:  # noqa: BLE001 - no quote today is fine
            print(f"quote of the day ({lang}): {e}", flush=True)
            continue
        if q:
            out[lang] = q
        else:  # show what the page looks like, to adjust the reader
            at = page_html.lower().find(heading.lower())
            print(f"quote of the day ({lang}): not found; heading at {at}; "
                  f"{page_html[max(0, at - 300):at + 1500] if at >= 0 else page_html[:600]!r}", flush=True)
    return out


def refresh_history(current: dict | None, now: datetime, get_json: Callable[[str], dict],
                    translator, gaz=None) -> dict | None:
    """Today's list, fetched and translated when the Istanbul date changes; otherwise `current`.
    A failed fetch keeps `current`; a failed translation leaves the English text."""
    day = now.astimezone(DAY_ZONE).date()
    if current and current.get("date") == day.isoformat() and current.get("v") == VERSION:
        quote = current.get("quote") or {}
        checked = current.get("quote_checked")
        if all(lang in quote for lang in QUOTE_SOURCES) or (
                checked and now - datetime.fromisoformat(checked) < QUOTE_RETRY):
            return current
        # a quote is missing (site down, page changed): try again hourly, the rest stays as it is
        return {**current, "quote": {**fetch_quotes(get_json, skip=set(quote)), **quote},
                "quote_checked": now.isoformat()}
    try:
        parsed = parse_onthisday(get_json(FEED.format(m=day.month, d=day.day)))
    except Exception as e:  # noqa: BLE001 - a missing day is not worth failing the news update for
        print(f"on this day: fetch failed: {e}", flush=True)
        return current
    # who to show among today's deaths: the best known, with a few of their works
    qids = [d["wikidata"] for d in parsed.get("deaths", []) if d.get("wikidata")]
    try:
        facts = people_facts(get_json, qids) if qids else {}
    except Exception as e:  # noqa: BLE001 - the list is fine without them
        print(f"people facts: {e}", flush=True)
        facts = {}
    parsed["deaths"] = pick_people(parsed.get("deaths", []), facts)

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
    return {"date": day.isoformat(), "v": VERSION, "quote": fetch_quotes(get_json), "quote_checked": now.isoformat(),
            **parsed}
