"""
Kart kodu <-> gorsel dosya adi / URL eslestirmesi.

Kart kodu formati:
    "kirmizi_7"        -> kirmizi renk, 7 sayisi
    "kirmizi_artiiki"  -> kirmizi +2
    "kirmizi_durdur"   -> kirmizi DUR (skip)
    "kirmizi_yonvedegis" -> kirmizi YON (reverse)
    "wild_renk"        -> joker (renk sec)
    "wild_artidort"    -> joker +4

Gorseller assets/cards/<kod>.png olarak durur. Bu dosyalari kendi
GitHub reponda barindirip (veya baska bir statik host'a yukleyip)
CARD_IMAGE_BASE_URL degiskenini raw URL koku ile guncelle.

Ornek (GitHub raw):
    CARD_IMAGE_BASE_URL = "https://raw.githubusercontent.com/<kullanici>/<repo>/main/assets/cards"
"""

from config import CARD_IMAGE_BASE_URL

COLOR_LABELS = {
    "kirmizi": "🔴",
    "yesil": "🟢",
    "mavi": "🔵",
    "sari": "🟡",
}

SYMBOL_LABELS = {
    "artiiki": "+2",
    "durdur": "DUR",
    "yonvedegis": "YÖN",
}

WILD_LABELS = {
    "renk": "JOKER",
    "artidort": "JOKER +4",
}


def card_image_url(card_code: str) -> str:
    """Kart kodundan gorselin (raw) URL'ini uretir."""
    return f"{CARD_IMAGE_BASE_URL.rstrip('/')}/{card_code}.png"


def card_display_label(card_code: str) -> str:
    """Metin gerektigi yerlerde (fallback) kisa etiket uretir. Rakam ayri gosterilmez, sadece renk+tur."""
    if card_code.startswith("wild_"):
        _, symbol = card_code.split("_", 1)
        return f"⚫ {WILD_LABELS.get(symbol, symbol)}"

    color, value = card_code.split("_", 1)
    color_emoji = COLOR_LABELS.get(color, "❔")
    if value in SYMBOL_LABELS:
        return f"{color_emoji} {SYMBOL_LABELS[value]}"
    return f"{color_emoji} Kart"
