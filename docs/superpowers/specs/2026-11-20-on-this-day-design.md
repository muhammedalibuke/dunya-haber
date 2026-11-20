# "Tarihte bugün" sayfası — kısa tasarım

Onaylandı: 20 Kasım 2026 ("ben beğendim, bi temel atalım"). Taslak: ana ekrandan giriş + ayrı sayfa.

## Kararlar (kullanıcıyla)
- Dünya olayları: İngilizce Vikipedi "On this day" listesi; Türkçesi otomatik çeviri (Argos). İki dilde aynı olaylar.
- Ayrı sayfa (`#/tarih`), ana ekranda kutu yok; giriş tarih satırında "Tarihte bugün" bağlantısı.
- Sayfa: tarih başlığı, Olaylar / Doğumlar / Ölümler sekmeleri, ilk olay büyük fotoğraflı, sonra yıl + 1–2 cümle +
  varsa küçük foto, "N yıl önce", Vikipedi bağlantısı, altta kaynak ve lisans notu.

## Yaklaşım
Pipeline günde bir kez (tarih değişince) listeyi çeker, çevirir, `state/history.json.gz`'de saklar ve
`history.json` olarak yayınlar. Çekme ya da çeviri başarısız olursa önceki gün kalır / İngilizce gösterilir.

## Benim kararlarım
- Gün, İstanbul saatine göre (kişisel kullanım; gece yarısı Türkiye'de değişir).
- Olaylar: Vikipedi'nin seçkisi ("selected"), hepsi. Doğumlar ve ölümler: fotoğraflı olanlardan en yeni 20'si
  (Vikipedi bunları seçmiyor; kullanıcı sonra değiştirecek).
- Sıralama: yeniden eskiye.
