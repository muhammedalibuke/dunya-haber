"""Offline translation (Argos Translate, MIT/CC0 models) with a persistent cache."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Protocol

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


class Budget:
    """Wall-clock allowance for translation in one run; unfinished work waits for the next run."""

    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self.deadline = clock() + seconds

    @property
    def exhausted(self) -> bool:
        return self.clock() >= self.deadline


def translate_pair(text: str, lang: str, cache: dict, tr: Translator) -> tuple[str, str]:
    """(tr, en) for a text. Non-English sources go X→en once, then en→tr from that result."""
    if lang == "en":
        return translate_cached(text, "en", "tr", cache, tr), text
    if lang == "tr":
        return text, translate_cached(text, "tr", "en", cache, tr)
    en = translate_cached(text, lang, "en", cache, tr)
    if en == text:  # no X→en model: nothing better to offer
        return text, text
    return translate_cached(en, "en", "tr", cache, tr), en


def translate_articles(articles: list[Article], cache: dict, tr: Translator,
                       budget: Budget | None = None) -> None:
    """Fill title_tr/title_en; stops early when the budget runs out (fields stay None)."""
    for a in articles:
        if a.title_tr is not None and a.title_en is not None:
            continue
        if budget and budget.exhausted:
            return
        a.title_tr, a.title_en = translate_pair(a.title, a.lang, cache, tr)


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
        self._installed: set[tuple[str, str]] | None = None
        self._tried: set[tuple[str, str]] = set()

    def _ensure(self, src: str, tgt: str) -> bool:
        if self._installed is None:
            self._installed = {(p.from_code, p.to_code) for p in self._pkg.get_installed_packages()}
        if (src, tgt) in self._installed:
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
                self._installed.add((src, tgt))
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


__all__ = ["Translator", "ArgosTranslator", "Budget", "translate_cached", "translate_pair",
           "translate_articles", "TARGET_LANGS"]
