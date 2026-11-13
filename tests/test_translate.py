from pipeline.translate import translate_articles, translate_cached
from tests.fakes import NOW, FakeTranslator, art


def test_same_language_passthrough_without_calls():
    tr, cache = FakeTranslator(), {}
    assert translate_cached("Merhaba", "tr", "tr", cache, tr) == "Merhaba"
    assert tr.calls == 0 and cache == {}


def test_second_call_served_from_cache():
    tr, cache = FakeTranslator(), {}
    assert translate_cached("Hello", "en", "tr", cache, tr) == "[tr] Hello"
    assert translate_cached("Hello", "en", "tr", cache, tr) == "[tr] Hello"
    assert tr.calls == 1


def test_unsupported_pair_returns_original_and_is_not_cached():
    tr, cache = FakeTranslator(unsupported={"xx"}), {}
    assert translate_cached("Bonjour", "xx", "tr", cache, tr) == "Bonjour"
    assert cache == {}


def test_empty_text_not_translated():
    tr, cache = FakeTranslator(), {}
    assert translate_cached("", "en", "tr", cache, tr) == ""
    assert tr.calls == 0


def test_translate_articles_fills_both_fields():
    tr, cache = FakeTranslator(), {}
    a_en = art("a1", "Quake hits Kobe", NOW, lang="en")
    a_ja = art("a2", "神戸で地震", NOW, lang="ja")
    translate_articles([a_en, a_ja], cache, tr)
    assert (a_en.title_tr, a_en.title_en) == ("[tr] Quake hits Kobe", "Quake hits Kobe")
    assert (a_ja.title_tr, a_ja.title_en) == ("[tr] [en] 神戸で地震", "[en] 神戸で地震")  # pivot via English


def test_translator_exception_falls_back_to_original():
    class Boom:
        def translate(self, text, src, tgt):
            raise RuntimeError("model crashed")
    assert translate_cached("Hello", "en", "tr", {}, Boom()) == "Hello"


def test_exhausted_budget_leaves_fields_empty_for_next_run():
    from pipeline.translate import Budget
    tr, cache = FakeTranslator(), {}
    a = art("a1", "Quake hits Kobe", NOW, lang="en")
    translate_articles([a], cache, tr, budget=Budget(0))
    assert (a.title_tr, a.title_en, tr.calls) == (None, None, 0)
