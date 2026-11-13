from pipeline.summarize import default_summary


def test_empty_input():
    assert default_summary("") == ""


def test_short_text_kept():
    assert default_summary("One. Two.") == "One. Two."


def test_cuts_at_sentence_boundary_within_limits():
    s = " ".join(f"Sentence number {i} is here." for i in range(1, 10))
    out = default_summary(s)
    assert out == " ".join(f"Sentence number {i} is here." for i in range(1, 5))


def test_char_limit_respected_without_mid_word_cut():
    s = "Word " * 200
    out = default_summary(s, max_chars=420)
    assert len(out) <= 421
    assert out.endswith("…")
    assert not out[:-1].endswith("Wor")


def test_read_more_tails_removed():
    assert default_summary("Big news today. Read more") == "Big news today."
    assert default_summary("Büyük haber. Devamı için tıklayın") == "Büyük haber."
    assert default_summary("Big news today. The post Big news appeared first on Example.") == "Big news today."
    assert default_summary("Big news [...]") == "Big news…"


def test_combined_summary_merges_sources_and_skips_repeats():
    from pipeline.summarize import combined_summary
    from tests.fakes import FakeEmbedder
    emb = FakeEmbedder({})
    items = [
        ("en", "A strong quake struck Kobe. Trains were halted. Read more"),
        ("en", "A strong quake struck Kobe. A tsunami warning was lifted an hour later."),
        ("ja", "死者は3人。"),
    ]
    out = combined_summary(items, emb)
    assert out == [("en", "A strong quake struck Kobe."), ("en", "Trains were halted."),
                   ("en", "A tsunami warning was lifted an hour later."), ("ja", "死者は3人。")]


def test_combined_summary_respects_limits():
    from pipeline.summarize import combined_summary
    from tests.fakes import FakeEmbedder
    items = [("en", " ".join(f"Fact number {i} about the event." for i in range(20)))]
    out = combined_summary(items, FakeEmbedder({}), max_sentences=6, max_chars=750)
    assert len(out) == 6
    out = combined_summary(items, FakeEmbedder({}), max_sentences=50, max_chars=200)
    assert sum(len(s) + 1 for _, s in out) <= 201


def test_combined_summary_empty():
    from pipeline.summarize import combined_summary
    from tests.fakes import FakeEmbedder
    assert combined_summary([("en", ""), ("tr", "   ")], FakeEmbedder({})) == []


def test_combined_summary_drops_cut_off_sentences():
    from pipeline.summarize import combined_summary
    from tests.fakes import FakeEmbedder
    items = [("en", "The board met on Wednesday. It was preparing to determine Huang’s"),
             ("en", "He said “we will recover.” Officials agreed")]
    out = combined_summary(items, FakeEmbedder({}))
    assert out == [("en", "The board met on Wednesday."), ("en", "He said “we will recover.”")]
