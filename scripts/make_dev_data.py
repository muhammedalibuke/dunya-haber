"""Write sample site data to site/dev-data/ for local previews (fictional examples).

Usage: python scripts/make_dev_data.py [IMG_BASE]   then open  /site/?data=dev-data
IMG_BASE is where the sample photos are served (photos must be absolute http URLs),
default http://localhost:8000/site/dev-data/
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.models import Article, Event, Location, State  # noqa: E402
from pipeline.publish import build_site_data, write_site_data  # noqa: E402
from pipeline.state import cache_key  # noqa: E402

NOW = datetime.now(timezone.utc).replace(microsecond=0)

EVENTS = [
    # id, title_tr, title_en, hours_ago, location, sources [(name, cc)], image, summary
    ("e1", "Japonya'nın Kobe kentinde 6,8 büyüklüğünde deprem", "6.8-magnitude earthquake hits Kobe, Japan", 1.5,
     Location("city", "Kobe", 34.69, 135.19, "JP"),
     [("NHK", "JP"), ("BBC", "GB"), ("AA", "TR"), ("DW", "DE"), ("Yonhap", "KR"), ("ABC", "AU")], True,
     ("Batı Japonya'da sabah saatlerinde 6,8 büyüklüğünde güçlü bir deprem meydana geldi. Tren seferleri geçici "
      "olarak durduruldu. Tsunami uyarısı bir saat sonra kaldırıldı. Yetkililer en az üç kişinin hayatını "
      "kaybettiğini, onlarca kişinin yaralandığını açıkladı. Kobe'deki bazı eski binalarda hasar bildirildi.",
      "A strong 6.8-magnitude earthquake struck western Japan in the morning. Train services were briefly "
      "suspended. A tsunami warning was lifted an hour later. Officials said at least three people died and "
      "dozens were injured. Damage was reported to several older buildings in Kobe.")),
    ("e2", "AB ülkeleri ortak enerji paketinde anlaştı", "EU states agree on joint energy package", 3,
     Location("city", "Brussels", 50.85, 4.35, "BE"),
     [("Brussels Times", "BE"), ("Le Monde", "FR"), ("tagesschau", "DE"), ("ANSA", "IT")], False,
     ("Üye ülkeler kış öncesi ortak gaz alımını genişletmeye karar verdi.",
      "Member states decided to expand joint gas purchasing ahead of winter.")),
    ("e3", "Florida'da kasırga karaya ulaştı", "Hurricane makes landfall in Florida", 5,
     Location("region", "Florida", 28.15, -81.62, "US"),
     [("NPR", "US"), ("CBC", "CA"), ("BBC", "GB")], True,
     ("Kasırga gece saatlerinde eyaletin batı kıyısına ulaştı; yüz binlerce ev elektriksiz kaldı.",
      "The hurricane reached the state's west coast overnight, leaving hundreds of thousands of homes without power.")),
    ("e4", "Sudan'da ateşkes görüşmeleri yeniden başladı", "Sudan ceasefire talks resume", 6,
     Location("country", "Sudan", 15.5, 30.2, "SD"),
     [("Sudan Tribune", "SD"), ("Al Jazeera", "QA"), ("Africanews", "CG")], False,
     ("Taraflar insani yardım koridorlarını görüşmek üzere yeniden masaya oturdu.",
      "The parties returned to the table to discuss humanitarian corridors.")),
    ("e5", "Brezilya'da iklim zirvesi sona erdi", "Climate summit ends in Brazil", 8,
     Location("city", "Belém", -1.46, -48.5, "BR"),
     [("Agência Brasil", "BR"), ("The Guardian", "GB"), ("El País", "ES")], True,
     ("Zirve, ormansızlaşmayı azaltmaya yönelik yeni bir fon kararıyla kapandı.",
      "The summit closed with a new fund aimed at reducing deforestation.")),
    ("e6", "Merkez bankası faiz kararını açıkladı", "Central bank announces rate decision", 9,
     None, [("AA", "TR"), ("NTV", "TR")], False,
     ("Karar piyasa beklentileriyle uyumlu oldu.", "The decision was in line with market expectations.")),
    ("e7", "Yeni Zelanda'da seçim sonuçları kesinleşti", "New Zealand election results confirmed", 11,
     Location("country", "New Zealand", -41.8, 172.8, "NZ"),
     [("RNZ", "NZ"), ("ABC", "AU")], False,
     ("Seçim komisyonu kesin sonuçları açıkladı.", "The electoral commission published the final results.")),
]


# a story running for days, for the "günlerdir gündemde" box:
# (source, cc, hours ago, title_tr, title_en, detail_tr, detail_en)
FEATURED = [
    ("Le Temps", "CH", 52, "Cenevre'de ateşkes görüşmeleri başladı", "Ceasefire talks open in Geneva", "", ""),
    ("AFP", "FR", 0.3, "Taraflar esir takasında uzlaştı", "Sides agree on prisoner swap",
     "Her iki taraf da onar esiri cuma günü serbest bırakacak. Takası Kızılhaç yürütecek.",
     "Each side will free ten prisoners on Friday. The Red Cross will oversee the swap."),
    ("BBC", "GB", 1.2, "Ateşkesin ilk gününde çatışma bildirilmedi", "No clashes reported on first day of truce",
     "Gözlemciler cephe hattında sakin bir gün geçtiğini söyledi.", "Monitors said the front line was quiet all day."),
    ("Reuters", "GB", 2.5, "Ateşkes anlaşması Cenevre'de imzalandı", "Ceasefire deal signed in Geneva",
     "Anlaşma pazartesi yürürlüğe girecek. Ayrıntılar bu hafta açıklanacak.",
     "The deal takes effect on Monday. Details will be published this week."),
] + [(n, cc, 20 + i * 3, "Cenevre görüşmeleri sürüyor", "Geneva talks continue", "", "")
     for i, (n, cc) in enumerate([("DW", "DE"), ("ANSA", "IT"), ("NHK", "JP"), ("AA", "TR"), ("Al Jazeera", "QA"),
                                  ("EFE", "ES"), ("Yonhap", "KR"), ("ABC", "AU")])]


def add_featured(state: State, base: str) -> None:
    ids = []
    for i, (name, cc, hours, ttr, ten, dtr, den) in enumerate(FEATURED):
        aid = f"f{i}"
        state.articles[aid] = Article(
            id=aid, url=f"https://example.com/f/{i}", title=ten, description=den,
            source_id=name.lower().replace(" ", "-"), source_name=name, country=cc, lang="en",
            published=NOW - timedelta(hours=hours), image_url=f"{base}sample2.svg" if i < 2 else None, tags=[],
            title_tr=ttr, title_en=ten,
            source_tier=1 if name in ("AFP", "BBC", "Reuters") else 3)
        if den:
            state.translations[cache_key(den, "en", "tr")] = {"text": dtr}
        ids.append(aid)
    created = min(state.articles[a].published for a in ids)
    updated = max(state.articles[a].published for a in ids)
    state.events["f"] = Event("f", ids, np.zeros(4, np.float32), created, updated,
                              location=Location("city", "Geneva", 46.2, 6.14, "CH"))


def sample_history(base: str) -> dict:
    """A day's 'Tarihte bugün' list (20 November, written for previews)."""
    def it(year, tr, en, img=None, born=None, died=None, ctx=None, loc=None):
        return {"year": year, "text": {"tr": tr, "en": en}, "title": None, "born": born, "died": died,
                "extract": {"tr": ctx[0], "en": ctx[1]} if ctx else None,
                "location": dict(zip(("level", "name", "lat", "lon", "country"), loc)) if loc else None,
                "url": "https://en.wikipedia.org/wiki/November_20", "thumb": f"{base}{img}" if img else None,
                "image": f"{base}{img}" if img else None}
    holidays = [{"text": {"tr": "Dünya Çocuk Günü", "en": "World Children's Day"},
                 "url": "https://en.wikipedia.org/wiki/Universal_Children%27s_Day"},
                {"text": {"tr": "Devrim Günü (Meksika)", "en": "Revolution Day (Mexico)"}, "url": None}]
    return {"date": NOW.date().isoformat(), "v": 3, "holidays": holidays, "events": [
        it(1998, "Uluslararası Uzay İstasyonu'nun ilk parçası Zarya modülü fırlatıldı.",
           "Zarya, the first module of the International Space Station, is launched.", "sample3.svg",
           ctx=("Zarya, istasyonun ilk modülüdür. Kazakistan'daki Baykonur Uzay Üssü'nden bir Proton roketiyle fırlatıldı.",
                "Zarya was the station's first module. It was launched on a Proton rocket from Baikonur in Kazakhstan."),
           loc=("city", "Baikonur", 45.6, 63.3, "KZ")),
        it(1989, "BM Genel Kurulu, Çocuk Haklarına Dair Sözleşme'yi kabul etti.",
           "The UN General Assembly adopts the Convention on the Rights of the Child.",
           loc=("city", "New York", 40.7, -74.0, "US")),
        it(1985, "Microsoft, Windows'un ilk sürümünü piyasaya sürdü.", "Microsoft releases the first version of Windows.",
           "sample1.svg"),
        it(1945, "Nürnberg duruşmaları başladı.", "The Nuremberg trials begin.", "sample0.svg",
           ctx=("Duruşmalarda Nazi Almanyası'nın önde gelen isimleri savaş suçlarından yargılandı.",
                "Leading figures of Nazi Germany were tried for war crimes."),
           loc=("city", "Nuremberg", 49.45, 11.08, "DE")),
        it(1910, "Meksika Devrimi başladı.", "The Mexican Revolution begins.", "sample2.svg",
           loc=("country", "Mexico", 23.6, -102.5, "MX")),
    ], "births": [it(1889, "Edwin Hubble, Amerikalı gökbilimci", "Edwin Hubble, American astronomer", "sample0.svg", died="1953")],
       "deaths": [it(1910, "Lev Tolstoy, Rus yazar", "Leo Tolstoy, Russian writer", "sample2.svg", born="1828"),
                  it(2024, "Andy Paley, Amerikalı söz yazarı", "Andy Paley, American songwriter", "sample1.svg", born="1952")]}


