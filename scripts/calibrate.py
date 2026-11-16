"""Measure how well embedding models separate same-story from different-story pairs.

Labelled pairs: scripts/calibration/pairs.json  ({"same": 0|1, "a": {...}, "b": {...}})
Runs in GitHub Actions (calibrate workflow); needs the [ml] extras and network for models.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.cluster import name_tokens  # noqa: E402
from pipeline.state import load_state  # noqa: E402

MODELS = {
    "minilm": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", ""),
    "mpnet": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", ""),
    "e5-base": ("intfloat/multilingual-e5-base", "query: "),
    "labse": ("sentence-transformers/LaBSE", ""),
    "bge-m3": ("BAAI/bge-m3", ""),
}


def text(x: dict) -> str:
    return x["title"] + ". " + x["desc"][:200]


def sweep(sims: np.ndarray, y: np.ndarray):
    best = (0.0, 0.0, 0.0, 0.0)
    for t in np.arange(0.40, 0.96, 0.01):
        pred = sims >= t
        tp, fp, fn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum())
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        acc = float((pred == y).mean())
        if f1 > best[0]:
            best = (f1, acc, t, fp)
    return best


def main() -> None:
    pairs = json.loads((ROOT / "scripts" / "calibration" / "pairs.json").read_text(encoding="utf-8"))
    y = np.array([bool(p["same"]) for p in pairs])
    state_dir = ROOT / "state"
    df = {}
    if state_dir.exists():
        st = load_state(state_dir)
        for a in st.articles.values():
            for tok in set(name_tokens(a.title + " " + a.description[:200])):
                df[tok] = df.get(tok, 0) + 1
    shared = np.array([
        sum(1 for t in set(name_tokens(text(p["a"]))) & set(name_tokens(text(p["b"]))) if df.get(t, 0) <= 15)
        for p in pairs])
    print(f"{len(pairs)} pairs, {int(y.sum())} same; corpus tokens: {len(df)}")
    print(f"pairs sharing a rare name: same {int((shared[y] > 0).sum())}/{int(y.sum())}, "
          f"different {int((shared[~y] > 0).sum())}/{int((~y).sum())}")

    from sentence_transformers import SentenceTransformer

    only = [m for m in sys.argv[1:] if m in MODELS]
    for label, (name, prefix) in MODELS.items():
        if only and label not in only:
            continue
        try:
            t0 = time.time()
            m = SentenceTransformer(name, device="cpu")
            load = time.time() - t0
            t0 = time.time()
            va = m.encode([prefix + text(p["a"]) for p in pairs], normalize_embeddings=True)
            vb = m.encode([prefix + text(p["b"]) for p in pairs], normalize_embeddings=True)
            speed = (time.time() - t0) / (2 * len(pairs)) * 1000
            sims = (va * vb).sum(axis=1)
        except Exception as exc:
            print(f"{label}: failed: {exc}")
            continue
        print("SIMS " + label + " " + json.dumps([round(float(x), 4) for x in sims]))
        f1, acc, t, fp = sweep(sims, y)
        print(f"\n== {label}: best F1 {f1:.2f} acc {acc:.2f} at {t:.2f} (false merges {fp}); "
              f"load {load:.0f}s, {speed:.0f} ms/text")
        print(f"   same: min {sims[y].min():.2f} median {np.median(sims[y]):.2f} | "
              f"different: median {np.median(sims[~y]):.2f} max {sims[~y].max():.2f}")
        for lo in (0.50, 0.55, 0.60, 0.65):
            for hi in (0.70, 0.75, 0.80, 0.85):
                if hi <= lo:
                    continue
                pred = (sims >= hi) | ((sims >= lo) & (shared > 0))
                tp, fp2 = int((pred & y).sum()), int((pred & ~y).sum())
                print(f"   rule hi={hi:.2f} lo={lo:.2f}+rare name: merges {tp}/{int(y.sum())} same, "
                      f"{fp2} wrong")


if __name__ == "__main__":
    main()
