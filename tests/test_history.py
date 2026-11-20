from datetime import datetime, timezone

from pipeline.history import parse_onthisday, refresh_history
from tests.fakes import FakeTranslator


def page(title, thumb=True):
    p = {"titles": {"normalized": title},
         "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}}}
    if thumb:
        p["thumbnail"] = {"source": f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/{title[:3]}.jpg/320px-{title[:3]}.jpg"}
    return p


PAYLOAD = {
    "selected": [
        {"text": "The Nuremberg trials begin.", "year": 1945, "pages": [page("Nuremberg trials")]},
        {"text": "Zarya, the first ISS module, is launched.", "year": 1998, "pages": [page("Zarya")]},
        {"text": "No page here.", "year": 1910, "pages": []},
        {"text": "Bad link.", "year": 1900, "pages": [{"content_urls": {"desktop": {"page": "javascript:alert(1)"}}}]},
    ],
    "births": [{"text": f"Person {i}, scientist", "year": 1800 + i, "pages": [page(f"Person {i}", thumb=i % 2 == 0)]}
               for i in range(50)],
    "deaths": [{"text": "Leo Tolstoy, Russian writer", "year": 1910, "pages": [page("Leo Tolstoy")]}],
}


def test_parse_keeps_selected_events_newest_first_with_safe_links():
    h = parse_onthisday(PAYLOAD)
    assert [e["year"] for e in h["events"]] == [1998, 1945, 1910, 1900]
    zarya = h["events"][0]
    assert zarya["url"] == "https://en.wikipedia.org/wiki/Zarya"
    assert zarya["thumb"].endswith("/320px-Zar.jpg") and zarya["image"].endswith("/960px-Zar.jpg")
    assert h["events"][2]["url"] is None and h["events"][2]["thumb"] is None
    assert h["events"][3]["url"] is None


def test_births_are_the_newest_twenty_with_a_photo():
    h = parse_onthisday(PAYLOAD)
    years = [b["year"] for b in h["births"]]
    assert len(years) == 20 and years[0] == 1848 and all(y % 2 == 0 for y in years)
    assert [d["year"] for d in h["deaths"]] == [1910]


def test_refresh_uses_the_istanbul_date_and_translates():
    urls = []

    def get_json(url):
        urls.append(url)
        return PAYLOAD

    now = datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc)  # 01:30 on 20 Nov in Istanbul
    h = refresh_history(None, now, get_json, FakeTranslator())
    assert urls == ["https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/11/20"]
    assert h["date"] == "2026-11-20"
    assert h["events"][0]["text"] == {"tr": "[tr] Zarya, the first ISS module, is launched.",
                                      "en": "Zarya, the first ISS module, is launched."}
    assert refresh_history(h, now, get_json, FakeTranslator()) is h and len(urls) == 1  # once a day


def test_refresh_keeps_old_data_when_fetch_fails_and_english_when_translation_fails():
    def boom(url):
        raise RuntimeError("offline")

    old = {"date": "2026-11-19", "events": []}
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    assert refresh_history(old, now, boom, FakeTranslator()) is old

    class Broken:
        def translate(self, text, src, tgt):
            raise RuntimeError("no model")

    h = refresh_history(None, now, lambda u: PAYLOAD, Broken())
    assert h["events"][0]["text"]["tr"] == h["events"][0]["text"]["en"]
