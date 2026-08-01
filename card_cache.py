import httpx
from telegram.error import BadRequest

# Bellek içi cache: {card_code: file_id}
_file_id_cache = {}

async def get_card_file_id(bot, card_code, chat_id):
    """Kart görselini indirip Telegram'a gönderir, file_id döndürür."""
    if card_code in _file_id_cache:
        return _file_id_cache[card_code]

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

    # Telegram'a gönder ve file_id al
    try:
        msg = await bot.send_photo(chat_id=chat_id, photo=image_data)
        file_id = msg.photo[-1].file_id
        _file_id_cache[card_code] = file_id
        return file_id
    except BadRequest as e:
        if "Chat not found" in str(e):
            print(f"⚠️ Depo sohbeti bulunamadı ({chat_id}). STORAGE_CHAT_ID kontrol edin.")
        raise
    except Exception as e:
        print(f"⚠️ Kart gönderilemedi ({card_code}): {e}")
        raise


async def prewarm_all_cards(bot, chat_id, card_codes):
    """Tüm kartları arka planda önbelleğe alır."""
    for code in card_codes:
        try:
            await get_card_file_id(bot, code, chat_id)
        except Exception as e:
            print(f"⚠️ Önbellekleme atlandı ({code}): {e}")
