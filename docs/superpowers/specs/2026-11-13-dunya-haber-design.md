# Dünya Haber — Tasarım Belgesi

Tarih: 2026-11-13
Durum: Taslak (onay bekliyor)

## 1. Amaç ve neden

Dünyanın her yerinde olan önemli olayları tek, sade bir yerde görmek. Kullanıcı (şimdilik tek kullanıcı: proje sahibi) Bundle'ı kullanıyor ama iki şeyden rahatsız:

1. **Aynı haber tekrar tekrar geliyor.** Aynı olayı 15 site yazınca akışta 15 kez görünüyor.
2. **Tasarım kalabalık.** "Sanki üzerime harfler, cümleler geliyor, sadelik yok." Renkler sorun değil, sorun yoğunluk ve dağınıklık.

Bu uygulama haberleri **olay** etrafında birleştirir ve sakin, bitirilebilir bir ekran sunar. İlgi çeken olayda kullanıcı orijinal habere bir dokunuşla gidip detaylı okur.

**Başarı ölçütü:** Kullanıcı Bundle yerine bunu her gün açıyor. Devam ederse ileride başkalarına açmak düşünülecek (şimdi kapsam dışı).

## 2. Hedefler

- Dünyanın tüm bölgelerinden haber toplamak (her ülkeden en az bir kaynak hedeflenir).
- Aynı olayı anlatan haberleri dil fark etmeksizin **tek bir olay kartında** birleştirmek.
- Olay geliştikçe yeni kart açmamak; mevcut kartı güncelleyip "yeni gelişme" işareti koymak.
- Her şeyi **Türkçe ve İngilizce** sunmak (arayüzde dil değiştirme).
- Her olayda, olayı yazan kaynakları ve **orijinal habere doğrudan bağlantıları** göstermek.
- **Sıfır maliyet.** Ücretli sunucu, ücretli API yok.
- Telefondan açılabilen, ana ekrana eklenebilen bir web uygulaması.
- Olayların yerini haritada göstermek: günün özeti için bir dünya haritası, olay detayında da yakınlaştırılmış küçük bir harita. Olay yeri kırmızı nokta ile işaretlenir, mümkünse eyalet veya şehir düzeyinde.

## 3. Hedef dışı (şimdilik yapılmayacaklar)

- Üyelik, giriş, kullanıcı hesabı.
- Bildirimler.
- Kişiselleştirme, kategori filtreleri.
- Harita servisleri (Google Maps, ücretli harita karoları vb.). Harita kendi çizdiğimiz sınır verisiyle oluşturulur.
- Mağazadan indirilen yerel mobil uygulama.
- Başkalarına yayınlama (KVKK, alan adı, telif açısından görsel lisansı vb.). Bu iş, kişisel kullanım tuttuğunda ayrı bir proje olarak ele alınacak.

## 4. Anti-hedefler (çalışsa bile başarısızlık sayılacak durumlar)

- Ekranda aynı olayın birden fazla kez görünmesi.
- Kalabalık ekran: bir listede başlıkla birlikte uzun metin bloklarının, çok sayıda etiketin ya da görsellerin yığılması.
- Sonsuz kaydırma hissi. Ana ekranın bir sonu olmalı.
- Reklam, tık tuzağı, ara sayfalar. Bağlantı doğrudan kaynağa gider.

## 5. Kısıtlar

- **Maliyet sıfır.** Çalışma ortamı GitHub Actions'tır (açık depoda ücretsiz ve dakika sınırı yok). Site GitHub Pages'tedir.
- **Depo açık (public).** Kod ve toplanan veri herkese görünür. Gizli anahtarlar (varsa Gemini API anahtarı) GitHub Secrets'ta tutulur.
- **Lisans.** Kullanılan modeller ve kütüphaneler ileride ticari kullanıma da izin vermelidir. Örneğin NLLB gibi ticari kullanımı yasak (CC-BY-NC) modeller kullanılmaz.
- **İçerik.** Haberin tamamı kopyalanmaz. Sadece başlık, kaynağın RSS'te verdiği kısa açıklama veya bizim özetimiz, kaynak adı ve bağlantı gösterilir.
- **GitHub sınırları.** Zamanlanmış görevler yoğunlukta birkaç dakika gecikebilir. Açık depolarda 60 gün boyunca depo etkinliği olmazsa zamanlanmış görevler kapanır. Her çalışmada veri dalına yapılan yazma bunu önlemelidir. Önlemiyorsa basit bir "canlı tutma" adımı eklenir.

