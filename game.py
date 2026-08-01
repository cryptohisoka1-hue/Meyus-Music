import random

# chat_id -> oyun bilgisi
games = {}

COLORS = ["kirmizi", "yesil", "mavi", "sari"]


def create_deck():
    """
    Kart kodlari assets/cards/<kod>.png dosya adlariyla birebir eslesir.
    Ornek: 'kirmizi_7', 'kirmizi_artiiki', 'wild_renk', 'wild_artidort'
    """
    deck = []
    for color in COLORS:
        for i in range(10):
            deck.append(f"{color}_{i}")
        deck.extend([
            f"{color}_artiiki",     # +2
            f"{color}_durdur",      # skip
            f"{color}_yonvedegis",  # reverse
        ])

    deck.extend([
        "wild_renk",
        "wild_renk",
        "wild_renk",
        "wild_renk",
        "wild_artidort",
        "wild_artidort",
        "wild_artidort",
        "wild_artidort",
    ])

    random.shuffle(deck)
    return deck


def create_game(chat_id, owner_id):
    if chat_id in games:
        return False
    games[chat_id] = {
        "owner": owner_id,
        "players": [],
        "deck": [],
        "hands": {},
        "started": False,
    }
    return True


def join_game(chat_id, user_id, name):
    if chat_id not in games:
        return "NO_GAME"

    players = games[chat_id]["players"]
    for p in players:
        if p["id"] == user_id:
            return "ALREADY_JOINED"

    players.append({
        "id": user_id,
        "name": name,
    })
    return "OK"


def start_game(chat_id):
    game = games[chat_id]
    deck = create_deck()
    game["deck"] = deck

    for player in game["players"]:
        hand = []
        for _ in range(7):
            hand.append(deck.pop())
        game["hands"][player["id"]] = hand

    game["started"] = True
    return game


def find_active_game_for_user(user_id):
    """
    Kullanicinin icinde bulundugu, basi baslamis ilk oyunu bulur.
    Inline query private ekranda calisirken chat_id bilinmedigi icin kullanilir.
    """
    for chat_id, game in games.items():
        if game.get("started") and user_id in game.get("hands", {}):
            return chat_id, game
    return None, None


lobby_messages = {}
