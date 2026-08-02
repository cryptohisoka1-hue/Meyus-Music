import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ayarlanmamış! Railway Variables'a eklenmeli.")
# Depo sohbeti ID'si (kart önbellekleme için)
# None bırakırsanız oyun grubu kullanılır
_storage = os.getenv("STORAGE_CHAT_ID", "")
STORAGE_CHAT_ID = int(_storage) if _storage else None

STICKER_SET_NAME = os.getenv("STICKER_SET_NAME", "classic_colorblind")
