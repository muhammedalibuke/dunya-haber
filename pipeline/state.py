"""Load, save and prune the pipeline state kept as JSON on the `data` branch."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .models import Article, Event, Location, State

RETENTION = timedelta(days=7)
OPEN_WINDOW = timedelta(hours=48)
SEEN_DAYS = 14
TARGET_LANGS = ("tr", "en")


def epoch_day(dt: datetime) -> int:
    return int(dt.timestamp() // 86400)


def cache_key(text: str, src: str, tgt: str) -> str:
    return hashlib.sha1(f"{src}|{tgt}|{text}".encode()).hexdigest()[:20]


def _enc_vec(v: np.ndarray | None) -> str | None:
    if v is None:
        return None
    return base64.b64encode(np.asarray(v, dtype=np.float16).tobytes()).decode()


def _dec_vec(s: str | None) -> np.ndarray | None:
    if s is None:
        return None
    return np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)


def _article_to_json(a: Article) -> dict:
    d = asdict(a)
    d["published"] = a.published.isoformat()
    return d


def _article_from_json(d: dict) -> Article:
    d = dict(d)
    d["published"] = datetime.fromisoformat(d["published"])
    return Article(**d)


def _event_to_json(e: Event) -> dict:
    return {
        "id": e.id,
        "article_ids": e.article_ids,
        "centroid": _enc_vec(e.centroid),
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
        "topic": e.topic,
        "location": asdict(e.location) if e.location else None,
        "summary_tr": e.summary_tr,
        "summary_en": e.summary_en,
        "summary_ai": e.summary_ai,
        "summary_v": e.summary_v,
    }


def _event_from_json(d: dict) -> Event:
    return Event(
        id=d["id"],
        article_ids=list(d["article_ids"]),
        centroid=_dec_vec(d["centroid"]),
        created_at=datetime.fromisoformat(d["created_at"]),
        updated_at=datetime.fromisoformat(d["updated_at"]),
        topic=d.get("topic", "general"),
        location=Location(**d["location"]) if d.get("location") else None,
        summary_tr=d.get("summary_tr", ""),
        summary_en=d.get("summary_en", ""),
        summary_ai=d.get("summary_ai", False),
        summary_v=d.get("summary_v", 0),
    )


def _read(path: Path, default):
    if not path.exists():
        return default
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def load_state(dir: Path) -> State:
    dir = Path(dir)
    arts = _read(dir / "articles.json.gz", [])
    evs = _read(dir / "events.json.gz", [])
    return State(
        articles={a["id"]: _article_from_json(a) for a in arts},
        events={e["id"]: _event_from_json(e) for e in evs},
        translations=_read(dir / "translations.json.gz", {}),
        seen=_read(dir / "seen.json.gz", {}),
    )


def save_state(state: State, dir: Path) -> None:
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)

    def dump(name, obj):
        with gzip.open(dir / name, "wt", encoding="utf-8", compresslevel=6) as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    dump("articles.json.gz", [_article_to_json(a) for a in state.articles.values()])
    dump("events.json.gz", [_event_to_json(e) for e in state.events.values()])
    dump("translations.json.gz", state.translations)
    dump("seen.json.gz", state.seen)


def prune(state: State, now: datetime) -> None:
    cutoff = now - RETENTION
    closed = now - OPEN_WINDOW
    for eid in list(state.events):
        e = state.events[eid]
        n_sources = len({state.articles[a].source_id for a in e.article_ids if a in state.articles})
        if e.updated_at < cutoff or (e.updated_at < closed and n_sources < 2):
            del state.events[eid]
        elif e.updated_at < closed:
            # closed events can never gain articles again: keep only what the site shows
            e.centroid = None
            for aid in e.article_ids:
                if aid in state.articles:
                    state.articles[aid].description = ""
    keep = {aid for e in state.events.values() for aid in e.article_ids}
    for aid in [aid for aid in state.articles if aid not in keep]:
        del state.articles[aid]
    from .summarize import default_summary

    needed = {
        cache_key(text, a.lang, tgt)
        for a in state.articles.values()
        for text in (a.title, a.description, default_summary(a.description))
        for tgt in TARGET_LANGS
    }
    for k in [k for k in state.translations if k not in needed]:
        del state.translations[k]
    oldest = epoch_day(now) - SEEN_DAYS
    for k in [k for k, d in state.seen.items() if d < oldest]:
        del state.seen[k]
