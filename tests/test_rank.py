from datetime import timedelta

import numpy as np

from pipeline.models import Event
from pipeline.rank import score, select_today
from tests.fakes import NOW, art

ARTS = {}
_n = 0


def ev(eid, countries, hours_ago=1.0, topic="general"):
    """countries: list of country codes, one distinct source per entry."""
    global _n
    ids = []
    t = NOW - timedelta(hours=hours_ago)
    for c in countries:
        _n += 1
        aid = f"{eid}-{_n}"
        ARTS[aid] = art(aid, "x", t, source_id=f"src{_n}", country=c)
        ids.append(aid)
    return Event(eid, ids, np.zeros(4, np.float32), t, t, topic=topic)


def test_country_diversity_beats_volume_from_one_country():
    diverse = ev("d", ["US", "GB", "FR", "DE", "JP", "BR"])
    mono = ev("m", ["TR"] * 12)
    assert score(diverse, ARTS, NOW) > score(mono, ARTS, NOW)


def test_same_source_twice_counts_once():
    e = ev("s", ["GB", "GB"])
    one_source = Event("s1", [e.article_ids[0]], e.centroid, e.created_at, e.updated_at)
    ARTS[e.article_ids[1]].source_id = ARTS[e.article_ids[0]].source_id
    assert score(e, ARTS, NOW) == score(one_source, ARTS, NOW)


def test_freshness_decays():
    assert score(ev("f", ["US", "GB"], 1), ARTS, NOW) > score(ev("o", ["US", "GB"], 10), ARTS, NOW)


def test_sport_older_than_24h_and_single_source_excluded():
    events = {e.id: e for e in [
        ev("ok", ["US", "GB"]),
        ev("sport", ["US", "GB", "FR", "DE"], topic="sport"),
        ev("fun", ["US", "GB", "FR"], topic="entertainment"),
        ev("old", ["US", "GB", "FR"], hours_ago=25),
        ev("single", ["US"]),
    ]}
    assert select_today(events, ARTS, NOW) == ["ok"]


def test_returns_at_most_10():
    events = {f"e{i}": ev(f"e{i}", ["US", "GB", "FR"]) for i in range(15)}
    assert len(select_today(events, ARTS, NOW)) == 10


def test_cutoff_keeps_at_least_min_n():
    big = ev("big", ["US", "GB", "FR", "DE", "JP", "BR", "IN", "CN", "ZA", "AU"])
    small = [ev(f"s{i}", ["US", "GB"], hours_ago=20) for i in range(6)]
    events = {e.id: e for e in [big, *small]}
    out = select_today(events, ARTS, NOW)
    assert out[0] == "big" and len(out) == 5


def test_cutoff_drops_weak_tail_above_min_n():
    strong = [ev(f"st{i}", ["US", "GB", "FR", "DE", "JP", "BR"]) for i in range(7)]
    weak = [ev(f"w{i}", ["US", "GB"], hours_ago=20) for i in range(3)]
    events = {e.id: e for e in [*strong, *weak]}
    out = select_today(events, ARTS, NOW)
    assert set(out) == {e.id for e in strong}


def test_fewer_candidates_than_min():
    events = {e.id: e for e in [ev(f"c{i}", ["US", "GB"]) for i in range(3)]}
    assert len(select_today(events, ARTS, NOW)) == 3
