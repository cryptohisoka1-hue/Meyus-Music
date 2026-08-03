# Oyuncuların seçebileceği kart temaları (sticker paketleri).
# Her tema bir Telegram sticker paketine karşılık gelir.
# "sticker_set" alanı, t.me/addstickers/<BURASI> kısmındaki paket adıdır.

DEFAULT_THEME = "classic_colorblind"

THEMES = [
    {"id": "classic_colorblind", "name": "🎨 Klasik",       "sticker_set": "classic_colorblind"},
    {"id": "cat_arya",           "name": "🐱 Kedi",         "sticker_set": "cat_arya"},
    {"id": "princess_arya",      "name": "👸 Prenses",       "sticker_set": "princess_arya"},
    {"id": "bjk_arya",           "name": "⚫⚪ BJK",         "sticker_set": "bjk_arya"},
    {"id": "gs_arya",            "name": "🟡🔴 GS",          "sticker_set": "gs_arya"},
    {"id": "arya_fb_theme_pack", "name": "🔵🟡 FB",          "sticker_set": "arya_fb_theme_pack"},
    {"id": "wolf_arya",          "name": "🐺 Kurt",         "sticker_set": "wolf_arya"},
]

_THEMES_BY_ID = {t["id"]: t for t in THEMES}


def get_theme_by_id(theme_id):
    """Geçerli bir tema ID'si döndürür; bulunamazsa varsayılana düşer."""
    return _THEMES_BY_ID.get(theme_id, _THEMES_BY_ID[DEFAULT_THEME])
  
