"""Multilingual sentence vectors used to group articles about the same event."""
from __future__ import annotations

from typing import Protocol

import numpy as np

from .models import Article

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # Apache-2.0


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return one L2-normalized float32 row per text."""


def embed_text(a: Article) -> str:
    return a.title + ". " + a.description[:200]


class SentenceEmbedder:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        from sentence_transformers import SentenceTransformer  # heavy; imported lazily

        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), np.float32)
        v = self.model.encode(texts, batch_size=64, normalize_embeddings=True,
                              show_progress_bar=False, convert_to_numpy=True)
        return v.astype(np.float32)
