"""One pipeline run: fetch → cluster → enrich → rank → publish.

CLI: python -m pipeline.run --state state --out build/data
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .cluster import assign
from .collect import fetch_all, http_get
from .embed import Embedder, embed_text
from .geo import Gazetteer, locate_event
from .models import Source
from .publish import build_site_data, lead_article, write_site_data
from .rank import select_today
from .sources import load_sources
from .state import load_state, prune, save_state
from .summarize import default_summary
from .topics import TopicConfig, article_topic, event_topic, load_topic_config, prototype_vectors
from .translate import Translator, translate_articles, translate_cached

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunReport:
    new_articles: int = 0
    touched_events: int = 0
    failures: dict[str, str] = field(default_factory=dict)
    today: int = 0

    def line(self) -> str:
        return (f"new_articles={self.new_articles} touched_events={self.touched_events} "
                f"failed_feeds={len(self.failures)} today={self.today}")


def run(state_dir: Path, out_dir: Path, now: datetime, sources: list[Source],
        get: Callable[[str], bytes], embedder: Embedder, translator: Translator,
        gaz: Gazetteer, topic_cfg: TopicConfig) -> RunReport:
    state = load_state(state_dir)
    fetched, failures = fetch_all(sources, get, now)
    new = [a for a in fetched if a.id not in state.articles]
    report = RunReport(new_articles=len(new), failures=failures)

    if new:
        vectors = embedder.encode([embed_text(a) for a in new])
        protos = prototype_vectors(topic_cfg, embedder)
        for a, v in zip(new, vectors):
            a.topic = article_topic(a, v, topic_cfg, protos)
            state.articles[a.id] = a
        translate_articles(new, state.translations, translator)
        touched = assign(state.events, new, vectors, now)
        report.touched_events = len(touched)

        for eid in touched:
            e = state.events[eid]
            arts = [state.articles[a] for a in e.article_ids if a in state.articles]
            e.topic = event_topic([a.topic for a in arts])
            e.location = locate_event([a.title_en or a.title for a in arts], [a.country for a in arts], gaz)
            if not e.summary_ai:
                lead = lead_article(e, state.articles)
                text = default_summary(lead.description)
                e.summary_tr = translate_cached(text, lead.lang, "tr", state.translations, translator)
                e.summary_en = translate_cached(text, lead.lang, "en", state.translations, translator)

    prune(state, now)
    today = select_today(state.events, state.articles, now)
    report.today = len(today)
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
    report = run(
        state_dir=args.state,
        out_dir=args.out,
        now=datetime.now(timezone.utc),
        sources=load_sources(ROOT / "config" / "sources.yaml"),
        get=http_get,
        embedder=SentenceEmbedder(),
        translator=ArgosTranslator(Path(argos_dir) if argos_dir else None),
        gaz=Gazetteer.load(ROOT / "data" / "gazetteer.json.gz", ROOT / "config" / "place_stoplist.txt"),
        topic_cfg=load_topic_config(ROOT / "config" / "topics.yaml"),
    )
    print(report.line())
    for sid, err in sorted(report.failures.items()):
        print(f"  feed failed: {sid}: {err}")


if __name__ == "__main__":
    main()
