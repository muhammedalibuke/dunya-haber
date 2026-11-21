"""Event importance and the "today" selection (5–10 general events, country-balanced)."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

from .models import Article, Event

FRESHNESS_HOURS = 12
TODAY_WINDOW = timedelta(hours=24)


def score(event: Event, articles: dict[str, Article], now: datetime) -> float:
    sources_by_country: dict[str, set[str]] = defaultdict(set)
    for aid in event.article_ids:
        a = articles.get(aid)
        if a:
            sources_by_country[a.country].add(a.source_id)
    base = sum(1 + math.log2(len(s)) for s in sources_by_country.values())
    age_h = max(0.0, (now - event.updated_at).total_seconds() / 3600)
    return base * math.exp(-age_h / FRESHNESS_HOURS)


def _source_count(event: Event, articles: dict[str, Article]) -> int:
    return len({articles[a].source_id for a in event.article_ids if a in articles})


def select_today(events: dict[str, Event], articles: dict[str, Article], now: datetime,
                 min_n: int = 5, max_n: int = 10, rel_cutoff: float = 0.4,
                 exclude: set[str] | None = None, even: bool = False) -> list[str]:
    """Today's most important stories. `exclude`: shown elsewhere (the featured box).
    `even`: an even number, so the two-column list has no hole: the next story is added,
    or if there is none, the weakest one is left out (a single story stays)."""
    exclude = exclude or set()
    cands = [
        e for e in events.values()
        if e.topic == "general" and e.updated_at >= now - TODAY_WINDOW and _source_count(e, articles) >= 2
        and e.id not in exclude
    ]
    ranked_all = sorted(cands, key=lambda e: (-score(e, articles, now), e.id))
    ranked = ranked_all[:max_n]
    if not ranked:
        return []
    top = score(ranked[0], articles, now)
    keep = [e for i, e in enumerate(ranked) if i < min_n or score(e, articles, now) >= rel_cutoff * top]
    if even and len(keep) % 2:
        if len(keep) < len(ranked_all) and len(keep) < max_n:
            keep.append(ranked_all[len(keep)])
        elif len(keep) > 1:  # a lone story is still shown
            keep.pop()
    return [e.id for e in keep]


FEATURED_MIN_AGE = timedelta(hours=24)  # "günlerdir": first report at least a day ago
FEATURED_ACTIVE = timedelta(hours=6)  # and still developing
FEATURED_MIN_SOURCES = 10


def select_featured(events: dict[str, Event], articles: dict[str, Article], now: datetime) -> str | None:
    """The story that has been in the news for days and is still developing: of those, the one
    the most outlets wrote about in the last 24 hours."""
    best, best_key = None, None
    for e in events.values():
        if (e.topic != "general" or e.created_at > now - FEATURED_MIN_AGE
                or e.updated_at < now - FEATURED_ACTIVE or _source_count(e, articles) < FEATURED_MIN_SOURCES):
            continue
        recent = {articles[a].source_id for a in e.article_ids
                  if a in articles and articles[a].published >= now - TODAY_WINDOW}
        key = (len(recent), e.updated_at, e.id)
        if best_key is None or key > best_key:
            best, best_key = e.id, key
    return best
