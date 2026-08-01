"""
Telegram'in URL'den resim cekme mekanizmasi bazi CDN/host'larda
'Wrong type of the web page content' hatasi verebiliyor.

Bu modul, karti BOTUN KENDISI indirip Telegram'a byte olarak yukler,
donen file_id'yi bellekte cache'ler. Ayni kart bir daha ihtiyac
duyuldugunda tekrar indirmeden, cache'lenmis file_id ile aninda kullanilir.

Ilk kullanimda kart resmi hedef sohbete kisaca yuklenip hemen silinir
(sadece file_id almak icin) - sonraki kullanimlar tamamen aninda olur.

NOT: storage_chat_id olarak OYUN GRUBU degil, botun kendine ait GIZLI
bir depo sohbeti/kanali (CACHE_CHAT_ID) kullanilmali. Aksi halde
oyuncular, onbellekleme sirasinda gonderilip silinen kart fotograflarini
gorebilir ve bunu "bot kendi kendine kart oynuyor" olarak algilayabilir.
"""

import asyncio
from io import BytesIO

import requests

from cards_data import card_image_url

_file_id_cache = {}
_cache_lock = asyncio.Lock()


async def get_card_file_id(bot, card_code: str, storage_chat_id: int) -> str:
    if card_code in _file_id_cache:
        return _file_id_cache[card_code]

    # Ayni kart icin es zamanli birden fazla istek gelirse (ornegin
    # inline_hand + prewarm_all_cards ayni anda calisirsa), sadece bir
    # tanesi gercekten indirip yuklesin; digerleri onu beklesin.
    async with _cache_lock:
        if card_code in _file_id_cache:
            return _file_id_cache[card_code]

        url = card_image_url(card_code)
        try:
            response = await asyncio.to_thread(requests.get, url, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"⚠️ Kart gorseli indirilemedi ({card_code}): {e}")
            raise

        buffer = BytesIO(response.content)
        buffer.name = f"{card_code}.png"

        try:
            msg = await bot.send_photo(
                storage_chat_id, photo=buffer, disable_notification=True
            )
        except Exception as e:
            print(f"⚠️ Kart gorseli depo sohbetine yuklenemedi ({card_code}): {e}")
            raise

        file_id = msg.photo[-1].file_id
        _file_id_cache[card_code] = file_id

        try:
            await msg.delete()
        except Exception:
            pass

        return file_id


async def prewarm_all_cards(bot, storage_chat_id: int, card_codes) -> None:
    """
    Butun kart gorsellerini onceden indirip cache'ler (arka planda, fire-and-forget
    olarak cagrilmali). Telegram flood limitine takilmamak icin sirayla, aralarda
    kucuk bir bekleme ile calisir.
    """
    for card_code in card_codes:
        if card_code in _file_id_cache:
            continue
        try:
            await get_card_file_id(bot, card_code, storage_chat_id)
        except Exception as e:
            print(f"⚠️ Onbellekleme atlandi ({card_code}): {e}")
        await asyncio.sleep(0.05)
        