def main() -> None:
    state = State()
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/site/dev-data/"
    for eid, ttr, ten, hours, loc, srcs, has_img, (str_, sen) in EVENTS:
        t = NOW - timedelta(hours=hours)
        ids = []
        for i, (name, cc) in enumerate(srcs):
            aid = f"{eid}a{i}"
            state.articles[aid] = Article(
                id=aid, url=f"https://example.com/{eid}/{i}", title=ten if i else ttr, description="",
                source_id=name.lower().replace(" ", "-"), source_name=name, country=cc,
                lang="en" if i else "tr", published=t - timedelta(minutes=10 * (len(srcs) - i)),
                image_url=f"{base}sample{i % 4}.svg" if has_img and i < 4 else None, tags=[],
                title_tr=ttr, title_en=ten)
            ids.append(aid)
        state.events[eid] = Event(eid, ids, np.zeros(4, np.float32), t - timedelta(hours=1), t,
                                  location=loc, summary_tr=str_, summary_en=sen)
    out = ROOT / "site" / "dev-data"
    add_featured(state, base)
    state.history = sample_history(base)
    write_site_data(out, build_site_data(state, [e[0] for e in EVENTS], NOW, featured_id="f"))
    for i, (sky, land) in enumerate([("#9fb3c8", "#5d7690"), ("#c8b59f", "#90745d"),
                                     ("#a9c8a0", "#5d8a5a"), ("#b9a9c8", "#6f5d90")]):
        (out / f"sample{i}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450">'
            f'<rect width="800" height="450" fill="{sky}"/><circle cx="{200 + 120 * i}" cy="160" r="70" fill="#eef2f5"/>'
            f'<path d="M0 330 L220 210 L380 300 L560 190 L800 320 L800 450 L0 450Z" fill="{land}"/></svg>',
            encoding="utf-8")
    empty = ROOT / "site" / "dev-data-empty"
    write_site_data(empty, build_site_data(State(), [], NOW))
    print(f"wrote {out} and {empty}")


if __name__ == "__main__":
    main()
