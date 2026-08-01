"""
Telegram'in URL'den resim cekme mekanizmasi bazi CDN/host'larda
'Wrong type of the web page content' hatasi verebiliyor.

Bu modul, karti BOTUN KENDISI indirip Telegram'a byte olarak yukler,
donen file_id'yi bellekte cache'ler. Ayni kart bir daha ihtiyac
duyuldugunda tekrar indirmeden, cache'lenmis file_id ile aninda kullanilir.

Ilk kullanimda kart resmi hedef sohbete kisaca yuklenip hemen silinir
(sadece file_id almak icin) - sonraki kullanimlar tamamen aninda olur.
"""

import asyncio
from io import BytesIO

import requests

from cards_data import card_image_url

_file_id_cache = {}


async def get_card_file_id(bot, card_code: str, storage_chat_id: int) -> str:
    if card_code in _file_id_cache:
        return _file_id_cache[card_code]

    url = card_image_url(card_code)
    response = await asyncio.to_thread(requests.get, url, timeout=15)
    response.raise_for_status()

    buffer = BytesIO(response.content)
    buffer.name = f"{card_code}.png"

    msg = await bot.send_photo(storage_chat_id, photo=buffer)
    file_id = msg.photo[-1].file_id
    _file_id_cache[card_code] = file_id

    try:
        await msg.delete()
    except Exception:
        pass

    return file_id