## 6. Değerlendirilen yaklaşımlar

| Yaklaşım | Artısı | Eksisi |
|---|---|---|
| **A. GitHub Actions + GitHub Pages (seçilen)** | Tamamen ücretsiz; sunucu yönetimi yok; telefondan her yerden erişim | Depo açık olmalı; işlem 30 dakikada bir toplu çalışır (anlık değil); işlem gücü sınırlı |
| B. Ücretli küçük sunucu + yapay zekâ API'si | En iyi özet kalitesi, gerçek zamanlıya yakın | Ayda yaklaşık 15–40 $; kullanıcı şimdilik ödeme yapmak istemiyor |
| C. Oracle Cloud ücretsiz sunucu | Gerçek, her zaman açık sunucu | Kredi kartı ister, ücretsiz kotası bu yıl yarıya indi, yine değişebilir |
| D. Kendi bilgisayarında çalıştırma | Sıfır maliyet | Bilgisayar kapalıyken haber toplanmaz, dışarıdan erişilemez |

**Kullanıcının seçimi: A.** Kişisel kullanım için sıfır maliyetle her gün telefondan kullanılabilen tek seçenek bu. İleride yayın kararı verilirse veri işleme kodu aynı kalır, B'ye taşınır.

## 7. Kullanıcının verdiği kararlar

- **Ana ekran "Günün özeti":** O günün en önemli 5–10 olayı, numaralı ve tek satır başlık halinde. Altında ülke ve kaynak sayısı. Sonda "Bugünlük bu kadar · Tümünü gör" yazar.
- **"Tümünü gör" sakin liste:** Bütün olaylar alt alta. Sadece küçük meta satırı (ülke · zaman), başlık ve kaynak sayısı. Bol boşluk, ince ayraçlar, görsel yok.
- **Kartlı tasarım (iki satır özetli kartlar) kesinlikle yok.** Kullanıcı bunu açıkça reddetti.
- **Olay detayı:** En üstte tek bir büyük fotoğraf. Altında başlık, ülke ve zaman, birkaç kaynaktan derlenmiş 5–6 cümlelik özet. En altta kaynak listesi: en çok okunan en fazla 5 kaynak (popülerlik sırası `sources.yaml` içindeki `tier` alanıyla, 1–3), her biri için kaynak adı, o kaynağın kendi başlığı ve orijinal habere giden bağlantı (↗). Altında "Bu olayı toplam N kaynak haberleştirdi" satırı. (13 Kasım güncellemesi, kullanıcı isteği.)
- **Diğer haberler (14 Kasım):** Olay sayfasının sonunda en fazla 5 başka haber: önce günün özetindekiler, sonra en yeniler; açılmamış olanlar önce. Altında "Tümünü gör".
- **Fotoğraf:** Listelerde yok, sadece detay ekranında. "Bir deneyelim, olmazsa değiştiririz."
- **Diller:** Türkçe ve İngilizce.
- **Kapsam:** Bütün dünya ülkeleri.
- **Kod ve kaynak seçimi** bana (geliştiriciye) bırakıldı.
- **Spor ve magazin:** Günün özetine girmez, "Tümünü gör" listesinde yer alır.
- **Türkiye:** Diğer ülkeler gibi işlenir. Sıralamada ek ağırlık almaz, ayrı bölümü olmaz.
- **Harita (seçenek b):**
  - **"Bugün dünyada" haritası:** Günün özetindeki 5–10 olay dünya haritasında kırmızı noktalarla gösterilir. Noktaya dokununca o olayın detayı açılır.
  - ~~Olay detayında küçük harita~~ (14 Kasım: kullanıcı isteğiyle kaldırıldı; yerine farklı kaynaklardan en fazla 4 fotoğraf: büyük fotoğraf + küçük kareler, dokununca büyüğün yerine geçer).
  - Dünya haritasında noktaların yanında yer adı yazar, olayların ülkeleri hafifçe boyanır; listede "Kobe, Japonya" gibi yer adı görünür.
  - Arka plan ve sınır renkleri bizim seçimimizdir, sade tutulur.

