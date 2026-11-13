"""Tag articles/events as sport, entertainment or general (free, offline)."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import yaml

from .embed import Embedder
from .models import Article

TOPICS = ("sport", "entertainment")


@dataclass
class TopicConfig:
    url_keywords: dict[str, list[str]]
    tag_keywords: dict[str, list[str]]
    prototypes: dict[str, list[str]]


def load_topic_config(path: Path) -> TopicConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return TopicConfig(raw["url_keywords"], raw["tag_keywords"], raw["prototypes"])


def prototype_vectors(cfg: TopicConfig, embedder: Embedder) -> dict[str, np.ndarray]:
    out = {}
    for topic, phrases in cfg.prototypes.items():
        m = embedder.encode(phrases).mean(axis=0)
        out[topic] = (m / np.linalg.norm(m)).astype(np.float32)
    return out


def article_topic(a: Article, vector: np.ndarray, cfg: TopicConfig,
                  protos: dict[str, np.ndarray], min_sim: float = 0.45) -> str:
    segments = {s for s in re.split(r"[/\-_.]", urlsplit(a.url).path.lower()) if s}
    for topic in TOPICS:
        if segments & set(cfg.url_keywords.get(topic, [])):
            return topic
    tags = {t.lower() for t in a.tags}
    for topic in TOPICS:
        if tags & set(cfg.tag_keywords.get(topic, [])):
            return topic
    best, best_sim = "general", min_sim
    for topic, p in protos.items():
        sim = float(np.dot(vector, p))
        if sim >= best_sim:
            best, best_sim = topic, sim
    return best


def event_topic(topics: list[str]) -> str:
    if not topics:
        return "general"
    topic, n = Counter(topics).most_common(1)[0]
    return topic if topic != "general" and n / len(topics) > 0.5 else "general"
