import os
import asyncio
import json
import httpx
from telegram.error import BadRequest, RetryAfter, TimedOut, NetworkError

# ─── AYARLAR ───
# Kartların file_id'sini almak için gonderileceği GİZLİ depo sohbeti.
# KANAL kullanman önerilir (gruplara göre flood limiti çok daha yüksek).
# Railway Variables kısmına STORAGE_CHAT_ID adıyla ekle.
#
# Nasıl oluşturulur:
#   1) Telegram'da yeni bir KANAL oluştur (Private/Public fark etmez).
#   2) Botu kanala ekle ve YÖNETİCİ yap.
#   3) Kanal ID'sini öğrenmek için kanala herhangi bir mesaj at,
#      sonra tarayıcıdan https://api.telegram.org/bot<TOKEN>/getUpdates
#      adresine gidip "chat":{"id":-100...} değerini kopyala.
#   4) Railway Variables'a STORAGE_CHAT_ID olarak ekle.
STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
if STORAGE_CHAT_ID:
    STORAGE_CHAT_ID = int(STORAGE_CHAT_ID)

# Kalıcı cache dosyası. Railway'de Volume kullanıyorsan mount path'e
# göre ayarla (örn: /app/data/file_id_cache.json). Volume yoksa repo'ya
# eklenmiş olmalı ki deploy sonrası silinmesin.
# Railway Volume ekleme: Dashboard -> Volumes -> New Volume -> /app/data
CACHE_FILE = os.getenv("CACHE_FILE", "file_id_cache.json")

# Aynı sohbete ardışık gönderimler arasında bekleme süresi (saniye).
# Kanal kullanıyorsan 2.5 güvenli, grup kullanıyorsan 3.0+ önerilir.
_MIN_INTERVAL = 2.5

# Ağ/indirme hatalarında kaç kez tekrar denecek
_MAX_RETRIES = 5

# Bellek içi cache ve senkronizasyon
_file_id_cache = {}
_send_lock = asyncio.Lock()
_last_send_time = 0.0


# ─── KALICI CACHE YÖNETİMİ ───
def _load_cache():
    """JSON dosyasından cache'i belleğe yükle."""
    global _file_id_cache
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            # Sadece string: string mapping kabul et
            _file_id_cache = {k: v for k, v in loaded.items() if isinstance(v, str)}
        print(f"💾 {len(_file_id_cache)} kart kalıcı cache'ten yüklendi ({CACHE_FILE}).")
    except FileNotFoundError:
        _file_id_cache = {}
        print(f"ℹ️ Cache dosyası bulunamadı ({CACHE_FILE}), boş cache ile başlanıyor.")
    except json.JSONDecodeError as e:
        print(f"⚠️ Cache dosyası bozuk ({CACHE_FILE}), sıfırdan başlanıyor: {e}")
        _file_id_cache = {}


