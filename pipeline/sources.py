"""Load and validate the feed list in config/sources.yaml."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from .models import REGIONS, Source

FIELDS = ("id", "name", "url", "country", "lang", "region")


@lru_cache(maxsize=1)
def country_codes() -> frozenset[str]:
    import geonamescache

    return frozenset(geonamescache.GeonamesCache().get_countries())


def load_sources(path: Path) -> list[Source]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    out: list[Source] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for entry in raw:
        sid = str(entry.get("id", "?"))
        missing = [f for f in FIELDS if not entry.get(f)]
        if missing:
            raise ValueError(f"source {sid}: missing {missing}")
        s = Source(**{f: str(entry[f]).strip() for f in FIELDS}, tier=entry.get("tier", 3))
        if s.tier not in (1, 2, 3):
            raise ValueError(f"source {sid}: tier must be 1, 2 or 3")
        if s.country not in country_codes():
            raise ValueError(f"source {sid}: unknown country {s.country!r}")
        if not re.fullmatch(r"[a-z]{2}", s.lang):
            raise ValueError(f"source {sid}: lang must be ISO-639-1, got {s.lang!r}")
        if s.region not in REGIONS:
            raise ValueError(f"source {sid}: unknown region {s.region!r}")
        if not s.url.startswith(("http://", "https://")):
            raise ValueError(f"source {sid}: url must be http(s)")
        if s.id in seen_ids or s.url in seen_urls:
            raise ValueError(f"source {sid}: duplicate id or url")
        seen_ids.add(s.id)
        seen_urls.add(s.url)
        out.append(s)
    return out
