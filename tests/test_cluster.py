from datetime import timedelta

import numpy as np

from pipeline.cluster import assign
from pipeline.embed import embed_text
from pipeline.models import Event
from tests.fakes import NOW, FakeEmbedder, art, axis, unit

EMB = FakeEmbedder({"quake": axis(0), "deprem": axis(0), "budget": axis(1), "bütçe": axis(1)})


def vecs(arts):
    return EMB.encode([embed_text(a) for a in arts])


def test_embed_text_uses_title_and_description_prefix():
    a = art("a", "Title", NOW, desc="x" * 500)
    assert embed_text(a) == "Title. " + "x" * 200


def test_similar_articles_join_one_event():
    arts = [art("a1", "Quake hits Kobe", NOW - timedelta(hours=2), source_id="bbc"),
            art("a2", "Kobe'de deprem", NOW - timedelta(hours=1), source_id="aa", lang="tr")]
    events = {}
    touched = assign(events, arts, vecs(arts), NOW)
    assert len(events) == 1
    [e] = events.values()
    assert e.article_ids == ["a1", "a2"]
    assert touched == {e.id}


def test_dissimilar_articles_make_two_events():
    arts = [art("a1", "Quake hits Kobe", NOW), art("a2", "Budget passes", NOW)]
    events = {}
    assign(events, arts, vecs(arts), NOW)
    assert len(events) == 2


def test_article_joins_existing_open_event_and_bumps_updated_at():
    old_time = NOW - timedelta(hours=5)
    events = {"e1": Event("e1", ["x"], unit(axis(0)), old_time, old_time)}
    a = art("a1", "Another quake report", NOW - timedelta(minutes=10))
    touched = assign(events, [a], vecs([a]), NOW)
    assert touched == {"e1"}
    assert events["e1"].article_ids == ["x", "a1"]
    assert events["e1"].updated_at == a.published


def test_closed_event_not_reused():
    old_time = NOW - timedelta(hours=49)
    events = {"e1": Event("e1", ["x"], unit(axis(0)), old_time, old_time)}
    a = art("a1", "Quake again", NOW)
    assign(events, [a], vecs([a]), NOW)
    assert len(events) == 2
    assert events["e1"].article_ids == ["x"]


def test_same_article_id_never_added_twice():
    events = {}
    a = art("a1", "Quake hits Kobe", NOW)
    assign(events, [a], vecs([a]), NOW)
    assign(events, [a], vecs([a]), NOW)
    [e] = events.values()
    assert e.article_ids == ["a1"]


def test_centroid_is_normalized_running_mean():
    emb = FakeEmbedder({"alpha": [1, 0.2] + [0] * 14, "beta": [1, -0.2] + [0] * 14})
    arts = [art("a1", "alpha", NOW), art("a2", "beta", NOW)]
    events = {}
    assign(events, arts, emb.encode([embed_text(a) for a in arts]), NOW, threshold=0.5)
    [e] = events.values()
    assert np.isclose(np.linalg.norm(e.centroid), 1.0, atol=1e-5)
    assert np.allclose(e.centroid, unit([1, 0] + [0] * 14), atol=1e-5)


def test_updated_at_never_moves_backwards():
    events = {"e1": Event("e1", ["x"], unit(axis(0)), NOW - timedelta(hours=3), NOW - timedelta(hours=1))}
    a = art("a1", "Late-published quake piece", NOW - timedelta(hours=2))
    assign(events, [a], vecs([a]), NOW)
    assert events["e1"].updated_at == NOW - timedelta(hours=1)


def test_name_tokens_picks_names_and_acronyms():
    from pipeline.cluster import name_tokens
    toks = name_tokens("NYPD shoots suspect; Gérard Depardieu's appeal in São Paulo, 2027 Budget")
    assert "nypd" in toks and "depardieu" in toks and "gerard" in toks and "paulo" in toks
    assert "shoots" not in toks and "2027" not in toks and "sao" not in toks  # short / lowercase / digits out
    assert name_tokens("神戸で地震") == []


def test_borderline_match_merges_only_with_rescue():
    emb = FakeEmbedder({"alpha": [1, 0.9] + [0] * 14})  # cos with axis(0) ≈ 0.74 → set thresholds around it
    e = Event("e1", ["x"], unit(axis(0)), NOW, NOW)
    a = art("a1", "alpha story", NOW)
    v = emb.encode([embed_text(a)])
    sim = float(v[0] @ e.centroid)
    events = {"e1": e}
    assign(events, [a], v, NOW, threshold=sim + 0.05, low=sim - 0.05, rescue=lambda art_, ev: False)
    assert len(events) == 2
    e2 = Event("e1", ["x"], unit(axis(0)), NOW, NOW)
    events = {"e1": e2}
    assign(events, [a], v, NOW, threshold=sim + 0.05, low=sim - 0.05, rescue=lambda art_, ev: ev.id == "e1")
    assert events["e1"].article_ids == ["x", "a1"] and len(events) == 1


def test_name_rescue_uses_names_rare_across_events():
    from pipeline.cluster import NameRescue
    arts = {
        "r1": art("r1", "Ronaldinho returns to football", NOW, source_id="s1"),
        "t1": art("t1", "Trump speaks", NOW, source_id="s2"),
        **{f"t{i}": art(f"t{i}", f"Trump story {i}", NOW, source_id=f"s{i}") for i in range(2, 9)},
    }
    events = {k: Event(k, [k], unit(axis(0)), NOW, NOW) for k in arts}
    rescue = NameRescue(arts, events, max_events=5)
    assert rescue(art("n1", "Icon Ronaldinho makes winning return", NOW), events["r1"])
    assert not rescue(art("n2", "Trump again", NOW), events["t1"])  # Trump is in 8 events: too common


def test_merge_split_events():
    from pipeline.cluster import merge_events
    t0 = NOW - timedelta(hours=3)
    a = Event("old", ["a1", "a2"], unit(axis(0)), t0, NOW - timedelta(hours=2))
    b = Event("new", ["b1"], unit([1, 0.05] + [0] * 14), NOW - timedelta(hours=1), NOW)
    c = Event("other", ["c1"], unit(axis(5)), NOW, NOW)
    events = {"old": a, "new": b, "other": c}
    merged = merge_events(events, {"new"}, NOW, threshold=0.9)
    assert merged == {"new": "old"}
    assert set(events) == {"old", "other"}
    assert events["old"].article_ids == ["a1", "a2", "b1"]
    assert events["old"].created_at == t0 and events["old"].updated_at == NOW


def test_merge_chain_points_to_surviving_event():
    """x merges into y, then y merges into z: x must map to z, never to the deleted y."""
    from pipeline.cluster import merge_events
    import math

    def at(deg):
        r = math.radians(deg)
        return unit([math.cos(r), math.sin(r)] + [0] * 14)

    z = Event("z", ["z1"], at(0), NOW - timedelta(hours=3), NOW - timedelta(hours=3))
    y = Event("y", ["y1"], at(20), NOW - timedelta(hours=2), NOW - timedelta(hours=2))
    x = Event("x", ["x1"], at(60), NOW - timedelta(hours=1), NOW)
    events = {"x": x, "y": y, "z": z}
    merged = merge_events(events, {"x", "y"}, NOW, threshold=0.72)
    assert set(events) == {"z"}
    assert merged == {"x": "z", "y": "z"}
    assert all(kept in events for kept in merged.values())
