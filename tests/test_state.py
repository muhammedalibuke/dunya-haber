from datetime import datetime, timedelta, timezone

import numpy as np

from pipeline.models import Article, Event, Location, State
from pipeline.state import cache_key, load_state, prune, save_state

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def make_article(aid="a1", published=NOW, title="Quake hits Kobe", desc="Strong quake."):
    return Article(
        id=aid, url=f"https://example.com/{aid}", title=title, description=desc,
        source_id="bbc", source_name="BBC", country="GB", lang="en",
        published=published, image_url=None, tags=["world"],
    )


def make_event(eid="a1", article_ids=("a1",), updated=NOW, dim=384, seed=0):
    v = np.random.default_rng(seed).normal(size=dim).astype(np.float32)
    v /= np.linalg.norm(v)
    return Event(id=eid, article_ids=list(article_ids), centroid=v,
                 created_at=updated, updated_at=updated)


def test_load_missing_dir_returns_empty_state(tmp_path):
    s = load_state(tmp_path / "nope")
    assert s.articles == {} and s.events == {} and s.translations == {}


def test_roundtrip(tmp_path):
    a = make_article()
    e = make_event()
    e.location = Location(level="city", name="Kobe", lat=34.69, lon=135.19, country="JP")
    e.topic = "general"
    e.summary_tr = "Güçlü deprem."
    key = cache_key(a.title, "en", "tr")
    s = State(articles={a.id: a}, events={e.id: e}, translations={key: {"text": "Kobe'de deprem"}})
    save_state(s, tmp_path)
    t = load_state(tmp_path)
    assert t.articles["a1"] == a
    te = t.events["a1"]
    assert te.article_ids == ["a1"]
    assert te.updated_at == NOW and te.created_at == NOW
    assert te.location == e.location
    assert te.summary_tr == "Güçlü deprem."
    assert te.centroid.dtype == np.float32
    assert np.allclose(te.centroid, e.centroid, atol=1e-3)
    assert t.translations == s.translations


def test_prune_deletes_events_7_days_after_last_article():
    old = make_event("old", ["o1"], updated=NOW - timedelta(days=7, minutes=1))
    keep = make_event("keep", ["k1"], updated=NOW - timedelta(days=6))
    s = State(
        articles={"o1": make_article("o1"), "k1": make_article("k1")},
        events={"old": old, "keep": keep}, translations={},
    )
    prune(s, NOW)
    assert set(s.events) == {"keep"}
    assert set(s.articles) == {"k1"}


def test_prune_drops_orphan_translations_not_needed():
    a = make_article("k1", title="Hello")
    s = State(
        articles={"k1": a},
        events={"k1": make_event("k1", ["k1"])},
        translations={
            cache_key("Hello", "en", "tr"): {"text": "Merhaba"},
            cache_key("Gone", "en", "tr"): {"text": "Gitti"},
        },
    )
    prune(s, NOW)
    assert list(s.translations) == [cache_key("Hello", "en", "tr")]