### Ekran taslakları

```
Günün özeti (ana ekran)        Tümünü gör                   Olay detayı
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│ 13 Kasım      TR|EN  │   │ ← Tüm olaylar        │   │ [  büyük fotoğraf  ] │
│ ┌──────────────────┐ │   │──────────────────────│   │ Tokyo'da 6,8 büyük-  │
│ │ ●  dünya    ●    │ │   │ Japonya · 2 sa       │   │ lüğünde deprem       │
│ │   haritası   ●   │ │   │ Tokyo'da deprem      │   │ Japonya · 2 saat önce│
│ └──────────────────┘ │   │ 14 kaynak            │   │ ┌──────────────────┐ │
│ Bugün 7 önemli olay  │   │──────────────────────│   │ │ küçük harita  ●  │ │
│ 1 Tokyo'da deprem    │   │ Avrupa · 4 sa        │   │ └──────────────────┘ │
│   Japonya · 14 kaynak│   │ AB enerji paketi     │   │ Özet 3-4 cümle…      │
│ 2 AB enerji paketi   │   │ 9 kaynak             │   │                      │
│   Avrupa · 9 kaynak  │   │──────────────────────│   │ Kaynaklar            │
│ …                    │   │ …                    │   │  NHK  başlık…     ↗  │
│ Bugünlük bu kadar ·  │   │                      │   │  BBC  başlık…     ↗  │
│ Tümünü gör           │   │                      │   │  AA   başlık…     ↗  │
└──────────────────────┘   └──────────────────────┘   └──────────────────────┘
```

## 8. Sistem tasarımı

### 8.1 Genel akış

```
GitHub Actions (her 30 dakikada bir)
  1. Topla     → RSS beslemelerini çek
  2. Temizle   → aynı URL'yi ve boş kayıtları at, dili tespit et
  3. Kümele    → çok dilli vektörlerle haberleri olaylara ata (mevcut olaylara ekle ya da yeni olay aç)
  4. Çevir     → yeni başlıkları ve açıklamaları TR ve EN'e çevir
  5. Sırala    → olay önem puanını hesapla, günün özetini seç
  5b. Konumla  → olayın yerini bul (şehir / eyalet / ülke) ve koordinatını kaydet
  6. Özetle    → (isteğe bağlı) günün özetindeki olaylar için Gemini ücretsiz katmanıyla özet; hata ya da limit olursa yedek özet
  7. Yayınla   → durumu veri dalına kaydet, site için JSON üret, GitHub Pages'e yükle
```

### 8.2 Bileşenler

