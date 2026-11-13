"""Build data/gazetteer.json.gz from GeoNames (geonamescache) and Natural Earth.

Sources and licenses:
- GeoNames via geonamescache: cities with population >= 100 000 (CC-BY 4.0)
- Natural Earth admin-0 (countries) and admin-1 (states/provinces): public domain

Usage: python scripts/build_gazetteer.py [--ne-dir DIR]
"""
from __future__ import annotations

import argparse
import gzip
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
ADMIN0 = "ne_50m_admin_0_countries"
ADMIN1 = "ne_10m_admin_1_states_provinces"
CITY_MIN_POP = 100_000
ALT_NAME_MIN_POP = 1_000_000
GENERIC = {
    "central", "north", "south", "east", "west", "northern", "southern", "eastern", "western",
    "capital", "coast", "coastal", "islands", "island", "lakes", "upper", "lower", "greater",
    "north-east", "north-west", "south-east", "south-west", "northeast", "northwest",
    "southeast", "southwest", "centre", "center", "littoral", "plateau", "highlands", "lake",
}
# Regions of these countries are kept even when another country has a city/country of the
# same name (e.g. the US state of Georgia); elsewhere such regions are dropped as ambiguous.
KEEP_REGION_COLLISIONS = {"US"}
COUNTRY_ALIASES = {
    "US": ["US", "U.S", "USA", "U.S.A", "United States", "America", "ABD"],
    "GB": ["UK", "U.K", "Britain", "Great Britain", "United Kingdom", "England", "Scotland", "Wales",
           "İngiltere", "Birleşik Krallık"],
    "AE": ["UAE", "Emirates", "BAE"],
    "KR": ["South Korea", "Güney Kore"],
    "KP": ["North Korea", "Kuzey Kore"],
    "CD": ["DR Congo", "DRC", "Democratic Republic of Congo"],
    "CG": ["Congo-Brazzaville"],
    "RU": ["Russia", "Rusya"],
    "CZ": ["Czech Republic", "Czechia"],
    "CI": ["Ivory Coast", "Côte d'Ivoire"],
    "PS": ["Gaza", "West Bank", "Palestine", "Filistin"],
    "TR": ["Turkey", "Türkiye", "Turkiye"],
    "NL": ["Holland", "Netherlands"],
    "VA": ["Vatican"],
    "MM": ["Burma"],
    "SZ": ["Swaziland", "Eswatini"],
    "TW": ["Taiwan", "Tayvan"],
    "CN": ["China", "Çin"],
}


def load_geojson(name: str, ne_dir: Path | None) -> list[dict]:
    if ne_dir and (ne_dir / f"{name}.geojson").exists():
        data = (ne_dir / f"{name}.geojson").read_bytes()
    else:
        with urllib.request.urlopen(NE_URL.format(name), timeout=120) as r:
            data = r.read()
    return [f["properties"] for f in json.loads(data)["features"]]


def iso2(p: dict) -> str | None:
    for k in ("ISO_A2", "ISO_A2_EH", "iso_a2"):
        v = p.get(k)
        if v and v != "-99" and len(v) == 2:
            return v.upper()
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ne-dir", type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    import geonamescache

    places: set[tuple] = set()
    country_names: dict[str, str] = {}
    country_centroid: dict[str, tuple[float, float, int]] = {}

    for p in load_geojson(ADMIN0, args.ne_dir):
        cc = iso2(p)
        if not cc:
            continue
        lat, lon, pop = float(p["LABEL_Y"]), float(p["LABEL_X"]), int(p.get("POP_EST") or 0)
        country_centroid[cc] = (lat, lon, pop)
        country_names[cc] = p.get("NAME_EN") or p["NAME"]
        names = {p.get(k) for k in ("NAME", "NAME_EN", "NAME_LONG", "ADMIN", "NAME_TR")} | set(COUNTRY_ALIASES.get(cc, []))
        for n in names:
            if n:
                places.add((n, "country", round(lat, 4), round(lon, 4), cc, pop))

    admin1_by_name: dict[str, set[str]] = defaultdict(set)
    admin1 = load_geojson(ADMIN1, args.ne_dir)
    for p in admin1:
        cc = iso2(p)
        for n in {p.get("name"), p.get("name_en")}:
            if cc and n:
                admin1_by_name[n.lower()].add(cc)
    for p in admin1:
        cc = iso2(p)
        if not cc or p.get("latitude") is None:
            continue
        for n in {p.get("name"), p.get("name_en")}:
            if not n or len(n) < 4 or n.lower() in GENERIC or any(w in GENERIC for w in n.lower().split()):
                continue
            if len(admin1_by_name[n.lower()]) >= 3:  # too generic across countries
                continue
            places.add((n, "region", round(float(p["latitude"]), 4), round(float(p["longitude"]), 4), cc, 0))

    cities = [c for c in geonamescache.GeonamesCache().get_cities().values() if int(c["population"]) >= CITY_MIN_POP]
    big_names: dict[str, set[str]] = defaultdict(set)  # name -> countries having it as city/country
    for n, lv, _lat, _lon, cc, _pop in places:
        if lv != "region":
            big_names[n.lower()].add(cc)
    for c in cities:
        big_names[c["name"].lower()].add(c["countrycode"])
    regions = [r for r in places if r[1] == "region"]
    for r in regions:
        other = big_names.get(r[0].lower(), set()) - {r[4]}
        if other and r[4] not in KEEP_REGION_COLLISIONS:
            places.discard(r)

    for c in geonamescache.GeonamesCache().get_cities().values():
        pop = int(c["population"])
        if pop < CITY_MIN_POP:
            continue
        lat, lon, cc = round(float(c["latitude"]), 4), round(float(c["longitude"]), 4), c["countrycode"]
        places.add((c["name"], "city", lat, lon, cc, pop))
        if pop >= ALT_NAME_MIN_POP:
            for alt in c.get("alternatenames") or []:
                if alt.isascii() and len(alt) >= 4 and alt[0].isupper() and not any(ch in alt for ch in "'`\""):
                    places.add((alt, "city", lat, lon, cc, pop))

    out = sorted(places)
    payload = {"places": out, "country_names": country_names}
    dest = root / "data" / "gazetteer.json.gz"
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out)} places, {len(country_names)} countries -> {dest} ({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
