import random

# chat_id -> oyun bilgisi
games = {}
lobby_messages = {}

COLORS = ["🔴", "🟢", "🔵", "🟡"]
COLOR_NAMES = {"🔴": "Kırmızı", "🟢": "Yeşil", "🔵": "Mavi", "🟡": "Sarı"}
NAME_TO_COLOR = {
    "kirmizi": "🔴", "kırmızı": "🔴",
    "yesil": "🟢", "yeşil": "🟢",
    "mavi": "🔵",
    "sari": "🟡", "sarı": "🟡",
}


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


def is_wild(card):
    return card.startswith("🌈")


def card_color(card):
    if is_wild(card):
        return None
    return card[0]


def card_value(card):
    return card[1:]


def can_play_card(card, top_card, current_color):
    if is_wild(card):
        return True
    if card_color(card) == current_color:
        return True
    if not is_wild(top_card) and card_value(card) == card_value(top_card):
        return True
    return False


# ---------- Lobi yönetimi ----------

def create_game(chat_id, owner_id):
    if chat_id in games:
        return False

    games[chat_id] = {
        "owner": owner_id,
        "players": [],
        "deck": [],
        "hands": {},
        "discard": [],
        "turn_order": [],
        "turn_index": 0,
        "direction": 1,
        "current_color": None,
        "pending_color_choice": None,
        "pending_draw": 0,
        "winner": None,
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


def end_game(chat_id):
    if chat_id not in games:
        return False

    del games[chat_id]
    if chat_id in lobby_messages:
        del lobby_messages[chat_id]

    return True


def get_player_name(chat_id, user_id):
    game = games.get(chat_id)
    if not game:
        return "?"
    for p in game["players"]:
        if p["id"] == user_id:
            return p["name"]
    return "?"


# ---------- Oyun başlatma ----------

def start_game(chat_id):
    game = games[chat_id]
    deck = create_deck()

    hands = {}
    for player in game["players"]:
        hand = [deck.pop() for _ in range(7)]
        hands[player["id"]] = hand
    game["hands"] = hands

    # Başlangıç üst kartı joker olmasın
    first = deck.pop()
    tries = 0
    while is_wild(first) and deck and tries < 20:
        deck.insert(0, first)
        first = deck.pop()
        tries += 1

    game["deck"] = deck
    game["discard"] = [first]
    game["current_color"] = card_color(first) or random.choice(COLORS)
    game["turn_order"] = [p["id"] for p in game["players"]]
    game["turn_index"] = 0
    game["direction"] = 1
    game["pending_color_choice"] = None
    game["pending_draw"] = 0
    game["winner"] = None
    game["started"] = True

    return game


# ---------- Sıra / kart çekme yardımcıları ----------

def advance_turn(chat_id, steps=1):
    game = games[chat_id]
    n = len(game["turn_order"])
    game["turn_index"] = (game["turn_index"] + game["direction"] * steps) % n


def player_at_offset(chat_id, offset):
    game = games[chat_id]
    n = len(game["turn_order"])
    idx = (game["turn_index"] + game["direction"] * offset) % n
    return game["turn_order"][idx]


def get_current_player_id(chat_id):
    game = games[chat_id]
    return game["turn_order"][game["turn_index"]]


def reshuffle_discard(chat_id):
    game = games[chat_id]
    if len(game["discard"]) <= 1:
        return
    top = game["discard"][-1]
    rest = game["discard"][:-1]
    random.shuffle(rest)
    game["deck"] = rest
    game["discard"] = [top]


def draw_cards(chat_id, user_id, count):
    game = games[chat_id]
    for _ in range(count):
        if not game["deck"]:
            reshuffle_discard(chat_id)
            if not game["deck"]:
                break
        game["hands"][user_id].append(game["deck"].pop())


# ---------- Oyun aksiyonları ----------

def play_card(chat_id, user_id, index):
    game = games.get(chat_id)
    if not game or not game.get("started"):
        return {"status": "NO_GAME"}
    if game.get("winner"):
        return {"status": "GAME_OVER"}
    if game.get("pending_color_choice"):
        return {"status": "WAITING_COLOR"}

    current_id = game["turn_order"][game["turn_index"]]
    if user_id != current_id:
        return {"status": "NOT_YOUR_TURN"}

    hand = game["hands"].get(user_id)
    if hand is None:
        return {"status": "NOT_PLAYER"}
    if index < 0 or index >= len(hand):
        return {"status": "INVALID_INDEX"}

    card = hand[index]
    top_card = game["discard"][-1]

    if not can_play_card(card, top_card, game["current_color"]):
        return {"status": "INVALID_CARD"}

    hand.pop(index)
    game["discard"].append(card)

    if len(hand) == 0:
        game["winner"] = user_id
        return {"status": "WIN", "card": card}

    if is_wild(card):
        game["pending_color_choice"] = user_id
        game["pending_draw"] = 4 if card == "🌈+4" else 0
        return {"status": "WILD_PLAYED", "card": card}

    game["current_color"] = card_color(card)
    value = card_value(card)

    if value == "🔄":
        game["direction"] *= -1
        steps = 2 if len(game["turn_order"]) == 2 else 1
        advance_turn(chat_id, steps)
        return {"status": "OK", "card": card, "effect": "reverse"}

    if value == "⛔":
        skipped_id = player_at_offset(chat_id, 1)
        advance_turn(chat_id, 2)
        return {"status": "OK", "card": card, "effect": "skip", "skipped": skipped_id}

    if value == "+2":
        target_id = player_at_offset(chat_id, 1)
        draw_cards(chat_id, target_id, 2)
        advance_turn(chat_id, 2)
        return {"status": "OK", "card": card, "effect": "+2", "target": target_id}

    advance_turn(chat_id, 1)
    return {"status": "OK", "card": card, "effect": "normal"}


def choose_color(chat_id, user_id, color):
    game = games.get(chat_id)
    if not game or not game.get("started"):
        return {"status": "NO_GAME"}
    if game.get("pending_color_choice") != user_id:
        return {"status": "NOT_PENDING"}
    if color not in COLORS:
        return {"status": "INVALID_COLOR"}

    game["current_color"] = color
    pending_draw = game.get("pending_draw", 0)
    game["pending_color_choice"] = None
    game["pending_draw"] = 0

    if pending_draw:
        target_id = player_at_offset(chat_id, 1)
        draw_cards(chat_id, target_id, pending_draw)
        advance_turn(chat_id, 2)
        return {"status": "OK", "effect": "+4", "target": target_id, "color": color}

    advance_turn(chat_id, 1)
    return {"status": "OK", "effect": "wild", "color": color}


def draw_turn(chat_id, user_id):
    game = games.get(chat_id)
    if not game or not game.get("started"):
        return {"status": "NO_GAME"}
    if game.get("winner"):
        return {"status": "GAME_OVER"}
    if game.get("pending_color_choice"):
        return {"status": "WAITING_COLOR"}

    current_id = game["turn_order"][game["turn_index"]]
    if user_id != current_id:
        return {"status": "NOT_YOUR_TURN"}

    draw_cards(chat_id, user_id, 1)
    advance_turn(chat_id, 1)
    return {"status": "OK"}


# ---------- Görüntüleme ----------

def hand_alert_text(chat_id, user_id):
    game = games.get(chat_id)
    if not game or not game.get("started"):
        return None
    hand = game["hands"].get(user_id)
    if hand is None:
        return None

    top = game["discard"][-1]
    color_name = COLOR_NAMES.get(game["current_color"], game["current_color"])
    turn_name = get_player_name(chat_id, game["turn_order"][game["turn_index"]])

    header = f"Üst:{top} Renk:{color_name} Sıra:{turn_name}\n"
    cards_line = " ".join(f"{i + 1}:{c}" for i, c in enumerate(hand))
    return header + cards_line
    
