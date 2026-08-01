import asyncio

_sticker_cache = {}       # {set_name: StickerSet}
_sticker_file_cache = {}  # {(set_name, index): file_id}

async def get_sticker_set(bot, set_name):
    """Sticker setini Telegram'dan çeker ve önbelleğe alır."""
    if set_name not in _sticker_cache:
        _sticker_cache[set_name] = await bot.get_sticker_set(set_name)
    return _sticker_cache[set_name]

async def get_card_sticker_file_id(bot, set_name, card_code, sticker_index):
    """
    Belirli bir sticker index'inin file_id'sini döndürür.
    """
    key = (set_name, sticker_index)
    if key not in _sticker_file_cache:
        sticker_set = await get_sticker_set(bot, set_name)
        if sticker_index >= len(sticker_set.stickers):
            raise IndexError(
                f"Sticker index {sticker_index} sette yok "
                f"({len(sticker_set.stickers)} adet var)"
            )
        _sticker_file_cache[key] = sticker_set.stickers[sticker_index].file_id
    return _sticker_file_cache[key]
