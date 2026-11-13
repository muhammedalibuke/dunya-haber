"""Load, save and prune the pipeline state kept as JSON on the `data` branch."""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .models import Article, Event, Location, State

RETENTION = timedelta(days=7)
TARGET_LANGS = ("tr", "en")


def cache_key(text: str, src: str, tgt: str) -> str:
    return hashlib.sha1(f"{src}|{tgt}|{text}".encode()).hexdigest()[:20]


def _enc_vec(v: np.ndarray) -> str:
    return base64.b64encode(np.asarray(v, dtype=np.float16).tobytes()).decode()


def _dec_vec(s: str) -> np.ndarray:
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
    )


def _read(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(dir: Path) -> State:
    dir = Path(dir)
    arts = _read(dir / "articles.json", [])
    evs = _read(dir / "events.json", [])
    trs = _read(dir / "translations.json", {})
    return State(
        articles={a["id"]: _article_from_json(a) for a in arts},
        events={e["id"]: _event_from_json(e) for e in evs},
        translations=trs,
    )


def save_state(state: State, dir: Path) -> None:
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)

    def dump(name, obj):
        (dir / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    dump("articles.json", [_article_to_json(a) for a in state.articles.values()])
    dump("events.json", [_event_to_json(e) for e in state.events.values()])
    dump("translations.json", state.translations)


def prune(state: State, now: datetime) -> None:
    cutoff = now - RETENTION
    for eid in [eid for eid, e in state.events.items() if e.updated_at < cutoff]:
        del state.events[eid]
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
