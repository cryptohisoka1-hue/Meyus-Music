import os
import random
from card_sticker_map import CARD_TO_STICKER_INDEX  # <-- EKLENDİ

# Kart görselleri için temel URL
# GitHub Raw veya kendi CDN'inizi kullanın
BASE_URL = os.getenv("CARDS_BASE_URL",
    "https://raw.githubusercontent.com/cryptohisoka1-hue/Meyus-Music/main/assets/cards")

# Eğer kartları yerel kullanacaksanız:
# BASE_URL = "assets/cards"

def card_image_url(card_code):
    """Kart koduna göre görsel URL'si döndürür."""
    return f"{BASE_URL}/{card_code}.png"

def card_display_label(card_code):
    """Kartın görünen adını döndürür."""
    mapping = {
        "kirmizi_0": "🔴 0", "kirmizi_1": "🔴 1", "kirmizi_2": "🔴 2",
        "kirmizi_3": "🔴 3", "kirmizi_4": "🔴 4", "kirmizi_5": "🔴 5",
        "kirmizi_6": "🔴 6", "kirmizi_7": "🔴 7", "kirmizi_8": "🔴 8",
        "kirmizi_9": "🔴 9", "kirmizi_arti2": "🔴 +2",
        "kirmizi_dur": "🔴 DUR", "kirmizi_yon": "🔴 YÖN",

        "yesil_0": "🟢 0", "yesil_1": "🟢 1", "yesil_2": "🟢 2",
        "yesil_3": "🟢 3", "yesil_4": "🟢 4", "yesil_5": "🟢 5",
        "yesil_6": "🟢 6", "yesil_7": "🟢 7", "yesil_8": "🟢 8",
        "yesil_9": "🟢 9", "yesil_arti2": "🟢 +2",
        "yesil_dur": "🟢 DUR", "yesil_yon": "🟢 YÖN",

        "mavi_0": "🔵 0", "mavi_1": "🔵 1", "mavi_2": "🔵 2",
        "mavi_3": "🔵 3", "mavi_4": "🔵 4", "mavi_5": "🔵 5",
        "mavi_6": "🔵 6", "mavi_7": "🔵 7", "mavi_8": "🔵 8",
        "mavi_9": "🔵 9", "mavi_arti2": "🔵 +2",
        "mavi_dur": "🔵 DUR", "mavi_yon": "🔵 YÖN",

        "sari_0": "🟡 0", "sari_1": "🟡 1", "sari_2": "🟡 2",
        "sari_3": "🟡 3", "sari_4": "🟡 4", "sari_5": "🟡 5",
        "sari_6": "🟡 6", "sari_7": "🟡 7", "sari_8": "🟡 8",
        "sari_9": "🟡 9", "sari_arti2": "🟡 +2",
        "sari_dur": "🟡 DUR", "sari_yon": "🟡 YÖN",

        "wild_renk": "🌈 Renk Değiştir",
        "wild_artidort": "🌈 +4",
        "deste": "🎴 Deste",
    }
    return mapping.get(card_code, card_code)


# Renk bilgileri
COLOR_NAME_TR = {
    "kirmizi": "Kırmızı",
    "yesil": "Yeşil",
    "mavi": "Mavi",
    "sari": "Sarı",
    "wild": "Joker",
}

COLOR_LABELS = {
    "kirmizi": "🔴",
    "yesil": "🟢",
    "mavi": "🔵",
    "sari": "🟡",
}

# Deste arka yüzü
DECK_BACK_CODE = "deste"

# Tüm kart kodları
ALL_CARD_CODES = list(CARD_TO_STICKER_INDEX.keys()) + [DECK_BACK_CODE]


def build_deck():
    """Standart UNO destesi oluşturur."""
    deck = []
    colors = ["kirmizi", "yesil", "mavi", "sari"]

    for color in colors:
        # 0 bir kere
        deck.append(f"{color}_0")
        # 1-9 ikişer kere
        for num in range(1, 10):
            deck.extend([f"{color}_{num}", f"{color}_{num}"])
        # Özel kartlar ikişer kere
        deck.extend([f"{color}_arti2", f"{color}_arti2"])
        deck.extend([f"{color}_dur", f"{color}_dur"])
        deck.extend([f"{color}_yon", f"{color}_yon"])

    # Jokerler 4'er kere
    deck.extend(["wild_renk"] * 4)
    deck.extend(["wild_artidort"] * 4)

    random.shuffle(deck)
    return deck


def card_color(card_code):
    """Kartın rengini döndürür."""
    if card_code.startswith("wild_"):
        return "wild"
    return card_code.split("_")[0]


def card_value(card_code):
    """Kartın değerini döndürür."""
    return card_code.split("_", 1)[1]


def can_play(card_code, top_card, top_color):
    """Kart oynanabilir mi kontrol eder."""
    if card_code.startswith("wild_"):
        return True

    card_c = card_color(card_code)
    card_v = card_value(card_code)
    top_c = card_color(top_card) if not top_card.startswith("wild_") else top_color
    top_v = card_value(top_card)

    return card_c == top_c or card_v == top_v
