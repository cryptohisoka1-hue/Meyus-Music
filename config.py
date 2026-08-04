import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "",
)


# =========================================================
# TEMALAR
# =========================================================

THEME_PACKS = {

    "kedi":
        "cat_arya",

    "ejder":
        "dragon_arya",

    "prenses":
        "princess_arya",

    "gs":
        "gs_arya",

    "bjk":
        "bjk_arya",

    "fb":
        "arya_fb_theme_pack",

    "sincap":
        "arya_sincap_theme_pack",
}


DEFAULT_THEME = "kedi"


# =========================================================
# KARTLAR
# =========================================================

COLORS = [
    "R",
    "Y",
    "G",
    "B",
]


COLOR_EMOJI = {
    "R": "🔴",
    "Y": "🟡",
    "G": "🟢",
    "B": "🔵",
}


NUMBER_VALUES = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
]


ACTION_VALUES = [
    "Skip",
    "Reverse",
    "Draw2",
]


ACTION_EMOJI = {
    "Skip": "⛔",
    "Reverse": "🔄",
    "Draw2": "+2",
}


# =========================================================
# STICKER SIRASI
# =========================================================

CARD_FACES = []

for color in COLORS:

    for value in (
        NUMBER_VALUES
        + ACTION_VALUES
    ):

        CARD_FACES.append(
            f"{color}{value}"
        )


CARD_FACES.append("Wild")
CARD_FACES.append("Wild4")


# =========================================================
# OYUNCU AYARLARI
# =========================================================

MIN_PLAYERS = 2

MAX_PLAYERS = 10

STARTING_HAND_SIZE = 7

LOBBY_TIMEOUT_SECONDS = 300
