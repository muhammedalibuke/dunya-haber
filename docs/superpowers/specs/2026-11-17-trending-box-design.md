# "Günlerdir gündemde" kutusu — kısa tasarım

Onaylandı: 17 Kasım 2026 ("uygun").

## Amaç
Günlerdir konuşulan, hâlâ gelişen haberi ana ekranın en üstünde bir kutuda göstermek: ne zamandır gündemde
olduğu, son güncelleme tarihi ve son gelişmelerin kısa ayrıntısıyla. Okur, haberin ilk gün başlığını değil,
bugün ne olduğunu görmeli.

## Kararlar (kullanıcıyla)
- Seçim: genel konu (spor/magazin değil), ilk haberi en az 24 saat önce, son haberi en fazla 6 saat önce,
  en az 10 kaynak. Uyanlardan son 24 saatte en çok farklı kaynağın yazdığı. Yoksa kutu yok.
- Yer: başlığın altında, haritanın üstünde. Bu haber aşağıdaki listede tekrar çıkmaz.
- Kutu: "N gündür gündemde · K kaynak", küçük foto, başlık, "Son güncelleme: 17 Kasım Salı, 19:12".
- Son gelişmeler: farklı kaynaklardan en yeni 3 haber; saat, başlık, kaynak, o haberin açıklamasından
  1–2 cümle; orijinal habere bağlantı. Kutunun sonunda "Haberin tamamı" bağlantısı.
- Bozuk çeviriler ("mainstremainstre…") gösterilmez; yerine orijinal metin.

## Yaklaşımlar
1. **Seçilen:** Pipeline seçer ve today.json'a `featured` alanı yazar; site yalnızca gösterir. Çeviriler
   (gelişme ayrıntıları) pipeline'da, mevcut çeviri önbelleğiyle yapılır.
2. Sitede seçmek: tüm haber dosyalarını indirmek gerekir, çeviri yapılamaz. Reddedildi.

## Benim kararlarım
- "Gün sayısı" = ilk haberden bugüne takvim günü (İstanbul saatine göre değil, UTC); en az 2.
- Benzer başlıklı gelişmeler (kelime örtüşmesi ≥ %50) tekrarlanmaz.
- Ayrıntı metni: haberin varsayılan özetinin (çevrilmiş) ilk 2 cümlesi, en fazla 240 karakter.
