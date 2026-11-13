from datetime import timedelta

import numpy as np

from pipeline.models import Event, Location, State
from pipeline.publish import build_site_data, write_site_data
from tests.fakes import NOW, art


def state_with_event(image=True):
    a1 = art("a1", "神戸で地震", NOW - timedelta(hours=3), source_id="nhk", country="JP", lang="ja",
             image_url="https://img.example/1.jpg" if image else None, source_name="NHK")
    a1.title_tr, a1.title_en = "Kobe'de deprem", "Earthquake in Kobe"
    a2 = art("a2", "Quake hits Kobe", NOW - timedelta(hours=2), source_id="bbc", country="GB",
             desc="A strong quake struck. " * 3, source_name="BBC")
    a2.title_tr, a2.title_en = "Deprem Kobe'yi vurdu", "Quake hits Kobe"
    e = Event("a1", ["a1", "a2"], np.zeros(4, np.float32), a1.published, a2.published,
              location=Location("city", "Kobe", 34.69, 135.19, "JP"),
              summary_tr="Güçlü bir deprem.", summary_en="A strong quake struck.")
    single = art("s1", "Local story", NOW - timedelta(hours=1), source_id="x")
    es = Event("s1", ["s1"], np.zeros(4, np.float32), single.published, single.published)
    return State(articles={"a1": a1, "a2": a2, "s1": single}, events={"a1": e, "s1": es})


def test_build_site_data_shapes():
    files = build_site_data(state_with_event(), ["a1"], NOW)
    assert set(files) == {"today.json", "all.json", "events/a1.json"}
    today = files["today.json"]
    assert today["generated_at"] == NOW.isoformat()
    [s] = today["events"]
    assert set(s) == {"id", "title", "country", "source_count", "updated_at", "topic", "location"}
    assert s["title"] == {"tr": "Deprem Kobe'yi vurdu", "en": "Quake hits Kobe"}  # English source preferred
    assert s["country"] == {"code": "JP", "name": {"tr": "Japonya", "en": "Japan"}}
    assert s["source_count"] == 2
    assert s["location"] == {"level": "city", "name": "Kobe", "lat": 34.69, "lon": 135.19, "country": "JP"}
    d = files["events/a1.json"]
    assert d["summary"] == {"tr": "Güçlü bir deprem.", "en": "A strong quake struck.", "ai": False}
    assert d["images"] == [{"url": "https://img.example/1.jpg", "source": "NHK"}]
    assert [x["name"] for x in d["sources"]] == ["NHK", "BBC"]
    assert d["sources"][0]["title"] == {"orig": "神戸で地震", "tr": "Kobe'de deprem", "en": "Earthquake in Kobe"}
    assert "description" not in str(d)


def test_all_lists_multi_source_events_only():
    files = build_site_data(state_with_event(), [], NOW)
    assert [e["id"] for e in files["all.json"]["events"]] == ["a1"]
    assert files["today.json"]["events"] == []


def test_event_without_image_has_no_images():
    files = build_site_data(state_with_event(image=False), ["a1"], NOW)
    assert files["events/a1.json"]["images"] == []


def test_images_up_to_4_one_per_source_popular_first():
    from pipeline.publish import MAX_IMAGES
    arts, ids = {}, []
    for i in range(7):
        a = art(f"p{i}", f"Story {i}", NOW - timedelta(hours=3, minutes=-i), source_id=f"s{i % 6}",
                source_name=f"S{i % 6}", image_url=f"https://img.example/{i}.jpg")
        a.source_tier = 1 if i == 4 else 3
        arts[a.id] = a
        ids.append(a.id)
    arts["p2"].image_url = None
    e = Event("p0", ids, np.zeros(4, np.float32), NOW - timedelta(hours=3), NOW)
    d = build_site_data(State(articles=arts, events={"p0": e}), ["p0"], NOW)["events/p0.json"]
    assert MAX_IMAGES == 4
    assert d["images"] == [{"url": "https://img.example/4.jpg", "source": "S4"},
                           {"url": "https://img.example/0.jpg", "source": "S0"},
                           {"url": "https://img.example/1.jpg", "source": "S1"},
                           {"url": "https://img.example/3.jpg", "source": "S3"}]


def test_write_site_data_clears_old_event_files(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "stale.json").write_text("{}")
    write_site_data(tmp_path, build_site_data(state_with_event(), ["a1"], NOW))
    assert sorted(p.name for p in (tmp_path / "events").iterdir()) == ["a1.json"]
    assert "Japonya" in (tmp_path / "today.json").read_text(encoding="utf-8")


def test_detail_lists_top_5_sources_by_tier_and_reports_total():
    from pipeline.publish import MAX_SOURCES_SHOWN
    arts, ids = {}, []
    for i in range(8):
        a = art(f"x{i}", f"Story {i}", NOW - timedelta(hours=2, minutes=-i), source_id=f"s{i}",
                source_name=f"S{i}")
        a.source_tier = 1 if i in (6, 7) else (2 if i == 5 else 3)
        arts[a.id] = a
        ids.append(a.id)
    e = Event("x0", ids, np.zeros(4, np.float32), NOW - timedelta(hours=2), NOW)
    files = build_site_data(State(articles=arts, events={"x0": e}), ["x0"], NOW)
    d = files["events/x0.json"]
    assert MAX_SOURCES_SHOWN == 5
    assert [s["name"] for s in d["sources"]] == ["S6", "S7", "S5", "S0", "S1"]
    assert d["source_total"] == 8