def _save_cache():
    """Bellekteki cache'i JSON dosyasına kaydet."""
    try:
        # Dosyanın yazılabilir olduğundan emin olmak için dizin oluştur
        os.makedirs(os.path.dirname(os.path.abspath(CACHE_FILE)) or ".", exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_file_id_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Cache dosyasına yazılamadı ({CACHE_FILE}): {e}")


# Bot başlatılırken cache'i yükle
_load_cache()


# ─── YARDIMCI FONKSİYONLAR ───
async def _throttle():
    """Bir önceki gönderimden bu yana yeterli süre geçmediyse bekler."""
    global _last_send_time
    loop = asyncio.get_event_loop()
    now = loop.time()
    wait = _MIN_INTERVAL - (now - _last_send_time)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_send_time = loop.time()


def get_cached_file_id(card_code):
    """Bellekteki cache'ten file_id döndürür (yoksa None)."""
    return _file_id_cache.get(card_code)


# ─── ANA FONKSİYON ───
async def get_card_file_id(bot, card_code, chat_id):
    """Kart görselini indirip Telegram'a gönderir, file_id döndürür.

    NOT: `chat_id` parametresi geriye dönük uyumluluk için duruyor ama
    KULLANILMIYOR. Görseller her zaman STORAGE_CHAT_ID'ye gönderilir,
    böylece oyunun oynandığı gruba asla kart görseli sızmaz.
    """
    # Önce bellek içi cache'e bak
    if card_code in _file_id_cache:
        return _file_id_cache[card_code]

    if not STORAGE_CHAT_ID:
        raise RuntimeError(
            "STORAGE_CHAT_ID ayarlanmamış! Railway Variables kısmına "
            "STORAGE_CHAT_ID eklenmeli (bkz. card_cache.py başındaki açıklama)."
        )

    from cards_data import card_image_url
    url = card_image_url(card_code)

    # Görseli indir (timeout / ağ hatalarında birkaç kez tekrar dene)
    image_data = None
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=15)) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}: {url}")
                image_data = resp.content
            break
        except Exception as e:
            last_err = e
            print(f"⚠️ Kart görseli indirilemedi ({card_code}), deneme {attempt + 1}/{_MAX_RETRIES}: {e}")
            await asyncio.sleep(1.5 * (attempt + 1))

    if image_data is None:
        raise last_err or Exception(f"Görsel indirilemedi: {card_code}")

    # Telegram'a gizli depo kanalına gönder ve file_id al
    for attempt in range(_MAX_RETRIES):
        try:
            async with _send_lock:
                await _throttle()
                msg = await bot.send_photo(
                    chat_id=STORAGE_CHAT_ID,
                    photo=image_data,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30,
                )
            file_id = msg.photo[-1].file_id
            _file_id_cache[card_code] = file_id
            _save_cache()  # ← Kalıcı diske yaz
            print(f"✅ Cache'e eklendi: {card_code} -> {file_id[:20]}...")
            return file_id

        except RetryAfter as e:
            # Telegram bize tam olarak ne kadar bekleyeceğimizi söylüyor
            wait_s = float(getattr(e, "retry_after", 5)) + 0.5
            print(f"⏳ Flood control ({card_code}): {wait_s:.1f} sn bekleniyor...")
            await asyncio.sleep(wait_s)

        except (TimedOut, NetworkError) as e:
            wait_s = 2.0 * (attempt + 1)
            print(f"⚠️ Gönderim zaman aşımı ({card_code}), {wait_s:.1f} sn sonra tekrar: {e}")
            await asyncio.sleep(wait_s)

        except BadRequest as e:
            err_msg = str(e)
            if "Chat not found" in err_msg:
                print(
                    f"❌ HATA: Depo sohbeti bulunamadı ({STORAGE_CHAT_ID}).\n"
                    f"   Botun bu sohbete eklendiğindeninden ve STORAGE_CHAT_ID'nin\n"
                    f"   doğru olduğundan emin olun. Kanal kullanıyorsanız botu\n"
                    f"   kanala YÖNETİCİ olarak eklemeyi unutmayın."
                )
            raise

        except Exception as e:
            print(f"⚠️ Kart gönderilemedi ({card_code}): {e}")
            raise

    raise Exception(f"Kart gönderilemedi, tüm denemeler tükendi: {card_code}")


# ─── ÖN ISITMA (PREWARM) ───
async def prewarm_all_cards(bot, chat_id, card_codes):
    """Tüm kartları arka planda önbelleğe alır.

    get_card_file_id zaten throttle + retry yaptığı için burada sıralı
    (paralel değil) şekilde çağırmak yeterli ve güvenli.
    """
    missing = [c for c in card_codes if c not in _file_id_cache]
    if not missing:
        print("✅ Tüm kartlar zaten cache'te.")
        return

    print(f"🔥 {len(missing)} eksik kart cache'leniyor...")
    for code in missing:
        try:
            await get_card_file_id(bot, code, chat_id)
        except Exception as e:
            print(f"⚠️ Önbellekleme atlandı ({code}): {e}")

    print(f"🏁 Önbellekleme tamamlandı. Toplam cache: {len(_file_id_cache)} kart.")
            
