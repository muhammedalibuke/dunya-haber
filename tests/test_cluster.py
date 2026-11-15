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


WIRE = "Triumphant Democrats descend on COP31 snubbed by Trump"


def _existing(created, centroid=True):
    first = art("orig", WIRE, created, source_id="france24")
    e = Event("orig", ["orig"], unit(axis(0)) if centroid else None, created, created)
    return {"orig": e}, {"orig": first}


def test_republished_wire_story_joins_its_event_even_if_vectors_differ():
    events, known = _existing(NOW - timedelta(hours=3))
    copy = art("copy", "  triumphant democrats descend on COP31, snubbed by Trump. ", NOW, source_id="vanguard")
    assign(events, [copy], unit([[0] * 15 + [1]]).reshape(1, -1), NOW, existing=known)
    assert len(events) == 1
    assert events["orig"].article_ids == ["orig", "copy"]
    assert events["orig"].created_at == NOW - timedelta(hours=3)


def test_republished_copy_of_a_closed_story_does_not_start_a_new_event():
    events, known = _existing(NOW - timedelta(hours=60), centroid=False)
    copy = art("copy", WIRE, NOW, source_id="vanguard")
    assign(events, [copy], vecs([copy]), NOW, existing=known)
    assert set(events) == {"orig"}
    assert events["orig"].created_at == NOW - timedelta(hours=60)


def test_two_copies_in_the_same_batch_make_one_event():
    a = art("a", WIRE, NOW - timedelta(minutes=5), source_id="france24")
    b = art("b", WIRE, NOW, source_id="vanguard")
    events = {}
    assign(events, [a, b], np.vstack([unit(axis(2)), unit(axis(3))]), NOW)
    assert len(events) == 1


def test_short_generic_titles_are_not_merged_by_title():
    events = {}
    a = art("a", "Morning update", NOW - timedelta(hours=1), source_id="mee")
    b = art("b", "Morning update", NOW, source_id="mee")
    assign(events, [a, b], np.vstack([unit(axis(2)), unit(axis(3))]), NOW)
    assert len(events) == 2
