# Dünya Haber

Dünyada bugün olan önemli olayları tek, sade bir sayfada gösteren kişisel haber uygulaması.

- Aynı olayı yazan haberler (farklı dillerde bile) **tek bir olayda** birleşir.
- Ana ekranda günün en önemli **5–10 olayı** ve bir **dünya haritası** var. Liste bitirilebilir.
- Her olayda kaynakların listesi ve **orijinal habere doğrudan bağlantı** bulunur.
- Türkçe ve İngilizce. Spor ve magazin günün özetine girmez, "Tümünü gör" listesinde görünür.
- **Ücretsiz:** GitHub Actions 30 dakikada bir haberleri toplar, site GitHub Pages'te yayınlanır.

Adres: `https://muhammedalibuke.github.io/dunya-haber/`

## İlk kurulum (bir kez)

1. **Settings → Pages → Build and deployment → Source: GitHub Actions** seç.
2. **Actions → check-sources → Run workflow** ile kaynakların sağlığını kontrol et (rapor, çalışmanın "Artifacts" kısmında).
3. **Actions → update → Run workflow** ile ilk çalıştırmayı başlat. Sonrasında her 30 dakikada bir kendiliğinden çalışır.

İlk çalıştırma çeviri ve vektör modellerini indirdiği için uzun sürer (15–25 dk). Sonrakiler önbellekten çalışır.

## Nasıl çalışır

```
config/sources.yaml  →  topla (RSS)  →  vektörle  →  olaylara kümele
→ spor/magazin etiketi  →  çeviri (TR/EN, çevrimdışı)  →  konum (GeoNames + Natural Earth)
→ sıralama (ülke dengeli)  →  site/data/*.json  →  GitHub Pages
```

Durum (olaylar, çeviri önbelleği) `data` dalında JSON olarak saklanır. Bu dal her çalışmada tek bir commit olarak üzerine yazılır.

## Sık yapılacaklar

- **Kaynak eklemek:** `config/sources.yaml` dosyasına bir satır ekle (`id, name, url, country, lang, region`). `pytest tests/test_sources.py` alanları kontrol eder.
- **Yanlış eşleşen yer adı:** `config/place_stoplist.txt` dosyasına ekle.
- **Benzer haberlerin birleşme hassasiyeti:** `pipeline/cluster.py` içindeki `CLUSTER_THRESHOLD`. Yükseltirsen daha az birleşir, düşürürsen daha çok.
- **Yerelde önizleme:** `python scripts/make_dev_data.py`, sonra `python -m http.server` ve `http://localhost:8000/site/?data=dev-data`.
- **Testler:** `pytest` ve `npm test`.

## İsteğe bağlı: yapay zekâ özeti

Varsayılan olarak kapalı. Açmak için Google AI Studio'dan ücretsiz bir Gemini API anahtarı al ve depoda
**Settings → Secrets and variables → Actions → New repository secret** ile `GEMINI_API_KEY` adıyla ekle.
Kota dolarsa ya da hata olursa sistem sessizce normal özete döner.

## Telif ve lisanslar

Haber başlıkları ve kısa açıklamalar ilgili yayıncılara aittir. Uygulama haberin tamamını göstermez, kaynağına bağlantı verir.
Yer verisi: [GeoNames](https://www.geonames.org/) (CC-BY 4.0). Harita: [Natural Earth](https://www.naturalearthdata.com/) (kamu malı).
Vektör modeli: `paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0). Çeviri: Argos Translate.
Harita kütüphaneleri: d3-geo, d3-array, topojson-client (ISC).
