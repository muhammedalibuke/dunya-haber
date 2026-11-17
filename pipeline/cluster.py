"""Assign incoming articles to events by cosine similarity to event centroids."""
from __future__ import annotations

from datetime import datetime, timedelta

import math
import re

import numpy as np

from .models import Article, Event

CLUSTER_THRESHOLD = 0.72
CLUSTER_LOW = 0.55  # borderline band [0.55, 0.72): merged only with a shared rare name
CORE_NAME_SHARE = 0.25  # an event's own names: those in at least this share of its articles
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
    low: float | None = None,
    rescue=None,
) -> set[str]:
    """Join each article to the closest open event if similar enough (>= threshold), or if it is
    borderline (>= low) and `rescue(article, event)` confirms it (e.g. a shared rare name)."""
    known = {aid for e in events.values() for aid in e.article_ids}
    cutoff = now - timedelta(hours=window_hours)
    open_ids = [eid for eid, e in events.items() if e.updated_at >= cutoff and e.centroid is not None]
    touched: set[str] = set()
    # centroids of open events as one matrix (room for one new event per article): one product
    # per article instead of a Python loop over thousands of events
    dim = vectors.shape[1] if len(vectors) else 0
    mat = np.zeros((len(open_ids) + len(articles), dim), dtype=np.float32)
    for row, eid in enumerate(open_ids):
        mat[row] = events[eid].centroid
    rows = len(open_ids)

    order = sorted(range(len(articles)), key=lambda i: articles[i].published)
    for i in order:
        a, v = articles[i], vectors[i]
        if a.id in known:
            continue
        sims = mat[:rows] @ v
        ranked = np.argsort(-sims, kind="stable")
        best = None
        if rows and sims[ranked[0]] >= threshold:
            best = int(ranked[0])
        elif rescue is not None and low is not None:
            for r in ranked:
                if sims[r] < low:
                    break
                if rescue(a, events[open_ids[r]]):
                    best = int(r)
                    break
        if best is not None:
            e = events[open_ids[best]]
            n = len(e.article_ids)
            e.centroid = _normalize(e.centroid * n + v)
            mat[best] = e.centroid
            e.article_ids.append(a.id)
            e.updated_at = max(e.updated_at, a.published)
            touched.add(e.id)
        else:
            eid = a.id
            events[eid] = Event(eid, [a.id], _normalize(v), a.published, a.published)
            open_ids.append(eid)
            mat[rows] = events[eid].centroid
            rows += 1
            touched.add(eid)
        known.add(a.id)
    return touched


_WORD = re.compile(r"[^\W\d_][\w'’\-]*", re.UNICODE)


def name_tokens(text: str) -> list[str]:
    """Name-like words (Capitalized, ≥4 letters) and acronyms (≥3 capitals), folded for matching."""
    from .geo import fold

    out = []
    for w in _WORD.findall(text or ""):
        w = re.split(r"['’]", w, maxsplit=1)[0].strip("-")
        if not w or not w[0].isupper():
            continue
        if len(w) >= 4 or (len(w) >= 3 and w.isupper()):
            out.append(fold(w))
    return out


class NameRescue:
    """Confirms borderline matches by a shared name that occurs in only a few events
    (e.g. "Ronaldinho", "Depardieu", "NYPD"); common names like "Trump" do not count."""

    def __init__(self, articles: dict, events: dict, max_events: int = 10):
        self.articles = articles
        self.max_events = max_events
        self._cache: dict[str, tuple[int, set[str]]] = {}
        self.df: dict[str, int] = {}
        for e in events.values():
            for t in self.event_names(e):
                self.df[t] = self.df.get(t, 0) + 1

    @staticmethod
    def article_names(a) -> set[str]:
        return set(name_tokens(a.title + " " + a.description[:200]))

    def event_names(self, e) -> set[str]:
        """Names the event is about: in at least CORE_NAME_SHARE of its articles. A name from one
        article out of many says nothing about the event (and would let it match everything)."""
        hit = self._cache.get(e.id)
        if hit and hit[0] == len(e.article_ids):
            return hit[1]
        counts: dict[str, int] = {}
        n = 0
        for aid in e.article_ids:
            if aid in self.articles:
                n += 1
                for t in self.article_names(self.articles[aid]):
                    counts[t] = counts.get(t, 0) + 1
        need = max(1, math.ceil(CORE_NAME_SHARE * n))
        names = {t for t, c in counts.items() if c >= need}
        self._cache[e.id] = (len(e.article_ids), names)
        return names

    def _rare(self, names: set[str]) -> bool:
        return any(self.df.get(t, 0) <= self.max_events for t in names)

    def __call__(self, article, event) -> bool:
        return self._rare(self.article_names(article) & self.event_names(event))

    def events_share(self, a, b) -> bool:
        return self._rare(self.event_names(a) & self.event_names(b))


def merge_events(events: dict[str, Event], touched: set[str], now: datetime,
                 threshold: float = CLUSTER_THRESHOLD, low: float | None = None, rescue=None,
                 window_hours: int = OPEN_WINDOW_HOURS) -> dict[str, str]:
    """Merge events that turned out to be the same story (split earlier). The older event keeps
    its id. Returns {merged_away_id: kept_id}."""
    cutoff = now - timedelta(hours=window_hours)
    merged: dict[str, str] = {}
    ids = [oid for oid, o in events.items() if o.centroid is not None and o.updated_at >= cutoff]
    if not ids:
        return merged
    row_of = {oid: r for r, oid in enumerate(ids)}
    mat = np.stack([events[oid].centroid for oid in ids]).astype(np.float32)
    alive = np.ones(len(ids), dtype=bool)
    for eid in sorted(touched):
        if eid not in events or events[eid].centroid is None:
            continue
        e = events[eid]
        sims = np.where(alive, mat @ e.centroid, -np.inf)
        if eid in row_of:
            sims[row_of[eid]] = -np.inf
        ranked = np.argsort(-sims, kind="stable")
        best = None
        if sims[ranked[0]] >= threshold:
            best = ids[ranked[0]]
        elif low is not None and rescue is not None:
            for r in ranked:
                if sims[r] < low:
                    break
                if rescue.events_share(e, events[ids[r]]):
                    best = ids[r]
                    break
        if best is None:
            continue
        keep, gone = sorted((e, events[best]), key=lambda x: (x.created_at, x.id))
        n1, n2 = len(keep.article_ids), len(gone.article_ids)
        keep.centroid = _normalize(keep.centroid * n1 + gone.centroid * n2)
        keep.article_ids += [a for a in gone.article_ids if a not in keep.article_ids]
        keep.updated_at = max(keep.updated_at, gone.updated_at)
        keep.created_at = min(keep.created_at, gone.created_at)
        del events[gone.id]
        if keep.id in row_of:
            mat[row_of[keep.id]] = keep.centroid
        if gone.id in row_of:
            alive[row_of[gone.id]] = False
        for k, v in merged.items():  # earlier merges into `gone` now live on in `keep`
            if v == gone.id:
                merged[k] = keep.id
        merged[gone.id] = keep.id
    return merged
