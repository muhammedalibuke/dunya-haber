"""Deterministic stand-ins for the ML components (no downloads in tests)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import numpy as np

from pipeline.models import Article

DIM = 16


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def axis(i: int, dim: int = DIM) -> list[float]:
    v = [0.0] * dim
    v[i] = 1.0
    return v


class FakeEmbedder:
    """Vector of the first mapping keyword found in the text (case-insensitive),
    else a hash-seeded random unit vector (nearly orthogonal to everything)."""

    def __init__(self, mapping: dict[str, list[float]], dim: int = DIM):
        self.mapping = {k.lower(): unit(v) for k, v in mapping.items()}
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for t in texts:
            low = t.lower()
            hit = next((v for k, v in self.mapping.items() if k in low), None)
            if hit is None:
                seed = int(hashlib.sha1(t.encode()).hexdigest()[:8], 16)
                hit = unit(np.random.default_rng(seed).normal(size=self.dim))
            rows.append(hit)
        return np.vstack(rows).astype(np.float32) if rows else np.zeros((0, self.dim), np.float32)


class FakeTranslator:
    """Prefixes the target language; returns None for languages in `unsupported`."""

    def __init__(self, unsupported: set[str] | None = None):
        self.unsupported = unsupported or set()
        self.calls = 0

    def translate(self, text: str, src: str, tgt: str) -> str | None:
        self.calls += 1
        if src in self.unsupported:
            return None
        return f"[{tgt}] {text}"


def art(aid, title, published, source_id="s1", country="GB", lang="en", desc="", url=None,
        tags=None, image_url=None, source_name=None):
    return Article(
        id=aid, url=url or f"https://{source_id}.example.com/{aid}", title=title, description=desc,
        source_id=source_id, source_name=source_name or source_id.upper(), country=country, lang=lang,
        published=published, image_url=image_url, tags=tags or [],
    )


NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
