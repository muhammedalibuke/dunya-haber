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
