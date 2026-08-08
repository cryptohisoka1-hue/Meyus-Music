# Burç Yorumu Telegram Botu

## 1. Bot oluşturma
1. Telegram'da **@BotFather**'a git.
2. `/newbot` yaz, ismini ve kullanıcı adını belirle.
3. Sana verilen **token**'ı kopyala (örn: `123456789:AAExxxxxxxxxxxx`).
4. Botu, mesaj atmasını istediğin **gruba ekle** ve grup içinde **admin** yap.

## 2. Grup Chat ID'sini bulma
1. Botu gruba ekledikten sonra grupta herhangi bir mesaj yaz (örn: `/start`).
2. Tarayıcıda şu adresi aç (TOKEN yerine kendi token'ını yaz):
   `https://api.telegram.org/botTOKEN/getUpdates`
3. Dönen JSON içinde `"chat":{"id": -100xxxxxxxxxx, ...}` kısmındaki
   sayıyı (eksi işaretiyle birlikte) not al — bu senin `CHAT_ID`'n.

## 3. Kurulum
```bash
pip install -r requirements.txt
```

## 4. Çalıştırma
```bash
export BOT_TOKEN="123456789:AAExxxxxxxxxxxx"
export CHAT_ID="-1001234567890"
python burc_bot.py
```

Bot çalışırken:
- Her gün rastgele **4–7 kez**, rastgele saatlerde (09:00–23:00 arası)
  otomatik olarak gruba mesaj atar.
- %70 ihtimalle **tek bir burcun** yorumunu, %30 ihtimalle **tüm burçları**
  paylaşır (bu oran `SINGLE_SIGN_PROBABILITY` değişkeninden ayarlanabilir).
- Grup üyeleri `/burc Aslan` yazarak istedikleri burcun yorumunu,
  `/burclar` yazarak da tüm burçların yorumunu anlık olarak alabilir.

## 5. Ayarları değiştirme
`burc_bot.py` dosyasının en üstündeki **AYARLAR** bölümünden:
- `MIN_POSTS_PER_DAY` / `MAX_POSTS_PER_DAY`: günlük mesaj sayısı aralığı
- `ACTIVE_HOUR_START` / `ACTIVE_HOUR_END`: mesajların atılabileceği saat aralığı
- `SINGLE_SIGN_PROBABILITY`: tek burç mu / tüm burçlar mı olasılığı

## 6. Sürekli çalışır durumda tutma (opsiyonel)
Bilgisayarını kapattığında bot da durur. Sürekli açık kalması için:
- Ücretsiz bir sunucuda (örn. Oracle Cloud, Railway, Render) çalıştırabilir,
- ya da `systemd`, `pm2`, `screen`/`tmux` gibi araçlarla arka planda
  sürekli çalışır hale getirebilirsin.

## 7. İçerik hakkında not
Yorumlar; aşk, kariyer ve sağlık temalı cümlelerin rastgele kombinasyonlarıyla
yerel olarak üretiliyor (dış bir astroloji API'sine bağımlı değil), bu yüzden
internet kesintisi ya da API limiti gibi sorunlar yaşamazsın. İstersen daha
sonra gerçek bir astroloji API'sine bağlayacak şekilde de genişletilebilir.
