"""Assign incoming articles to events by cosine similarity to event centroids."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

import numpy as np

from .models import Article, Event

CLUSTER_THRESHOLD = 0.72
OPEN_WINDOW_HOURS = 48
# A wire story (AFP, Reuters, AP…) republished elsewhere under the same headline joins the
# event it already belongs to, open or closed, instead of resurfacing as a new story.
# Shorter headlines ("Morning update", "Here's the latest") are too generic to match on.
MIN_TITLE_WORDS = 5


def title_key(title: str) -> str | None:
    """Headline reduced to lowercase words: punctuation, quotes and spacing don't matter."""
    t = unicodedata.normalize("NFKC", title or "").casefold()
    words = re.findall(r"\w+", t)
    return " ".join(words) if len(words) >= MIN_TITLE_WORDS else None


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return (v / n).astype(np.float32) if n else v.astype(np.float32)


def assign(
    events: dict[str, Event],
    articles: list[Article],
    vectors: np.ndarray,
    now: datetime,
    threshold: float = CLUSTER_THRESHOLD,
    window_hours: int = OPEN_WINDOW_HOURS,
    existing: dict[str, Article] | None = None,
) -> set[str]:
    """`existing`: articles already in events (to recognise republished headlines)."""
    known = {aid for e in events.values() for aid in e.article_ids}
    by_title: dict[str, str] = {}
    for eid, e in sorted(events.items(), key=lambda kv: kv[1].created_at):
        for aid in e.article_ids:
            k = title_key(existing[aid].title) if existing and aid in existing else None
            if k:
                by_title.setdefault(k, eid)
    cutoff = now - timedelta(hours=window_hours)
    open_ids = [eid for eid, e in events.items() if e.updated_at >= cutoff and e.centroid is not None]
    touched: set[str] = set()

    order = sorted(range(len(articles)), key=lambda i: articles[i].published)
    for i in order:
        a, v = articles[i], vectors[i]
        if a.id in known:
            continue
        key = title_key(a.title)
        same_title = by_title.get(key) if key else None
        best_id, best_sim = None, -1.0
        for eid in open_ids:
            sim = float(np.dot(events[eid].centroid, v))
            if sim > best_sim:
                best_id, best_sim = eid, sim
        if same_title is not None:
            best_id, best_sim = same_title, 1.0
        if best_id is not None and best_sim >= threshold:
            e = events[best_id]
            if e.centroid is not None:  # closed events keep no centroid and stay closed to vectors
                n = len(e.article_ids)
                e.centroid = _normalize(e.centroid * n + v)
            e.article_ids.append(a.id)
            e.updated_at = max(e.updated_at, a.published)
            target = best_id
        else:
            target = a.id
            events[target] = Event(target, [a.id], _normalize(v), a.published, a.published)
            open_ids.append(target)
        touched.add(target)
        if key:
            by_title.setdefault(key, target)
        known.add(a.id)
    return touched
