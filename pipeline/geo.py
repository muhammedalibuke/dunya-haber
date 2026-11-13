"""Offline place lookup: find where an event happened from its titles.

Rule of thumb from the spec: a wrong red point is worse than a coarse one.
Ambiguous names fall back to country level, or to no location at all.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .models import Location

LEVEL_RANK = {"city": 3, "region": 2, "country": 1}
MAX_WORDS = 4
_TOKEN_RE = re.compile(r"[^\W\d_][\w'’.\-]*", re.UNICODE)


@dataclass(frozen=True)
class Place:
    name: str
    level: Literal["city", "region", "country"]
    lat: float
    lon: float
    country: str
    population: int = 0


def _norm_token(tok: str) -> str:
    tok = re.split(r"['’]", tok, maxsplit=1)[0]
    return tok.rstrip(".-")


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ı", "i").replace("İ", "I"))
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _key(name: str) -> str:
    """Index key for a gazetteer name. Apostrophes are kept, so "Smith's" never equals "Smith"."""
    return fold(" ".join(t.rstrip(".") for t in name.split()))


class Gazetteer:
    def __init__(self, entries: list[Place], stoplist: set[str]):
        self.index: dict[str, list[Place]] = defaultdict(list)
        self.countries: dict[str, Place] = {}
        for p in entries:
            k = _key(p.name)
            if len(k) < 4 and p.level != "country":
                continue
            if p not in self.index[k]:
                self.index[k].append(p)
            if p.level == "country":
                self.countries.setdefault(p.country, p)
        self.stop = {s.lower() for s in stoplist}

    @classmethod
    def from_entries(cls, entries: list[Place], stoplist: set[str] | None = None) -> "Gazetteer":
        return cls(entries, stoplist or set())

    @classmethod
    def load(cls, path: Path, stoplist: Path) -> "Gazetteer":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            raw = json.load(f)
        entries = [Place(n, lv, la, lo, cc, pop) for n, lv, la, lo, cc, pop in raw["places"]]
        stop = {
            line.strip().lower()
            for line in Path(stoplist).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        g = cls(entries, stop)
        for cc, name in raw.get("country_names", {}).items():
            match = [p for p in g.index.get(_key(name), []) if p.level == "country" and p.country == cc]
            if match:
                g.countries[cc] = match[0]
        return g

    def find(self, text: str) -> list[list[Place]]:
        tokens = [_norm_token(t) for t in _TOKEN_RE.findall(text)]
        tokens = [t for t in tokens if t]
        out: list[list[Place]] = []
        i = 0
        while i < len(tokens):
            if not tokens[i][0].isupper():
                i += 1
                continue
            for n in range(min(MAX_WORDS, len(tokens) - i), 0, -1):
                key = fold(" ".join(tokens[i:i + n]))
                if key in self.index and key not in self.stop:
                    out.append(list(self.index[key]))
                    i += n
                    break
            else:
                i += 1
        return out


def _majority(countries: list[str]) -> str | None:
    if not countries:
        return None
    cc, n = Counter(countries).most_common(1)[0]
    return cc if n / len(countries) > 0.5 else None


def _km(a: Place, b: Place) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _colocated(ps: list[Place], max_km: float = 200) -> bool:
    return all(_km(a, b) <= max_km for a in ps for b in ps)


def _collapse_per_country(cands: list[Place], gaz: "Gazetteer") -> list[Place]:
    """One candidate per country. Same-level duplicates keep the most populous.
    Mixed levels: a city with its eponymous region (Budapest) stays the city; if the
    name is also a country-level name there (Gaza, Mexico) it becomes the country."""
    by_cc: dict[str, list[Place]] = defaultdict(list)
    for p in cands:
        by_cc[p.country].append(p)
    out = []
    for cc, ps in by_cc.items():
        levels = {p.level for p in ps}
        if len(levels) == 1:
            out.append(max(ps, key=lambda p: p.population))
        elif "country" not in levels and "city" in levels and _colocated(ps):
            out.append(max((p for p in ps if p.level == "city"), key=lambda p: p.population))
        else:
            out.append(gaz.countries.get(cc) or max(ps, key=lambda p: LEVEL_RANK[p.level]))
    return out


SALIENT_POP = 1_000_000
SALIENT_REGION_COUNTRIES = {"US"}  # US states are named constantly in world news


def _salient(p: Place) -> bool:
    return (p.level == "country" or p.population >= SALIENT_POP
            or (p.level == "region" and p.country in SALIENT_REGION_COUNTRIES))


def locate_event(titles: list[str], source_countries: list[str], gaz: Gazetteer) -> Location | None:
    found = [(ti, cands) for ti, t in enumerate(titles) for cands in gaz.find(t)]
    matches = [cands for _, cands in found]
    if not matches:
        return None
    context = {c[0].country for c in matches if len(c) == 1}
    fallback = _majority(source_countries)

    resolved: list[Place] = []
    unresolved: list[list[Place]] = []
    title_hits: dict[Place, set[int]] = defaultdict(set)
    for ti, cands in found:
        cands = _collapse_per_country(cands, gaz)
        if len(cands) > 1:
            pool = [p for p in cands if p.country in context] if context else []
            if not pool and fallback:
                pool = [p for p in cands if p.country == fallback]
            if not pool:
                pool = [p for p in cands if _salient(p)]
            cands = pool if len(pool) == 1 else cands
        if len(cands) == 1:
            resolved.append(cands[0])
            title_hits[cands[0]].add(ti)
        else:
            unresolved.append(cands)

    # A city/region needs corroboration: a named country, the sources' country, a big
    # population, or several headlines. Otherwise it is likely a surname or a common word.
    mentioned = {p.country for p in resolved if p.level == "country"}
    if mentioned:
        resolved = [p for p in resolved if p.country in mentioned]

    def corroborated(p: Place) -> bool:
        return _salient(p) or p.country in mentioned or p.country == fallback or len(title_hits[p]) >= 2

    resolved = [p for p in resolved if corroborated(p)]
    if resolved:
        counts = Counter(resolved)
        best = max(counts, key=lambda p: (counts[p], LEVEL_RANK[p.level], p.population))
        return Location(best.level, best.name, best.lat, best.lon, best.country)

    if not unresolved:
        return None
    top = Counter(tuple(c) for c in unresolved).most_common(1)[0][0]
    shared = {p.country for p in top}
    if len(shared) == 1:
        cc = shared.pop()
        country = gaz.countries.get(cc)
        if country:
            return Location("country", country.name, country.lat, country.lon, cc)
    return None


def country_of_event(location: Location | None, source_countries: list[str]) -> str:
    if location:
        return location.country
    if not source_countries:
        return ""
    return Counter(source_countries).most_common(1)[0][0]
