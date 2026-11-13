"""Assign incoming articles to events by cosine similarity to event centroids."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from .models import Article, Event

CLUSTER_THRESHOLD = 0.72
OPEN_WINDOW_HOURS = 48


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
) -> set[str]:
    known = {aid for e in events.values() for aid in e.article_ids}
    cutoff = now - timedelta(hours=window_hours)
    open_ids = [eid for eid, e in events.items() if e.updated_at >= cutoff]
    touched: set[str] = set()

    order = sorted(range(len(articles)), key=lambda i: articles[i].published)
    for i in order:
        a, v = articles[i], vectors[i]
        if a.id in known:
            continue
        best_id, best_sim = None, -1.0
        for eid in open_ids:
            sim = float(np.dot(events[eid].centroid, v))
            if sim > best_sim:
                best_id, best_sim = eid, sim
        if best_id is not None and best_sim >= threshold:
            e = events[best_id]
            n = len(e.article_ids)
            e.centroid = _normalize(e.centroid * n + v)
            e.article_ids.append(a.id)
            e.updated_at = max(e.updated_at, a.published)
            touched.add(best_id)
        else:
            eid = a.id
            events[eid] = Event(eid, [a.id], _normalize(v), a.published, a.published)
            open_ids.append(eid)
            touched.add(eid)
        known.add(a.id)
    return touched
