"""Download the models the pipeline needs (runs in CI before the pipeline, cached between runs).

- Argos Translate packages: every source language -> en, plus en -> tr and tr -> en.
- The multilingual sentence-transformers model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.embed import SentenceEmbedder  # noqa: E402
from pipeline.sources import load_sources  # noqa: E402
from pipeline.translate import ArgosTranslator  # noqa: E402


def main() -> None:
    langs = sorted({s.lang for s in load_sources(ROOT / "config" / "sources.yaml")})
    argos_dir = os.environ.get("ARGOS_PACKAGES_DIR")
    tr = ArgosTranslator(Path(argos_dir) if argos_dir else None)
    pairs = [(lang, "en") for lang in langs if lang != "en"] + [("en", "tr"), ("tr", "en")]
    for src, tgt in pairs:
        ok = tr._ensure(src, tgt)
        print(f"argos {src}->{tgt}: {'ok' if ok else 'not available'}")
    SentenceEmbedder()
    print("sentence model: ok")


if __name__ == "__main__":
    main()
