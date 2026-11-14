"""One pipeline run: fetch → cluster → enrich → rank → publish.

CLI: python -m pipeline.run --state state --out build/data
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .cluster import OPEN_WINDOW_HOURS, assign
from .collect import ConditionalGetter, fetch_all
from .embed import Embedder, embed_text
from .geo import Gazetteer, locate_event
from .models import Source
from .publish import build_site_data, listable, write_site_data
from .rank import select_today
from .sources import load_sources
from .state import epoch_day, load_state, prune, save_state
from .summarize import SUMMARY_VERSION, combined_summary, gemini_summary
from .topics import TopicConfig, article_topic, event_topic, load_topic_config, prototype_vectors
from .translate import Budget, Translator, translate_articles, translate_pair

ROOT = Path(__file__).resolve().parents[1]
TRANSLATE_BUDGET_S = 8 * 60  # keeps a run inside the 10-minute schedule; leftovers wait for the next run


@dataclass
class RunReport:
    new_articles: int = 0
    touched_events: int = 0
    failures: dict[str, str] = field(default_factory=dict)
    today: int = 0

    def line(self) -> str:
        return (f"new_articles={self.new_articles} touched_events={self.touched_events} "
                f"failed_feeds={len(self.failures)} today={self.today}")


def build_summary(e, arts, embedder, cache, translator) -> None:
    """Longer summary from several outlets: English and widely read sources first."""
    items, seen = [], set()
    for a in sorted(arts, key=lambda a: (a.lang != "en", a.source_tier, a.published)):
        if a.description and a.description not in seen:
            seen.add(a.description)
            items.append((a.lang, a.description))
    picked = combined_summary(items[:8], embedder)
    if not picked:
        return
    pairs = [translate_pair(sent, lang, cache, translator) for lang, sent in picked]
    e.summary_tr = " ".join(tr for tr, _ in pairs)
    e.summary_en = " ".join(en for _, en in pairs)
    e.summary_v = SUMMARY_VERSION


def run(state_dir: Path, out_dir: Path, now: datetime, sources: list[Source],
        get: Callable[[str], bytes], embedder: Embedder, translator: Translator,
        gaz: Gazetteer, topic_cfg: TopicConfig, gemini_key: str | None = None,
        post=None, translate_budget_s: float = TRANSLATE_BUDGET_S) -> RunReport:
    state = load_state(state_dir)
    tiers = {src.id: src.tier for src in sources}
    for a in state.articles.values():  # popularity can be edited in sources.yaml at any time
        a.source_tier = tiers.get(a.source_id, a.source_tier)
    fetched, failures = fetch_all(sources, get, now)
    too_old = now - timedelta(hours=OPEN_WINDOW_HOURS)
    today_n = epoch_day(now)
    new = []
    for a in fetched:
        if a.id in state.articles or a.id in state.seen:
            continue
        state.seen[a.id] = today_n  # remembered even after pruning: never processed twice
        if a.published >= too_old:
            new.append(a)
    report = RunReport(new_articles=len(new), failures=failures)

    if new:
        vectors = embedder.encode([embed_text(a) for a in new])
        protos = prototype_vectors(topic_cfg, embedder)
        for a, v in zip(new, vectors):
            a.topic = article_topic(a, v, topic_cfg, protos)
            state.articles[a.id] = a
        touched = assign(state.events, new, vectors, now)
        report.touched_events = len(touched)
        for eid in touched:
            e = state.events[eid]
            e.topic = event_topic([state.articles[a].topic for a in e.article_ids if a in state.articles])

    # Only events that can be shown (open, ≥2 sources) get translated, located and summarized,
    # most important first, within a time budget; leftovers are picked up by the next run.
    shown = [e for e in state.events.values() if listable(e, state.articles, now)]
    first = set(select_today(state.events, state.articles, now))
    # today's important events first, then the newest stories (breaking news) first
    shown.sort(key=lambda e: (e.id not in first, -e.created_at.timestamp()))
    budget = Budget(translate_budget_s)
    for e in shown:
        arts = [state.articles[a] for a in e.article_ids if a in state.articles]
        translate_articles(arts, state.translations, translator, budget)
        if not e.summary_ai and e.summary_v < SUMMARY_VERSION and not budget.exhausted:
            build_summary(e, arts, embedder, state.translations, translator)
        e.location = locate_event([a.title_en or a.title for a in arts], [a.country for a in arts], gaz)

    prune(state, now)
    today = select_today(state.events, state.articles, now)
    report.today = len(today)
    if gemini_key:
        for eid in today:
            e = state.events[eid]
            if e.summary_ai:
                continue
            arts = [state.articles[a] for a in e.article_ids if a in state.articles][:8]
            got = gemini_summary([a.title_en or a.title for a in arts], [a.description for a in arts],
                                 gemini_key, post=post)
            if got:
                e.summary_tr, e.summary_en = got
                e.summary_ai = True
    save_state(state, state_dir)
    write_site_data(out_dir, build_site_data(state, today, now))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--out", type=Path, default=Path("build/data"))
    args = ap.parse_args()

    from .embed import SentenceEmbedder
    from .translate import ArgosTranslator

    argos_dir = os.environ.get("ARGOS_PACKAGES_DIR")
    getter = ConditionalGetter(args.state / "http_cache.json.gz")
    report = run(
        state_dir=args.state,
        out_dir=args.out,
        now=datetime.now(timezone.utc),
        sources=load_sources(ROOT / "config" / "sources.yaml"),
        get=getter,
        embedder=SentenceEmbedder(),
        translator=ArgosTranslator(Path(argos_dir) if argos_dir else None),
        gaz=Gazetteer.load(ROOT / "data" / "gazetteer.json.gz", ROOT / "config" / "place_stoplist.txt"),
        topic_cfg=load_topic_config(ROOT / "config" / "topics.yaml"),
        gemini_key=os.environ.get("GEMINI_API_KEY") or None,
    )
    getter.save()  # only after the state was saved: a failed run must refetch everything it saw
    print(report.line())
    for sid, err in sorted(report.failures.items()):
        print(f"  feed failed: {sid}: {err}")


if __name__ == "__main__":
    main()
