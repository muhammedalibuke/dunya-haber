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

from .cluster import CLUSTER_LOW, OPEN_WINDOW_HOURS, NameRescue, _normalize, assign, merge_events
from .collect import ConditionalGetter, fetch_all, fetch_page_head
from .embed import Embedder, embed_text
from .geo import Gazetteer, locate_event
from .models import Source
from .publish import build_site_data, published_events, write_site_data
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


COVER_LOOKUPS_PER_RUN = 40


def find_covers(events, articles, page_get, limit: int = COVER_LOOKUPS_PER_RUN) -> int:
    """For shown stories without any photo, read one article page's cover photo (og:image).
    Each article page is asked at most once. Returns how many photos were found."""
    from concurrent.futures import ThreadPoolExecutor

    from .images import extract_og_image

    todo = []
    for e in events:
        arts = [articles[a] for a in e.article_ids if a in articles]
        if not arts or any(a.image_url for a in arts):
            continue
        cand = [a for a in sorted(arts, key=lambda a: (a.source_tier, a.published)) if not a.image_checked]
        if cand:
            todo.append(cand[0])
        if len(todo) >= limit:
            break

    def one(a):
        try:
            return a, extract_og_image(page_get(a.url).decode("utf-8", "ignore"), a.url)
        except Exception:  # unreachable or blocked page: simply no photo
            return a, None

    found = 0
    with ThreadPoolExecutor(max_workers=16) as pool:
        for a, url in pool.map(one, todo):
            a.image_checked = True
            if url:
                a.image_url = url
                found += 1
    return found


def migrate_centroids(state, embedder: Embedder, dim: int, now: datetime,
                      recent_hours: int = 12, max_articles: int = 600) -> None:
    """After a model change, centroids from the old model can't be compared. Recent events are
    re-embedded with the new model (newest first, bounded); older ones stop taking new articles."""
    stale = [e for e in state.events.values() if e.centroid is not None and e.centroid.shape[0] != dim]
    stale.sort(key=lambda e: e.updated_at, reverse=True)
    budget = max_articles
    for e in stale:
        arts = [state.articles[a] for a in e.article_ids if a in state.articles]
        if arts and e.updated_at >= now - timedelta(hours=recent_hours) and len(arts) <= budget:
            e.centroid = _normalize(embedder.encode([embed_text(a) for a in arts]).mean(axis=0))
            budget -= len(arts)
        else:
            e.centroid = None


def dissolve_events(state, over: int, now: datetime) -> list:
    """Remove events with more than `over` articles. Their articles from the last
    OPEN_WINDOW_HOURS are returned to be grouped again; older ones are dropped."""
    too_old = now - timedelta(hours=OPEN_WINDOW_HOURS)
    out = []
    for eid in [eid for eid, e in state.events.items() if len(e.article_ids) > over]:
        for aid in state.events.pop(eid).article_ids:
            a = state.articles.pop(aid, None)
            if a is not None and a.published >= too_old:
                out.append(a)
    print(f"dissolved events over {over} articles: {len(out)} articles to regroup", flush=True)
    return out


def run(state_dir: Path, out_dir: Path, now: datetime, sources: list[Source],
        get: Callable[[str], bytes], embedder: Embedder, translator: Translator,
        gaz: Gazetteer, topic_cfg: TopicConfig, gemini_key: str | None = None,
        post=None, translate_budget_s: float = TRANSLATE_BUDGET_S,
        topic_embedder: Embedder | None = None, page_get=None,
        dissolve_over: int | None = None) -> RunReport:
    """`embedder` groups articles into events; `topic_embedder` (default: the same) tags topics.
    `dissolve_over` (manual repair): events with more articles than this are broken up and their
    recent articles grouped again from scratch."""
    topic_embedder = topic_embedder or embedder
    state = load_state(state_dir)
    requeue = dissolve_events(state, dissolve_over, now) if dissolve_over else []
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
    new += requeue
    report = RunReport(new_articles=len(new), failures=failures)
    if any(e.centroid is not None for e in state.events.values()):
        migrate_centroids(state, embedder, embedder.encode(["dimension probe"]).shape[1], now)

    if new:
        texts = [embed_text(a) for a in new]
        vectors = embedder.encode(texts)
        topic_vectors = vectors if topic_embedder is embedder else topic_embedder.encode(texts)
        protos = prototype_vectors(topic_cfg, topic_embedder)
        for a, v in zip(new, topic_vectors):
            a.topic = article_topic(a, v, topic_cfg, protos)
            state.articles[a.id] = a
        rescue = NameRescue(state.articles, state.events)
        touched = assign(state.events, new, vectors, now, low=CLUSTER_LOW, rescue=rescue)
        merged = merge_events(state.events, touched, now, low=CLUSTER_LOW, rescue=rescue)
        touched = {merged.get(t, t) for t in touched}
        report.touched_events = len(touched)
        for eid in touched:
            e = state.events[eid]
            e.topic = event_topic([state.articles[a].topic for a in e.article_ids if a in state.articles])

    # Only events that can be shown (open, ≥2 sources) get translated, located and summarized,
    # most important first, within a time budget; leftovers are picked up by the next run.
    # only what the site will show: today's important events first, then the newest stories
    shown = published_events(state, select_today(state.events, state.articles, now), now)
    budget = Budget(translate_budget_s)
    for e in shown:
        arts = [state.articles[a] for a in e.article_ids if a in state.articles]
        translate_articles(arts, state.translations, translator, budget)
        if not e.summary_ai and e.summary_v < SUMMARY_VERSION and not budget.exhausted:
            build_summary(e, arts, embedder, state.translations, translator)
        e.location = locate_event([a.title_en or a.title for a in arts], [a.country for a in arts], gaz)

    if page_get is not None:
        find_covers(shown, state.articles, page_get)

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
    ap.add_argument("--dissolve-over", type=int, default=None,
                    help="repair: break up events with more articles than this")
    args = ap.parse_args()

    from .embed import CLUSTER_MODEL, SentenceEmbedder
    from .translate import ArgosTranslator

    argos_dir = os.environ.get("ARGOS_PACKAGES_DIR")
    getter = ConditionalGetter(args.state / "http_cache.json.gz")
    report = run(
        state_dir=args.state,
        out_dir=args.out,
        now=datetime.now(timezone.utc),
        sources=load_sources(ROOT / "config" / "sources.yaml"),
        get=getter,
        embedder=SentenceEmbedder(CLUSTER_MODEL),
        topic_embedder=SentenceEmbedder(),
        translator=ArgosTranslator(Path(argos_dir) if argos_dir else None),
        gaz=Gazetteer.load(ROOT / "data" / "gazetteer.json.gz", ROOT / "config" / "place_stoplist.txt"),
        topic_cfg=load_topic_config(ROOT / "config" / "topics.yaml"),
        gemini_key=os.environ.get("GEMINI_API_KEY") or None,
        page_get=fetch_page_head,
        dissolve_over=args.dissolve_over,
    )
    getter.save()  # only after the state was saved: a failed run must refetch everything it saw
    print(report.line())
    for sid, err in sorted(report.failures.items()):
        print(f"  feed failed: {sid}: {err}")


if __name__ == "__main__":
    main()
