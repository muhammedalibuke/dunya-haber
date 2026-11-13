"""Core data types shared by every pipeline stage."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import numpy as np

REGIONS = ("africa", "americas", "asia", "europe", "middle_east", "oceania")


@dataclass
class Source:
    id: str
    name: str
    url: str
    country: str  # ISO-3166 alpha-2, upper case
    lang: str  # ISO-639-1
    region: str  # one of REGIONS


@dataclass
class Article:
    id: str  # sha1(canonical_url)[:16]
    url: str
    title: str
    description: str
    source_id: str
    source_name: str
    country: str
    lang: str
    published: datetime  # tz-aware UTC
    image_url: str | None
    tags: list[str]
    topic: str = "general"
    title_tr: str | None = None
    title_en: str | None = None


@dataclass
class Location:
    level: Literal["city", "region", "country"]
    name: str
    lat: float
    lon: float
    country: str


@dataclass
class Event:
    id: str
    article_ids: list[str]
    centroid: np.ndarray | None  # float32, L2-normalized; None once the event is closed
    created_at: datetime
    updated_at: datetime
    topic: str = "general"
    location: Location | None = None
    summary_tr: str = ""
    summary_en: str = ""
    summary_ai: bool = False


@dataclass
class State:
    articles: dict[str, Article] = field(default_factory=dict)
    events: dict[str, Event] = field(default_factory=dict)
    translations: dict[str, dict[str, str]] = field(default_factory=dict)
    seen: dict[str, int] = field(default_factory=dict)  # article id -> day first seen (days since epoch)
