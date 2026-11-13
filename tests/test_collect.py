from datetime import datetime, timezone
from pathlib import Path

from pipeline.collect import canonical_url, clean_text, fetch_all, parse_feed
from pipeline.models import Source

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
SRC = Source("ex", "Example", "https://example.com/rss", "GB", "en", "europe")


def read(name):
    return (FIX / name).read_bytes()


def test_canonical_url_strips_tracking():
    assert canonical_url("http://Example.com/a/?utm_source=x&id=3#top") == "https://example.com/a?id=3"
    assert canonical_url("https://example.com/a?fbclid=1&gclid=2&ref=tw") == "https://example.com/a"


def test_clean_text_strips_tags_and_entities():
    assert clean_text("<p>A &amp; <b>B</b></p>\n\n  C") == "A & B C"


def test_parse_rss_basic():
    arts = parse_feed(read("rss_basic.xml"), SRC, NOW)
    by_url = {a.url: a for a in arts}
    quake = by_url["https://example.com/world/quake"]
    assert "<" not in quake.title and "alert(1)" not in quake.title
    assert quake.title.endswith("Kobe")
    assert quake.description == "A strong earthquake struck western Japan on Thursday."
    assert quake.published == datetime(2026, 11, 13, 9, 30, tzinfo=timezone.utc)
    assert (quake.source_id, quake.country, quake.lang) == ("ex", "GB", "en")
    assert len(quake.id) == 16


def test_empty_title_dropped():
    arts = parse_feed(read("rss_basic.xml"), SRC, NOW)
    assert all(a.title for a in arts)
    assert "https://example.com/world/empty-title" not in {a.url for a in arts}


def test_parse_atom_basic():
    [a] = parse_feed(read("atom_basic.xml"), SRC, NOW)
    assert a.url == "https://atom.example.org/politics/budget"
    assert a.description == "The parliament approved the 2027 budget."
    assert a.published == datetime(2026, 11, 13, 8, 0, tzinfo=timezone.utc)


def test_image_from_media_content_thumbnail_enclosure():
    imgs = {a.title: a.image_url for a in parse_feed(read("media_variants.xml"), SRC, NOW)}
    assert imgs["With media content"] == "https://m.example.com/img1.jpg"
    assert imgs["With thumbnail"] == "https://m.example.com/img2.jpg"
    assert imgs["With enclosure"] == "https://m.example.com/img3.png"
    assert imgs["With audio enclosure"] is None


def test_missing_or_future_date_clamped_to_fetched_at():
    by_title = {a.title: a for a in parse_feed(read("rss_basic.xml"), SRC, NOW)}
    assert by_title["No date story"].published == NOW
    assert by_title["Future story"].published == NOW


def test_tags_collected():
    arts = parse_feed(read("rss_basic.xml"), SRC, NOW)
    quake = next(a for a in arts if a.url.endswith("quake"))
    assert quake.tags == ["world", "asia"]


def test_broken_feed_reported_not_raised():
    good = SRC
    bad = Source("bad", "Bad", "https://bad.example.com/rss", "US", "en", "americas")
    pages = {good.url: read("rss_basic.xml"), bad.url: read("broken.html")}
    arts, failures = fetch_all([good, bad], pages.__getitem__, NOW)
    assert arts and all(a.source_id == "ex" for a in arts)
    assert "bad" in failures


def test_fetch_exception_reported_not_raised():
    def boom(url):
        raise TimeoutError("timed out")
    arts, failures = fetch_all([SRC], boom, NOW)
    assert arts == [] and "timed out" in failures["ex"]


def test_duplicate_urls_across_sources_deduped():
    other = Source("ex2", "Example 2", "https://example2.com/rss", "US", "en", "americas")
    pages = {SRC.url: read("rss_basic.xml"), other.url: read("rss_basic.xml")}
    arts, _ = fetch_all([SRC, other], pages.__getitem__, NOW)
    urls = [a.url for a in arts]
    assert len(urls) == len(set(urls))
