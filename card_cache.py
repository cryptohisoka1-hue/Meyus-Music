import os
import httpx
from telegram.error import BadRequest

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

    # Görseli indir
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {url}")
            image_data = resp.content
    except Exception as e:
        print(f"⚠️ Kart görseli indirilemedi ({card_code}): {e}")
        raise

    # Telegram'a gizli depo sohbetine gönder ve file_id al
    try:
        msg = await bot.send_photo(chat_id=STORAGE_CHAT_ID, photo=image_data)
        file_id = msg.photo[-1].file_id
        _file_id_cache[card_code] = file_id
        return file_id
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


async def prewarm_all_cards(bot, chat_id, card_codes):
    """Tüm kartları arka planda önbelleğe alır (depo sohbetine gönderir,
    oyunun oynandığı gruba değil)."""
    for code in card_codes:
        try:
            await get_card_file_id(bot, code, chat_id)
        except Exception as e:
            print(f"⚠️ Önbellekleme atlandı ({code}): {e}")
            
