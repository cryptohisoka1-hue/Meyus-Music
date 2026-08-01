from telegram import Bot

UNO_STICKER_SET = "UnoCardsDeck"

_stickers = {}
_loaded = False


async def load_uno_stickers(bot: Bot):
    """
    UnoCardsDeck paketindeki stickerları Telegram'dan alır.
    Sticker sırası, ALL_CARD_CODES sırasıyla eşleşmelidir.
    """
    global _stickers, _loaded

    if _loaded:
        return _stickers

    sticker_set = await bot.get_sticker_set(UNO_STICKER_SET)

    if not sticker_set or not sticker_set.stickers:
        raise RuntimeError("UnoCardsDeck sticker paketi bulunamadı.")

    _stickers.clear()

    for index, sticker in enumerate(sticker_set.stickers):
        _stickers[index] = sticker.file_id

    _loaded = True

    print(f"✅ UnoCardsDeck yüklendi: {len(_stickers)} sticker")

    return _stickers


async def get_card_sticker(bot: Bot, card_index: int):
    if not _loaded:
        await load_uno_stickers(bot)

    return _stickers.get(card_index)


async def get_all_stickers(bot: Bot):
    if not _loaded:
        await load_uno_stickers(bot)

    return _stickers
