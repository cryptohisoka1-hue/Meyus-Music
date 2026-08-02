import os
import asyncio
import httpx
from telegram.error import BadRequest, RetryAfter, TimedOut, NetworkError

# Kartların file_id'sini almak icin gonderilecegi GIZLI depo sohbeti.
# Bu, oyunun oynandigi grup DEGIL; botun kendi ozel bir kanali/grubu olmali.
# Railway -> Variables kismina STORAGE_CHAT_ID adiyla eklenmeli.
#
# Nasil olusturulur:
#   1) Telegram'da yeni bir OZEL grup ya da kanal olustur (sadece sen +
#      isteğe bağlı bot).
#   2) Botu o gruba/kanala ekle ve ADMIN yap.
#   3) O sohbetin chat_id'sini ogrenmek icin: gruba herhangi bir mesaj at,
#      sonra tarayicidan
#      https://api.telegram.org/bot<TOKEN>/getUpdates
#      adresine gidip "chat":{"id": ...} degerine bak. Gruplar icin bu
#      deger genelde eksi (negatif) bir sayidir, orn: -1001234567890
#   4) Bu sayiyi Railway Variables'a STORAGE_CHAT_ID olarak ekle.
STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
if STORAGE_CHAT_ID:
    STORAGE_CHAT_ID = int(STORAGE_CHAT_ID)

# Bellek içi cache: {card_code: file_id}
_file_id_cache = {}

# Ayni sohbete (STORAGE_CHAT_ID) ardisik gonderimler arasinda Telegram'in
# flood-control limitine takilmamak icin minimum bekleme suresi (saniye).
# Telegram ayni sohbete saniyede ~1 mesajdan fazlasini genelde flood
# control ile engeller (ozellikle gruplarda). Guvenli tarafta kalmak icin
# 1.1 saniye kullaniyoruz.
_MIN_INTERVAL = 1.1

# Tum prewarm/get cagrilarinin ayni STORAGE_CHAT_ID'yi paylastigi icin
# gonderimleri sirali/throttle'li yapmak amaciyla ortak bir kilit (lock).
_send_lock = asyncio.Lock()
_last_send_time = 0.0

# Ag/indirme hatalarinda kac kez tekrar denenecegi
_MAX_RETRIES = 5


async def _throttle():
    """Bir onceki gonderimden bu yana yeterli sure gecmediyse bekler."""
    global _last_send_time
    loop = asyncio.get_event_loop()
    now = loop.time()
    wait = _MIN_INTERVAL - (now - _last_send_time)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_send_time = loop.time()


async def get_card_file_id(bot, card_code, chat_id):
    """Kart görselini indirip Telegram'a gönderir, file_id döndürür.

    NOT: `chat_id` parametresi geriye donuk uyumluluk icin duruyor ama
    KULLANILMIYOR. Gorseller her zaman STORAGE_CHAT_ID'ye gonderilir,
    boylece oyuncularin oynadigi gruba asla kart gorseli sizmaz.
    """
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

    # Telegram'a gizli depo sohbetine gönder ve file_id al.
    # Ayni sohbete art arda gonderim flood control'e takilabilir,
    # bu yuzden hem throttle hem de RetryAfter/TimedOut icin retry var.
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
            return file_id
        except RetryAfter as e:
            # Telegram bize tam olarak ne kadar bekleyecegimizi soyluyor.
            wait_s = float(getattr(e, "retry_after", 5)) + 0.5
            print(f"⏳ Flood control ({card_code}): {wait_s:.1f} sn bekleniyor...")
            await asyncio.sleep(wait_s)
        except (TimedOut, NetworkError) as e:
            wait_s = 2.0 * (attempt + 1)
            print(f"⚠️ Gönderim zaman aşımı ({card_code}), {wait_s:.1f} sn sonra tekrar denenecek: {e}")
            await asyncio.sleep(wait_s)
        except BadRequest as e:
            if "Chat not found" in str(e):
                print(
                    f"⚠️ Depo sohbeti bulunamadı ({STORAGE_CHAT_ID}). "
                    f"Botun bu sohbete eklendiğinden ve STORAGE_CHAT_ID'nin "
                    f"doğru olduğundan emin olun."
                )
            raise
        except Exception as e:
            print(f"⚠️ Kart gönderilemedi ({card_code}): {e}")
            raise

    raise Exception(f"Kart gönderilemedi, tüm denemeler tükendi: {card_code}")


async def prewarm_all_cards(bot, chat_id, card_codes):
    """Tüm kartları arka planda önbelleğe alır (depo sohbetine gönderir,
    oyunun oynandığı gruba değil).

    get_card_file_id zaten throttle + retry yaptığı için burada sıralı
    (paralel değil) şekilde çağırmak yeterli ve güvenli.
    """
    for code in card_codes:
        if code in _file_id_cache:
            continue
        try:
            await get_card_file_id(bot, code, chat_id)
        except Exception as e:
            print(f"⚠️ Önbellekleme atlandı ({code}): {e}")
    
