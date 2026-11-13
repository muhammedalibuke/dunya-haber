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
                 min_n: int = 5, max_n: int = 10, rel_cutoff: float = 0.4) -> list[str]:
    cands = [
        e for e in events.values()
        if e.topic == "general" and e.updated_at >= now - TODAY_WINDOW and _source_count(e, articles) >= 2
    ]
    ranked = sorted(cands, key=lambda e: (-score(e, articles, now), e.id))[:max_n]
    if not ranked:
        return []
    top = score(ranked[0], articles, now)
    keep = [e for i, e in enumerate(ranked) if i < min_n or score(e, articles, now) >= rel_cutoff * top]
    return [e.id for e in keep]
