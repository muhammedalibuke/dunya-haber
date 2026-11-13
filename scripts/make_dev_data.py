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
    ("e6", "Merkez bankası faiz kararını açıkladı <b>test</b>", "Central bank announces rate decision <b>test</b>", 9,
     None, [("AA", "TR"), ("NTV", "TR")], False,
     ("Karar piyasa beklentileriyle uyumlu oldu.", "The decision was in line with market expectations.")),
    ("e7", "Yeni Zelanda'da seçim sonuçları kesinleşti", "New Zealand election results confirmed", 11,
     Location("country", "New Zealand", -41.8, 172.8, "NZ"),
     [("RNZ", "NZ"), ("ABC", "AU")], False,
     ("Seçim komisyonu kesin sonuçları açıkladı.", "The electoral commission published the final results.")),
]


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
    write_site_data(out, build_site_data(state, [e[0] for e in EVENTS], NOW))
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
