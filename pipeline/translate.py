"""Offline translation (Argos Translate, MIT/CC0 models) with a persistent cache."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import Article
from .state import TARGET_LANGS, cache_key


class Translator(Protocol):
    def translate(self, text: str, src: str, tgt: str) -> str | None:
        """Translated text, or None when the language pair is unsupported."""


def translate_cached(text: str, src: str, tgt: str, cache: dict, tr: Translator) -> str:
    if not text or src == tgt:
        return text
    key = cache_key(text, src, tgt)
    hit = cache.get(key)
    if hit:
        return hit["text"]
    try:
        out = tr.translate(text, src, tgt)
    except Exception:  # a translation failure must never stop the run
        out = None
    if not out:
        return text
    cache[key] = {"text": out}
    return out


def translate_articles(articles: list[Article], cache: dict, tr: Translator) -> None:
    for a in articles:
        a.title_tr = translate_cached(a.title, a.lang, "tr", cache, tr)
        a.title_en = translate_cached(a.title, a.lang, "en", cache, tr)


class ArgosTranslator:
    """Installs language packages on demand from the Argos index (cached by CI)."""

    def __init__(self, install_dir: Path | None = None):
        import os

        if install_dir:
            os.environ.setdefault("ARGOS_PACKAGES_DIR", str(install_dir))
        import argostranslate.package as pkg
        import argostranslate.translate as tr

        self._pkg, self._tr = pkg, tr
        self._available = None
        self._tried: set[tuple[str, str]] = set()

    def _ensure(self, src: str, tgt: str) -> bool:
        installed = {(p.from_code, p.to_code) for p in self._pkg.get_installed_packages()}
        if (src, tgt) in installed:
            return True
        if (src, tgt) in self._tried:
            return False
        self._tried.add((src, tgt))
        if self._available is None:
            try:
                self._pkg.update_package_index()
                self._available = self._pkg.get_available_packages()
            except Exception:
                self._available = []
        for p in self._available:
            if p.from_code == src and p.to_code == tgt:
                self._pkg.install_from_path(p.download())
                return True
        return False

    def translate(self, text: str, src: str, tgt: str) -> str | None:
        if src == tgt:
            return text
        if self._ensure(src, tgt):
            return self._tr.translate(text, src, tgt)
        if src != "en" and tgt != "en" and self._ensure(src, "en") and self._ensure("en", tgt):
            return self._tr.translate(self._tr.translate(text, src, "en"), "en", tgt)
        return None


__all__ = ["Translator", "ArgosTranslator", "translate_cached", "translate_articles", "TARGET_LANGS"]
