"""
Kart gorsellerini foto olarak indirip yukleme yerine, Telegram'in kendi
sticker paketini (ornegin 'classic_colorblind') kullanmak icin yardimci
modul. Sticker'lar Telegram sunucularinda zaten hazir oldugundan hicbir
indirme/yukleme/depo-sohbet ihtiyaci olmadan aninda kullanilabilir.
"""

import asyncio

_sticker_set_cache = None
_lock = asyncio.Lock()


async def get_sticker_set(bot, set_name: str):
    global _sticker_set_cache
    if _sticker_set_cache is not None:
        return _sticker_set_cache
    async with _lock:
        if _sticker_set_cache is None:
            _sticker_set_cache = await bot.get_sticker_set(set_name)
    return _sticker_set_cache


async def get_card_sticker_file_id(bot, set_name: str, card_code: str, mapping: dict):
    """mapping: {card_code: sticker_index} seklinde, cards_data/card_sticker_map'ten gelir."""
    idx = mapping.get(card_code)
    if idx is None:
        return None
    sticker_set = await get_sticker_set(bot, set_name)
    if idx >= len(sticker_set.stickers):
        return None
    return sticker_set.stickers[idx].file_id
    
