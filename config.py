import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_NAME = "uno_games.db"
# Depo sohbeti ID'si (kart önbellekleme için)
# None bırakırsanız oyun grubu kullanılır
_storage = os.getenv("STORAGE_CHAT_ID", "")
STORAGE_CHAT_ID = int(_storage) if _storage else None

STICKER_SET_NAME = os.getenv("STICKER_SET_NAME", "classic_colorblind")
