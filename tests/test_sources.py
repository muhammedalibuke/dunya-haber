from collections import Counter
from pathlib import Path

import pytest

from pipeline.models import REGIONS
from pipeline.sources import load_sources

ROOT = Path(__file__).resolve().parents[1]


def write(tmp_path, body):
    p = tmp_path / "s.yaml"
    p.write_text(body, encoding="utf-8")
    return p


GOOD = """
- {id: bbc, name: BBC, url: "https://feeds.bbci.co.uk/news/world/rss.xml", country: GB, lang: en, region: europe}
"""


def test_load_sources_parses_good_entry(tmp_path):
    [s] = load_sources(write(tmp_path, GOOD))
    assert (s.id, s.country, s.lang, s.region) == ("bbc", "GB", "en", "europe")


@pytest.mark.parametrize("bad", [
    '- {id: x1, name: X, url: "https://x.com/rss", country: XX, lang: en, region: europe}',
    '- {id: x1, name: X, url: "https://x.com/rss", country: GB, lang: english, region: europe}',
    '- {id: x1, name: X, url: "https://x.com/rss", country: GB, lang: en, region: mars}',
    '- {id: x1, name: X, country: GB, lang: en, region: europe}',
    '- {id: x1, name: X, url: "ftp://x.com/rss", country: GB, lang: en, region: europe}',
])
def test_load_sources_validates_fields(tmp_path, bad):
    with pytest.raises(ValueError, match="x1"):
        load_sources(write(tmp_path, bad))


def test_duplicate_id_or_url_rejected(tmp_path):
    with pytest.raises(ValueError, match="bbc"):
        load_sources(write(tmp_path, GOOD + GOOD))


def test_real_list_coverage():
    sources = load_sources(ROOT / "config" / "sources.yaml")
    assert len(sources) >= 150
    countries = {s.country for s in sources}
    assert len(countries) >= 100, len(countries)
    per_region = Counter(s.region for s in sources)
    for r in REGIONS:
        assert per_region[r] >= 10, (r, per_region[r])
    assert "TR" in countries
