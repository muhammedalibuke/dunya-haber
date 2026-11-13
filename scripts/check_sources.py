"""Report the health of every feed in config/sources.yaml.

Runs in GitHub Actions (check-sources workflow). Always exits 0: it is a report.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import http_get, parse_feed  # noqa: E402
from pipeline.sources import load_sources  # noqa: E402


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = load_sources(root / "config" / "sources.yaml")
    now = datetime.now(timezone.utc)
    healthy = []
    print(f"{'id':24} {'status':8} {'items':>5} {'newest':>8}  detail")
    from concurrent.futures import ThreadPoolExecutor

    def check(src):
        try:
            arts = parse_feed(http_get(src.url), src, now)
            if not arts:
                return src, "EMPTY", 0, None, ""
            newest = min((now - a.published).total_seconds() / 3600 for a in arts)
            status = "OK" if newest < 72 else "STALE"
            return src, status, len(arts), newest, ""
        except Exception as exc:
            return src, "FAIL", 0, None, f"{type(exc).__name__}: {exc}"[:90]

    with ThreadPoolExecutor(16) as pool:
        for src, status, n, newest, detail in pool.map(check, sources):
            age = f"{newest:.0f}h" if newest is not None else "-"
            print(f"{src.id:24} {status:8} {n:>5} {age:>8}  {detail}")
            if status == "OK":
                healthy.append(src)
    countries = Counter(s.country for s in healthy)
    print(f"\nhealthy: {len(healthy)}/{len(sources)} feeds, {len(countries)} countries")


if __name__ == "__main__":
    main()
