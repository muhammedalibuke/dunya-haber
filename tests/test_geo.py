from pathlib import Path

import pytest

from pipeline.geo import Gazetteer, Place, country_of_event, locate_event
from pipeline.models import Location

ROOT = Path(__file__).resolve().parents[1]

P = Place
ENTRIES = [
    P("Japan", "country", 36.0, 138.0, "JP", 125_000_000),
    P("Kobe", "city", 34.69, 135.19, "JP", 1_500_000),
    P("Tokyo", "city", 35.68, 139.69, "JP", 9_000_000),
    P("Oregon", "region", 44.0, -120.5, "US", 0),
    P("Georgia", "country", 42.0, 43.5, "GE", 3_700_000),
    P("Georgia", "region", 32.7, -83.4, "US", 0),
    P("Tbilisi", "city", 41.69, 44.83, "GE", 1_000_000),
    P("Atlanta", "city", 33.75, -84.39, "US", 500_000),
    P("Washington", "city", 38.9, -77.04, "US", 700_000),
    P("Washington", "region", 47.4, -120.5, "US", 0),
    P("United States", "country", 39.8, -98.6, "US", 330_000_000),
    P("Hyderabad", "city", 17.38, 78.48, "IN", 6_800_000),
    P("Hyderabad", "city", 25.39, 68.37, "PK", 1_700_000),
    P("India", "country", 22.0, 79.0, "IN", 1_400_000_000),
    P("Pakistan", "country", 30.0, 70.0, "PK", 240_000_000),
    P("Nice", "city", 43.70, 7.27, "FR", 340_000),
    P("Mobile", "city", 30.69, -88.04, "US", 190_000),
    P("New York City", "city", 40.71, -74.0, "US", 8_000_000),
    P("New York", "region", 43.0, -75.0, "US", 0),
]
GAZ = Gazetteer.from_entries(ENTRIES, stoplist={"nice", "mobile"})


def loc(titles, sources=("GB",)):
    return locate_event(titles, list(sources), GAZ)


def test_unique_city_gives_city_level():
    l = loc(["Earthquake hits Kobe"])
    assert (l.level, l.name, l.country) == ("city", "Kobe", "JP")
    assert l.lat == pytest.approx(34.69)


def test_us_state_gives_region_level():
    l = loc(["Wildfires spread across Oregon"])
    assert (l.level, l.name, l.country) == ("region", "Oregon", "US")


def test_possessive_and_turkish_suffix_stripped():
    assert loc(["Kobe's mayor speaks"]).name == "Kobe"
    assert loc(["Kobe'de deprem"]).name == "Kobe"


def test_longest_match_wins():
    l = loc(["Floods in New York City subway"])
    assert (l.level, l.name) == ("city", "New York City")


def test_ambiguous_name_resolved_by_other_country_in_titles():
    l = loc(["Protests in Georgia", "Police clash with crowds in Tbilisi"])
    assert l.country == "GE"
    l = loc(["Storm hits Georgia", "Atlanta airport closed", "Georgia storm toll rises"])
    assert (l.level, l.name, l.country) == ("region", "Georgia", "US")


def test_ambiguous_resolved_by_majority_source_country():
    l = loc(["Blast in Hyderabad"], sources=["PK", "PK", "GB"])
    assert (l.name, l.country) == ("Hyderabad", "PK")


def test_ambiguous_unresolved_across_countries_is_none():
    assert loc(["Blast in Hyderabad"], sources=["PK", "IN", "GB"]) is None


def test_ambiguous_within_one_country_falls_back_to_country():
    l = loc(["Washington braces for storm"], sources=["GB", "FR"])
    assert (l.level, l.country) == ("country", "US")
    assert l.name == "United States"


def test_stoplisted_word_never_matches():
    assert loc(["Nice weather in Mobile"]) is None


def test_lowercase_words_do_not_match():
    assert loc(["the georgia peach festival"]) is None


def test_most_frequent_place_across_titles_wins():
    l = loc(["Tokyo markets fall", "Kobe quake", "Kobe rescue", "Kobe toll rises"])
    assert l.name == "Kobe"


def test_tie_prefers_more_specific_level():
    l = loc(["Quake hits Kobe, Japan"])
    assert l.name == "Kobe"


def test_no_place_returns_none():
    assert loc(["Central bank raises rates"]) is None


def test_country_of_event_fallback_to_sources():
    assert country_of_event(Location("city", "Kobe", 1, 2, "JP"), ["GB"]) == "JP"
    assert country_of_event(None, ["GB", "FR", "FR"]) == "FR"
    assert country_of_event(None, []) == ""


def test_real_gazetteer_loads_and_finds_basics():
    gaz = Gazetteer.load(ROOT / "data" / "gazetteer.json.gz", ROOT / "config" / "place_stoplist.txt")
    assert locate_event(["Wildfires spread across Oregon"], ["US"], gaz).name == "Oregon"
    assert locate_event(["Earthquake hits Kobe"], ["GB"], gaz).country == "JP"
    assert locate_event(["Talks in Ankara"], ["TR"], gaz).country == "TR"
    assert locate_event(["U.S. imposes new tariffs"], ["GB"], gaz).country == "US"
    assert locate_event(["Nice weather"], ["FR"], gaz) is None


