"""Load-bearing behaviour for real-scale runs: no repeated work, bounded translation."""
import json
from datetime import timedelta

from pipeline.run import run
from tests.fakes import NOW, FakeTranslator
from tests.test_run_e2e import CFG, EMB, GAZ, GB, JP, TR, rss


class CountingTranslator(FakeTranslator):
    def __init__(self):
        super().__init__()
        self.pairs = []

    def translate(self, text, src, tgt):
        self.pairs.append((src, tgt, text))
        return super().translate(text, src, tgt)


def go(tmp_path, pages, now, tr=None, sources=(GB, TR, JP), **kw):
    tr = tr or CountingTranslator()
    rep = run(tmp_path / "state", tmp_path / "out", now, list(sources), pages.__getitem__, EMB, tr, GAZ, CFG, **kw)
    return rep, tr


def item(title, url, published, desc=""):
    return (title, url, desc, published, "")


def test_articles_older_than_48h_are_ignored(tmp_path):
    pages = {GB.url: rss([item("Quake old", "https://bbc.example/old", NOW - timedelta(days=9)),
                          item("Quake 49h", "https://bbc.example/49h", NOW - timedelta(hours=49))]),
             TR.url: rss([]), JP.url: rss([])}
    for _ in range(3):
        rep, tr = go(tmp_path, pages, NOW)
        assert rep.new_articles == 0 and tr.pairs == []


def test_undated_item_not_resurfacing_after_prune(tmp_path):
    undated = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>'
               b'<item><title>Static page item</title><link>https://bbc.example/static</link></item>'
               b'</channel></rss>')
    pages = {GB.url: undated, TR.url: rss([]), JP.url: rss([])}
    rep, _ = go(tmp_path, pages, NOW)
    assert rep.new_articles == 1
    go(tmp_path, pages, NOW + timedelta(days=7, hours=12))  # this run prunes the old event
    rep, _ = go(tmp_path, pages, NOW + timedelta(days=8))
    assert rep.new_articles == 0


def test_single_source_events_are_not_translated(tmp_path):
    t = NOW - timedelta(hours=1)
    pages = {GB.url: rss([item("Budget passes", "https://bbc.example/b", t, "MPs approved.")]),
             TR.url: rss([]), JP.url: rss([])}
    rep, tr = go(tmp_path, pages, NOW)
    assert rep.new_articles == 1 and tr.pairs == []


def test_pivot_reuses_english_and_late_joiner_gets_translated(tmp_path):
    t = NOW - timedelta(hours=2)
    pages = {GB.url: rss([item("Quake hits Kobe", "https://bbc.example/q", t, "A strong quake.")]),
             TR.url: rss([]), JP.url: rss([])}
    _, tr = go(tmp_path, pages, NOW)
    assert tr.pairs == []  # still single-source
    pages[JP.url] = rss([item("神戸で地震", "https://nhk.example/j", t + timedelta(minutes=5), "地震")])
    _, tr = go(tmp_path, pages, NOW + timedelta(minutes=30))
    srcs = {(s, g) for s, g, _ in tr.pairs}
    assert ("ja", "tr") not in srcs
    assert ("ja", "en") in srcs and ("en", "tr") in srcs
    titles = {s["title"]["tr"] for s in json.loads(
        next((tmp_path / "out" / "events").iterdir()).read_text())["sources"]}
    assert titles == {"[tr] Quake hits Kobe", "[tr] [en] 神戸で地震"}


def test_translation_budget_defers_work_to_next_run(tmp_path):
    t = NOW - timedelta(hours=2)
    pages = {GB.url: rss([item("Quake hits Kobe", "https://bbc.example/q", t, "A strong quake.")]),
             TR.url: rss([item("Kobe'de deprem", "https://aa.example/d", t, "Deprem.")]), JP.url: rss([])}
    _, tr = go(tmp_path, pages, NOW, translate_budget_s=0)
    assert tr.pairs == []
    today = json.loads((tmp_path / "out" / "today.json").read_text())
    assert today["events"][0]["title"]["tr"]  # falls back to an original title, never empty
    _, tr = go(tmp_path, pages, NOW + timedelta(minutes=30))
    assert tr.pairs  # deferred work done on the next run
    today = json.loads((tmp_path / "out" / "today.json").read_text())
    assert today["events"][0]["title"]["tr"] == "[tr] Quake hits Kobe"


def test_summary_combines_several_sources(tmp_path):
    t = NOW - timedelta(hours=2)
    pages = {GB.url: rss([item("Quake hits Kobe", "https://bbc.example/q", t,
                               "A strong quake struck Kobe. Trains were halted.")]),
             TR.url: rss([item("Kobe'de deprem", "https://aa.example/d", t, "Tsunami uyarısı kaldırıldı.")]),
             JP.url: rss([])}
    go(tmp_path, pages, NOW)
    d = json.loads(next((tmp_path / "out" / "events").iterdir()).read_text())
    assert d["summary"]["en"] == "A strong quake struck Kobe. Trains were halted. [en] Tsunami uyarısı kaldırıldı."
    assert d["summary"]["tr"] == "[tr] A strong quake struck Kobe. [tr] Trains were halted. Tsunami uyarısı kaldırıldı."


def test_old_short_summaries_are_rebuilt_once(tmp_path):
    from pipeline.state import load_state, save_state
    t = NOW - timedelta(hours=2)
    pages = {GB.url: rss([item("Quake hits Kobe", "https://bbc.example/q", t, "A strong quake struck Kobe.")]),
             TR.url: rss([item("Kobe'de deprem", "https://aa.example/d", t, "Tsunami uyarısı kaldırıldı.")]),
             JP.url: rss([])}
    go(tmp_path, pages, NOW)
    st = load_state(tmp_path / "state")
    for e in st.events.values():
        e.summary_en, e.summary_tr, e.summary_v = "Old.", "Eski.", 0
    save_state(st, tmp_path / "state")
    go(tmp_path, pages, NOW + timedelta(minutes=30))
    d = json.loads(next((tmp_path / "out" / "events").iterdir()).read_text())
    assert d["summary"]["en"].startswith("A strong quake struck Kobe.")