- **Kaynak listesi (`sources.yaml`):** Her kaynak için ad, RSS adresi, ülke, dil ve bölge. Hedef: dünyanın her bölgesinden 150–250 besleme, her ülkeden en az bir kaynak. Ülke için uygun RSS bulunamazsa bölgesel kaynaklarla kapatılır ve belgeye not düşülür. Büyük uluslararası kaynaklar (BBC, Reuters, Al Jazeera, DW, AFP, France 24, NHK World, AA vb.) ve ülkelerin önde gelen yerel kaynakları birlikte kullanılır.
- **Toplayıcı:** Python, `feedparser` ile. Kaynak başına zaman aşımı ve hata toleransı vardır: bir besleme bozuksa atlanır, kayıt tutulur, diğerleri etkilenmez. Görsel bilgisi RSS'teki `media:content`, `media:thumbnail` ya da `enclosure` alanlarından alınır.
- **Dil tespiti:** Hafif bir dil tespit kütüphanesi kullanılır. RSS'teki dil bilgisiyle birlikte değerlendirilir.
- **Kümeleme:** Çok dilli bir cümle vektör modeli kullanılır (örneğin `paraphrase-multilingual-MiniLM-L12-v2` ya da `multilingual-e5-small`, CPU'da çalışır, lisansı uygun). Her yeni haber, son 48 saatteki olayların merkez vektörlerine karşı karşılaştırılır. Benzerlik eşiği geçilirse olaya eklenir, geçilmezse yeni olay açılır. Eşik, gerçek veriyle ayarlanır.
- **Olay güncellemesi:** Bir olaya son gösterimden sonra yeni kaynak eklenirse olay "yeni gelişme" olarak işaretlenir. 48 saattir yeni haber gelmeyen olay kapanır. Kapanan olaylar 7 gün sonra silinir.
- **Çeviri:** Çevrimdışı, açık kaynaklı ve ticari kullanıma izin veren bir çeviri motoru kullanılır (öncelik Argos Translate, gerekirse Opus-MT modelleri). Kaynak dil → İngilizce → Türkçe şeklinde çevrilir. Sadece yeni gelen başlıklar ve kısa açıklamalar çevrilir, sonuçlar saklanır, aynı metin iki kez çevrilmez.
- **Önem puanı:** Farklı kaynak sayısı, kaynakların ülke çeşitliliği ve tazelik birlikte kullanılır. Günün özeti, son 24 saatteki en yüksek puanlı 5–10 olaydan oluşur. Sayı, puan dağılımına göre belirlenir: önemli olay azsa 5, çoksa 10.
  - **Ülke dengesi:** Hiçbir ülke, sırf çok kaynağı olduğu için öne çıkmamalıdır. Bunun için tek bir ülkeden gelen kaynakların puana katkısı azalan getiriyle sınırlanır (örneğin logaritmik ya da tavanlı). Olayı farklı ülkelerden kaynakların yazmış olması daha çok puan getirir. Türkiye dahil hiçbir ülkeye ek ağırlık verilmez.
  - **Konu filtresi:** Her olaya bir konu etiketi verilir (en azından "spor", "magazin/eğlence" ve "genel"). Spor ve magazin olayları günün özetine alınmaz, ama "Tümünü gör" listesinde görünür. Etiketleme ücretsiz yöntemlerle yapılır: beslemenin kendi kategori bilgisi, URL'deki bölüm adı (`/sport/`, `/spor/` gibi) ve olay vektörünün konu örnek vektörlerine benzerliği birlikte değerlendirilir.
- **Olay başlığı ve ülkesi:** Olay başlığı, olaydaki en güvenilir ya da en çok kullanılan kaynağın çevrilmiş başlığıdır. Ülke, başlıkta geçen ülke adlarından tespit edilir. Tespit edilemezse kaynakların ülkesinden en sık geçen kullanılır.
- **Konum bulma:** Ücretsiz ve çevrimdışı yapılır. GeoNames verisi kullanılır (CC-BY 4.0, ticari kullanıma izin verir, kaynak belirtilir). Bu veriden ülkeler, birinci düzey idari bölgeler (ABD eyaletleri, Türkiye illeri vb.) ve nüfusu belli bir eşiğin üstündeki şehirler alınır. Olaydaki başlıklarda (özgün dilde ve İngilizce çevirisinde) geçen yer adları bu sözlükle eşleştirilir.
  - **Belirsizlik kuralı:** Bir ad birden fazla yere uyuyorsa (örneğin "Washington", "Georgia") olaydaki diğer ipuçlarıyla (aynı başlıkta geçen ülke, kaynakların ülkesi) ayırt edilir. Ayırt edilemezse daha genel düzeye inilir: şehir yerine eyalet, eyalet yerine ülke. Yanlış yerde nokta göstermek, genel ama doğru göstermekten kötüdür.
  - **Sonuç:** Her olayda `konum = {düzey: şehir|eyalet|ülke|yok, ad, enlem, boylam, ülke_kodu}` tutulur. Konum bulunamazsa olay haritada gösterilmez, listede normal görünür.
- **Harita çizimi:** Harita servisi ya da harita karosu kullanılmaz. Natural Earth sınır verisi (kamu malı) sitede statik dosya olarak durur: ülke sınırları ve birinci düzey idari bölgeler, telefonda hızlı açılması için sadeleştirilmiş ve küçültülmüş halde. Tarayıcıda SVG olarak, hafif bir kütüphaneyle (ör. d3-geo) ya da elle çizilir. Renkler sade tutulur: açık/koyu temaya uyan nötr bir arka plan, soluk sınırlar, olay yerinde kırmızı nokta. Konum ülke düzeyindeyse ülke soluk kırmızıyla boyanır. Detay ekranında harita olay konumuna yakınlaşır. Ana ekrandaki dünya haritasında noktaya dokununca olay açılır. Noktalar üst üste binerse hafifçe aralanır.
- **Fotoğraf:** Olaydaki kaynaklardan RSS'te görsel veren ilk güvenilir kaynağın görseli, kaynak adıyla birlikte gösterilir. Görsel yoksa fotoğraf alanı hiç gösterilmez, yer tutucu kullanılmaz.
- **Özet:** Varsayılan özet, en iyi kaynağın RSS açıklamasının çevirisidir (HTML temizlenir, 3–4 cümleye kısaltılır). İsteğe bağlı olarak, Gemini API anahtarı tanımlıysa günün özetindeki olaylar için birden fazla kaynağın başlık ve açıklamasından TR ve EN özet üretilir. Bu özetler "yapay zekâ özeti" olarak etiketlenir. Kota dolarsa ya da hata olursa sessizce varsayılan özete düşülür.
- **Durum saklama:** Olaylar ve çeviri önbelleği, ayrı bir `data` dalında JSON dosyaları olarak tutulur. Depo geçmişi şişmesin diye bu dal her çalışmada tek bir commit olarak zorla güncellenir.
- **Ön yüz:** Statik site, framework'süz (HTML, CSS ve küçük bir JS). `today.json`, `events.json` ve olay başına `event/<id>.json` dosyalarını okur. Ana ekrana eklenebilmesi için web uygulaması manifesti bulunur. TR/EN tercihi tarayıcıda saklanır. Açık ve koyu tema sistem ayarını takip eder. Tipografi büyük ve sakindir, bol boşluk kullanılır.

### 8.3 Hata durumları

- Besleme çökerse ya da zaman aşımı olursa o kaynak atlanır. Üst üste çok kez çöken kaynaklar raporda listelenir.
- Çalışma tamamen başarısız olursa site bir önceki veriyle kalır, boş ekran gösterilmez. Sitede "son güncelleme: …" bilgisi yer alır.
- Gemini hatası olursa varsayılan özete düşülür.

## 9. Geliştiriciye bırakılanlar

- Kesin kaynak listesi ve hangi ülkelerin hangi kaynakla kapsanacağı.
- Vektör modeli ve çeviri modelinin kesin seçimi (lisans kısıtına uyarak).
- Kümeleme eşiği ve önem puanı formülünün ayarı.
- Dosya ve klasör yapısı, test yaklaşımı.
- Görsel tasarımın ince ayarı (yazı tipi, boşluklar), yukarıdaki sadelik ilkelerine bağlı kalarak.

## 10. Geliştiricinin verdiği kararlar (kullanıcı kontrol etsin)

- Gemini ile yapay zekâ özeti başlangıçta **kapalıdır**. Sistem sadece ücretsiz çeviriyle çalışır. Özetler yetersiz bulunursa API anahtarı eklenerek açılır.
- Güncelleme sıklığı **30 dakikadır**.
- Arayüzün varsayılan dili **Türkçedir**, İngilizceye tek dokunuşla geçilir.
- "Bugün", **İstanbul saatine** göre hesaplanır.
- "Yeni gelişme" işareti, kullanıcının hangi olayı en son ne zaman gördüğünü **telefonun tarayıcısında** saklayarak belirlenir. Hesap gerekmez.
- Bir olayda görsel yoksa fotoğraf alanı hiç gösterilmez.
- "Bugün dünyada" haritası ayrı sekmede değil, **ana ekranın en üstünde** durur. Ana ekran açıldığında ilk görünen şey harita ve altında numaralı liste olur.
- Konum, başlıktaki yer adlarından bulunur. Emin olunamayan durumda daha genel düzey (ülke) gösterilir.

## 11. Değerlendirme notları

Belge, uygulamayı yazacak birinin gözüyle okundu. Kullanıcıya iki soru soruldu ve cevapları yukarıya işlendi:

1. Spor ve magazin günün özetine girsin mi? → Hayır, sadece "Tümünü gör" listesinde (bkz. 7 ve 8.2).
2. Türkiye haberleri nasıl yer alsın? → Diğer ülkeler gibi, ek ağırlık olmadan (bkz. 7 ve 8.2).
