import os

# GUVENLIK UYARISI: Token'i asla kod icine yazip GitHub'a push etme!
# Eski token public repoda gorunuyordu -> BotFather'dan /revoke ile IPTAL ET,
# yeni token al ve asagidaki gibi ortam degiskeni (environment variable) olarak ver.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Veritabani dosya adi
DATABASE_NAME = os.environ.get("DATABASE_NAME", "uno_games.db")

# Kart gorsellerinin barindigi kok URL.
# assets/cards klasorunu GitHub reponda push ettikten sonra
# asagidaki degeri kendi raw URL'in ile degistir. Ornek:
# "https://raw.githubusercontent.com/cryptohisoka1-hue/Meyus-Music/main/assets/cards"
CARD_IMAGE_BASE_URL = os.environ.get(
    "CARD_IMAGE_BASE_URL",
    "https://raw.githubusercontent.com/cryptohisoka1-hue/Meyus-Music/main/assets/cards",
)
