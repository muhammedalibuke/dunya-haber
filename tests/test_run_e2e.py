import json
from datetime import timedelta

from pipeline.geo import Gazetteer, Place
from pipeline.models import Source
from pipeline.run import run
from pipeline.topics import TopicConfig
from tests.fakes import NOW, FakeEmbedder, FakeTranslator, axis

GB = Source("bbc", "BBC", "https://bbc.example/rss", "GB", "en", "europe")
TR = Source("aa", "AA", "https://aa.example/rss", "TR", "tr", "europe")
JP = Source("nhk", "NHK", "https://nhk.example/rss", "JP", "ja", "asia")
DE = Source("dw", "DW", "https://dw.example/rss", "DE", "en", "europe")

EMB = FakeEmbedder({"quake": axis(0), "deprem": axis(0), "地震": axis(0), "budget": axis(1),
                    "match": axis(2), "celebrity": axis(3)})
GAZ = Gazetteer.from_entries([Place("Kobe", "city", 34.69, 135.19, "JP", 1_500_000),
                              Place("Japan", "country", 36.0, 138.0, "JP", 125_000_000)])
CFG = TopicConfig({"sport": ["sport"], "entertainment": ["magazin"]},
                  {"sport": ["sport"], "entertainment": ["magazin"]},
                  {"sport": ["match goal"], "entertainment": ["celebrity"]})


def rss(items):
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><description>{d}</description>"
        f"<pubDate>{p.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>{extra}</item>"
        for t, u, d, p, extra in items)
    return f'<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>x</title>{body}</channel></rss>'.encode()


def pages_run1():
    t = NOW - timedelta(hours=3)
    return {
        GB.url: rss([("Quake hits Kobe", "https://bbc.example/quake", "A strong quake struck Kobe. Read more", t, ""),
                     ("Budget passes", "https://bbc.example/budget", "MPs approved it.", t, "")]),
        TR.url: rss([("Kobe'de deprem", "https://aa.example/deprem", "Japonya'da deprem.", t + timedelta(minutes=5), "")]),
        JP.url: rss([("神戸で地震", "https://nhk.example/jishin", "地震", t + timedelta(minutes=10),
                      '<media:content url="https://nhk.example/img.jpg" medium="image"/>')]),
    }


def do_run(tmp_path, pages, now, sources=(GB, TR, JP)):
    return run(tmp_path / "state", tmp_path / "out", now, list(sources), pages.__getitem__,
               EMB, FakeTranslator(), GAZ, CFG)


def load(tmp_path, rel):
    return json.loads((tmp_path / "out" / rel).read_text(encoding="utf-8"))


def test_e2e_two_runs(tmp_path):
    rep = do_run(tmp_path, pages_run1(), NOW)
    assert rep.new_articles == 4 and rep.failures == {} and rep.today == 1
    today = load(tmp_path, "today.json")
    [ev] = today["events"]
    assert ev["source_count"] == 3
    assert ev["title"]["en"] == "Quake hits Kobe"
    assert ev["location"]["name"] == "Kobe"
    detail = load(tmp_path, f"events/{ev['id']}.json")
    assert detail["summary"]["en"] == "A strong quake struck Kobe."
    assert detail["summary"]["tr"] == "[tr] A strong quake struck Kobe."
    assert detail["images"][0]["source"] == "NHK"
    first_updated = ev["updated_at"]

    pages = pages_run1()
    pages[DE.url] = rss([("Quake toll rises in Kobe", "https://dw.example/toll", "More victims.",
                          NOW - timedelta(minutes=20), "")])
    rep2 = do_run(tmp_path, pages, NOW + timedelta(minutes=30), sources=(GB, TR, JP, DE))
    assert rep2.new_articles == 1
    [ev2] = load(tmp_path, "today.json")["events"]
    assert ev2["id"] == ev["id"]
    assert ev2["source_count"] == 4
    assert ev2["updated_at"] > first_updated
    d2 = load(tmp_path, f"events/{ev['id']}.json")
    assert len(d2["sources"]) == 4
    assert len({s["url"] for s in d2["sources"]}) == 4


def test_e2e_first_run_empty_state_and_no_today(tmp_path):
    def down(url):
        raise ConnectionError("down")
    rep = run(tmp_path / "state", tmp_path / "out", NOW, [GB, TR], down, EMB, FakeTranslator(), GAZ, CFG)
    assert rep.today == 0 and set(rep.failures) == {"bbc", "aa"}
    assert load(tmp_path, "today.json")["events"] == []
    assert load(tmp_path, "all.json")["events"] == []
    assert (tmp_path / "state" / "events.json.gz").exists()
