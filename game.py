import random

# chat_id -> oyun bilgisi
games = {}

COLORS = ["🔴", "🟢", "🔵", "🟡"]


def create_deck():
    deck = []

    for color in COLORS:
        for i in range(10):
            deck.append(f"{color}{i}")

        deck.extend([
            f"{color}+2",
            f"{color}⛔",
            f"{color}🔄"
        ])

    deck.extend([
        "🌈",
        "🌈",
        "🌈",
        "🌈",
        "🌈+4",
        "🌈+4",
        "🌈+4",
        "🌈+4"
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
        "started": False
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
        "name": name
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
