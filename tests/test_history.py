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


def test_deaths_are_the_newest_twenty_with_a_photo_and_births_are_dropped():
    payload = {**PAYLOAD, "deaths": PAYLOAD["births"]}
    h = parse_onthisday(payload)
    years = [d["year"] for d in h["deaths"]]
    assert len(years) == 20 and years[0] == 1848 and all(y % 2 == 0 for y in years)
    assert "births" not in h


def test_refresh_uses_the_istanbul_date_and_translates():
    urls = []

    def get_json(url):
        urls.append(url)
        return PAYLOAD

    now = datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc)  # 01:30 on 20 Nov in Istanbul
    h = refresh_history(None, now, get_json, FakeTranslator())
    assert urls[0] == "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/11/20"
    fetched = len(urls)
    assert h["date"] == "2026-11-20"
    assert h["events"][0]["text"] == {"tr": "[tr] Zarya, the first ISS module, is launched.",
                                      "en": "Zarya, the first ISS module, is launched."}
    assert refresh_history(h, now, get_json, FakeTranslator()) is h and len(urls) == fetched  # once a day


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


def test_life_years_move_out_of_parentheses():
    h = parse_onthisday({
        "deaths": [{"text": "Andy Paley, American songwriter (born 1952)", "year": 2024, "pages": [page("Andy Paley")]},
                   {"text": "Someone, painter", "year": 1990, "pages": [page("Someone")]}],
    })
    d = h["deaths"][0]
    assert d["text"] == "Andy Paley, American songwriter" and d["born"] == "1952"
    assert h["deaths"][1]["born"] is None


def test_refresh_redoes_a_list_made_by_an_older_version():
    calls = []
    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    old = {"date": "2026-11-20", "events": []}  # no version: made before life years were split out
    h = refresh_history(old, now, lambda u: calls.append(u) or PAYLOAD, FakeTranslator())
    assert calls and h is not old


def test_context_holidays_and_places():
    from pipeline.geo import Gazetteer, Place

    def gazetteer_fixture():
        return Gazetteer.from_entries([Place("Mexico", "country", 23.6, -102.5, "MX", 126_000_000)])
    payload = {
        "selected": [{"text": "The Mexican Revolution begins in Mexico.", "year": 1910, "pages": [
            {**page("Mexican Revolution"), "extract": "The Mexican Revolution was an armed struggle. It lasted a decade. "
                                                      "It changed Mexico. Many died."}]}],
        "holidays": [{"text": "World Children's Day", "pages": [page("World Children's Day")]},
                     {"text": "Christian feast day: Edmund the Martyr", "pages": []},
                     {"text": "Revolution Day (Mexico)", "pages": []}],
    }
    h = parse_onthisday(payload)
    assert h["events"][0]["extract"] == "The Mexican Revolution was an armed struggle. It lasted a decade. It changed Mexico."
    assert [x["text"] for x in h["holidays"]] == ["World Children's Day", "Revolution Day (Mexico)"]

    now = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    out = refresh_history(None, now, lambda u: payload, FakeTranslator(), gaz=gazetteer_fixture())
    ev = out["events"][0]
    assert ev["extract"]["tr"].startswith("[tr] The Mexican Revolution")
    assert ev["location"]["country"] == "MX"
    assert out["holidays"][0]["text"]["tr"] == "[tr] World Children's Day"


def test_life_years_without_a_dot_and_holiday_background():
    h = parse_onthisday({
        "deaths": [{"text": "Bernard Rose, English organist and composer (b 1916)", "year": 1996, "pages": [page("Bernard Rose")]}],
        "holidays": [{"text": "World Television Day (United Nations observance)", "pages": [
            {**page("World Television Day"), "extract": "World Television Day is marked on 21 November. It was set up by "
                                                        "the UN in 1996. It honours television. More text here."}]}],
    })
    assert h["deaths"][0]["text"] == "Bernard Rose, English organist and composer" and h["deaths"][0]["born"] == "1916"
    assert h["holidays"][0]["extract"] == "World Television Day is marked on 21 November. It was set up by the UN in 1996."
    out = refresh_history(None, datetime(2026, 11, 21, 9, tzinfo=timezone.utc), lambda u: {"holidays": [
        {"text": "World Television Day", "pages": [{**page("World Television Day"), "extract": "A day. For TV."}]}]},
        FakeTranslator())
    assert out["holidays"][0]["extract"] == {"tr": "[tr] A day. For TV.", "en": "A day. For TV."}


TR_MAIN = """<div class="mw-parser-output"><h2><span id="G.C3.BCn.C3.BCn_S.C3.B6z.C3.BC"></span>Günün Sözü</h2>
<div class="quote"><p>“ · Büyük adam büyüklüğünü küçük adama davranışıyla gösterir. · „</p>
<p>—<a href="/wiki/Aldous_Huxley" title="Aldous Huxley">Aldous Huxley</a></p></div>
<h2>Kardeş projeler</h2><p>Vikisöz, kâr amacı gütmeyen …</p></div>"""

EN_MAIN = """<div class="mw-parser-output"><table><tr><td><h2>Quote of the day</h2>
<table><tr><td>Courage is not the absence of fear, but rather the judgment that something else is more important than fear.
<br/></td></tr><tr><td>~ <a href="/wiki/Ambrose_Redmoon" title="Ambrose Redmoon">Ambrose Redmoon</a> ~</td></tr></table>
</td></tr></table><h2>Selected pages</h2></div>"""


def test_quote_of_the_day_from_wikiquote_main_pages():
    from pipeline.history import parse_quote
    tr = parse_quote(TR_MAIN, "Günün Sözü", "https://tr.wikiquote.org")
    assert tr == {"text": "Büyük adam büyüklüğünü küçük adama davranışıyla gösterir.", "author": "Aldous Huxley",
                  "url": "https://tr.wikiquote.org/wiki/Aldous_Huxley"}
    en = parse_quote(EN_MAIN, "Quote of the day", "https://en.wikiquote.org")
    assert en["text"].startswith("Courage is not the absence of fear") and en["text"].endswith("than fear.")
    assert en["author"] == "Ambrose Redmoon" and en["url"] == "https://en.wikiquote.org/wiki/Ambrose_Redmoon"
    assert parse_quote("<p>nothing here</p>", "Quote of the day", "https://en.wikiquote.org") is None


def test_refresh_adds_each_languages_own_quote():
    def get_json(url):
        if "tr.wikiquote" in url:
            return {"parse": {"text": TR_MAIN}}
        if "en.wikiquote" in url:
            return {"parse": {"text": EN_MAIN}}
        return PAYLOAD

    h = refresh_history(None, datetime(2026, 11, 21, 9, tzinfo=timezone.utc), get_json, FakeTranslator())
    assert h["quote"]["tr"]["author"] == "Aldous Huxley" and h["quote"]["en"]["author"] == "Ambrose Redmoon"

    def no_quotes(url):
        if "wikiquote" in url:
            raise RuntimeError("down")
        return PAYLOAD

    h = refresh_history(None, datetime(2026, 11, 21, 9, tzinfo=timezone.utc), no_quotes, FakeTranslator())
    assert h["quote"] == {} and h["events"]
