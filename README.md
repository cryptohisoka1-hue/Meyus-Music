# UNO Telegram Botu

## Kurulum

1. `.env.example` dosyasını `.env` olarak kopyala ve BotFather'dan aldığın gerçek token'ı yaz.
2. Railway'e deploy edeceksen: **Variables** kısmına `BOT_TOKEN` adında bir değişken ekle, değeri gerçek token olsun.
3. Bağımlılıklar: `pip install -r requirements.txt`
4. Çalıştır: `python main.py`

## Komutlar

- `/oyun` — Grupta yeni bir UNO lobisi açar. Katılmak isteyenler "Katıl" butonuna basar.
- Lobi sahibi tema seçebilir (🎨 Tema butonu) ve en az 2 kişi katılınca "🚀 Başlat" ile oyunu başlatır.
- `/bitir` — Aktif oyunu/lobiyi sonlandırır (sadece lobiyi açan kişi kullanabilir).
- `/sıralama` — Son 7 günün galibiyet sıralamasını gösterir.
- `/profil` — Kendi istatistiklerini gösterir (oynanan oyun, galibiyet, kazanma oranı).

## Nasıl çalışır

- Her turda bot, sırası gelen oyuncunun elini grup içinde buton olarak gösterir.
- Oynanamayacak kartlar 🔒 ile işaretlenir ve basılsa bile hiçbir şey olmaz.
- Sırası gelen kişiye grup içinde etiketli bildirim gönderilir (`Sıra sende, @isim!`).
- Kart görselleri, seçilen temanın Telegram sticker paketinden otomatik çekilir — paket başına indirme/dosya işi yok, sadece `config.py` içindeki `THEME_PACKS` sözlüğüne sticker paketinin kısa adını (`t.me/addstickers/<isim>` içindeki `<isim>`) eklemen yeterli.

## Not — Basitleştirme

Standart UNO'da eller gizlidir (özel mesajla gösterilir). Bu bot, kurulumu basit tutmak için elleri **grup içinde** gösterir; herkes herkesin elini görebilir ama sadece sırası gelen kişi kart oynayabilir (başkası basarsa uyarı verir, hiçbir şey olmaz). Gerçekten gizli el istersen, oyuncuların bota özelden `/start` yazmış olması şartıyla DM tabanlı bir sürüme geçirebiliriz — istersen bunu birlikte ekleyelim.

## Kart eşleştirmesi hakkında

Her tema paketindeki stickerlar, paket içindeki sırayla 54 benzersiz UNO kart yüzüne (4 renk × 13 değer + 2 joker) otomatik eşlenir. Paket 54'ten az sticker içeriyorsa, kartlar sticker sayısına göre baştan tekrar eşlenir (bazı kartlar aynı görseli paylaşabilir) — bu görsel bir sadeleştirmedir, oyun kurallarını etkilemez.
