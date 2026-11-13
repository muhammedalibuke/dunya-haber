import pytest
from pathlib import Path

from pipeline.embed import embed_text
from pipeline.topics import (TopicConfig, article_topic, event_topic, load_topic_config,
                             prototype_vectors)
from tests.fakes import NOW, FakeEmbedder, art, axis

ROOT = Path(__file__).resolve().parents[1]
CFG = TopicConfig(
    url_keywords={"sport": ["sport", "spor"], "entertainment": ["entertainment", "magazin"]},
    tag_keywords={"sport": ["sport", "football"], "entertainment": ["magazin", "celebrity"]},
    prototypes={"sport": ["match goal league"], "entertainment": ["celebrity star"]},
)
EMB = FakeEmbedder({"match": axis(2), "goal": axis(2), "celebrity": axis(3), "star": axis(3)})
PROTOS = prototype_vectors(CFG, EMB)


def topic(a):
    return article_topic(a, EMB.encode([embed_text(a)])[0], CFG, PROTOS)


def test_url_path_keyword_sport():
    a = art("a", "Late winner in derby", NOW, url="https://x.com/sport/football/derby")
    assert topic(a) == "sport"


def test_url_keyword_must_be_path_segment():
    a = art("a", "Transport strike", NOW, url="https://x.com/news/transport-strike")
    assert topic(a) == "general"


def test_tag_keyword_entertainment():
    a = art("a", "Something", NOW, tags=["magazin"])
    assert topic(a) == "entertainment"


def test_prototype_similarity_sport():
    a = art("a", "Last-minute goal decides the match", NOW)
    assert topic(a) == "sport"


def test_plain_politics_is_general():
    a = art("a", "Parliament passes the budget", NOW)
    assert topic(a) == "general"


def test_event_topic_majority():
    assert event_topic(["sport", "general", "general"]) == "general"
    assert event_topic(["sport", "sport", "general"]) == "sport"
    assert event_topic(["sport", "entertainment"]) == "general"
    assert event_topic([]) == "general"


def test_real_config_loads():
    cfg = load_topic_config(ROOT / "config" / "topics.yaml")
    assert "spor" in cfg.url_keywords["sport"]
    assert "magazin" in cfg.url_keywords["entertainment"]
    assert cfg.prototypes["sport"] and cfg.prototypes["entertainment"]


@pytest.mark.parametrize("url", [
    "https://x.com/world/at-least-40-people-killed-in-sudan-attack",
    "https://x.com/news/thousands-of-people-flee-floods",
    "https://x.com/politics/sports-minister-resigns-over-scandal",
    "https://x.com/world/vip-flight-crash-kills-12",
    "https://x.com/people/2026/11/13/story",
])
def test_slug_words_do_not_set_topic(url):
    real = load_topic_config(ROOT / "config" / "topics.yaml")
    a = art("a", "Something happened", NOW, url=url)
    assert article_topic(a, EMB.encode([embed_text(a)])[0], real, PROTOS) == "general"


def test_section_segment_still_sets_topic():
    real = load_topic_config(ROOT / "config" / "topics.yaml")
    a = art("a", "Late winner", NOW, url="https://x.com/sports/football/late-winner")
    assert article_topic(a, EMB.encode([embed_text(a)])[0], real, PROTOS) == "sport"


def test_real_config_has_no_ambiguous_section_words():
    cfg = load_topic_config(ROOT / "config" / "topics.yaml")
    for word in ("people", "vip", "lifestyle"):
        assert word not in cfg.url_keywords["entertainment"]