def test_turkish_dotted_capital_i_and_diacritics_fold():
    gaz = Gazetteer.from_entries([P("Istanbul", "city", 41.0, 28.9, "TR", 15_000_000),
                                  P("Belém", "city", -1.45, -48.5, "BR", 1_400_000)])
    assert locate_event(["İstanbul'da şiddetli yağış"], ["TR"], gaz).name == "Istanbul"
    assert locate_event(["Talks in Belem"], ["BR"], gaz).name == "Belém"


def test_short_non_country_names_ignored():
    gaz = Gazetteer.from_entries([P("In'chuan'", "city", 38.4, 106.2, "CN", 1_400_000),
                                  P("US", "country", 39.8, -98.6, "US", 330_000_000)])
    assert locate_event(["Floods In Valencia"], ["ES"], gaz) is None
    assert locate_event(["US tariffs"], ["GB"], gaz).country == "US"


def test_same_country_same_level_duplicates_take_most_populous():
    gaz = Gazetteer.from_entries([P("New Delhi", "city", 28.62, 77.21, "IN", 300_000),
                                  P("New Delhi", "city", 28.65, 77.23, "IN", 11_000_000)])
    l = locate_event(["New Delhi chokes on smog"], ["IN"], gaz)
    assert (l.level, l.lat) == ("city", 28.65)


def test_same_country_mixed_levels_become_country():
    gaz = Gazetteer.from_entries([P("Palestine", "country", 32.0, 35.3, "PS", 5_000_000),
                                  P("Gaza", "country", 32.0, 35.3, "PS", 5_000_000),
                                  P("Gaza", "city", 31.5, 34.47, "PS", 410_000)])
    l = locate_event(["Israeli strikes on Gaza"], ["QA"], gaz)
    assert (l.level, l.country) == ("country", "PS")


def test_city_and_its_eponymous_region_give_city():
    gaz = Gazetteer.from_entries([P("Hungary", "country", 47.1, 19.4, "HU", 9_600_000),
                                  P("Budapest", "city", 47.5, 19.04, "HU", 1_700_000),
                                  P("Budapest", "region", 47.49, 19.06, "HU", 0)])
    l = locate_event(["Leaders meet in Budapest"], ["US"], gaz)
    assert (l.level, l.name) == ("city", "Budapest")


def test_possessive_gazetteer_names_do_not_match_surnames():
    gaz = Gazetteer.from_entries([P("Smith's", "region", 32.3, -64.7, "BM", 0)])
    assert locate_event(["Smith wins the vote"], ["US"], gaz) is None


def test_uncorroborated_small_place_abroad_is_ignored():
    gaz = Gazetteer.from_entries([P("Kennedy", "city", 4.7, -74.1, "CO", 300_000)])
    assert locate_event(["Kennedy speaks at rally"], ["US", "US", "GB"], gaz) is None


def test_small_place_corroborated_by_two_titles_or_sources():
    gaz = Gazetteer.from_entries([P("Kherson", "city", 46.6, 32.6, "UA", 280_000)])
    assert locate_event(["Shelling in Kherson", "Kherson residents flee"], ["GB", "US"], gaz).name == "Kherson"
    assert locate_event(["Shelling in Kherson"], ["UA", "UA", "GB"], gaz).name == "Kherson"


def test_named_country_beats_place_in_another_country():
    gaz = Gazetteer.from_entries([P("Bolivar", "region", -1.6, -79.0, "EC", 0),
                                  P("Venezuela", "country", 7.0, -66.0, "VE", 28_000_000)])
    l = locate_event(["Bolivar falls as Venezuela crisis deepens"], ["GB"], gaz)
    assert (l.level, l.country) == ("country", "VE")


@pytest.mark.parametrize("title", [
    "Smith wins the vote", "Army retook key City from rebels", "Kennedy speaks", "Bush library opens",
    "Meta shares fall", "George announces tour", "Hassan meets envoy", "Gulf states meet",
    "Mountain rescue under way", "Nelson leads poll", "Tyler signs deal", "Santos coach sacked",
])
def test_real_gazetteer_ignores_names_and_words(title):
    gaz = Gazetteer.load(ROOT / "data" / "gazetteer.json.gz", ROOT / "config" / "place_stoplist.txt")
    assert locate_event([title], ["US", "GB"], gaz) is None


def test_ambiguous_name_with_single_salient_candidate_resolves():
    gaz = Gazetteer.from_entries([P("Florida", "region", 28.1, -81.6, "US", 0),
                                  P("Florida", "city", -34.1, -56.2, "UY", 120_000)])
    l = locate_event(["Hurricane Makes Landfall In Florida"], ["US", "CA", "GB"], gaz)
    assert (l.level, l.name, l.country) == ("region", "Florida", "US")
