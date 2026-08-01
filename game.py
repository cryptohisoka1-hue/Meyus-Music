import random

# chat_id -> oyun bilgisi
games = {}

# user_id -> chat_id (kullanıcının aktif oyunda olduğu grup, inline query için hızlı lookup)
user_active_chat = {}

COLORS = ["kirmizi", "yesil", "mavi", "sari"]
SYMBOLS = ["artiiki", "durdur", "yonvedegis"]


def create_deck():
    """
    Kart kodları assets/cards/<kod>.png dosya adlarıyla birebir eşleşir.
    Örnek: 'kirmizi_7', 'kirmizi_artiiki', 'wild_renk', 'wild_artidort'
    """
    deck = []
    for color in COLORS:
        deck.append(f"{color}_0")
        for i in range(1, 10):
            deck.append(f"{color}_{i}")
            deck.append(f"{color}_{i}")
        for symbol in SYMBOLS:
            deck.append(f"{color}_{symbol}")
            deck.append(f"{color}_{symbol}")

    deck.extend(["wild_renk"] * 4)
    deck.extend(["wild_artidort"] * 4)

    random.shuffle(deck)
    return deck


def card_color(card_code):
    if card_code.startswith("wild"):
        return None
    return card_code.split("_", 1)[0]


def card_value(card_code):
    if card_code.startswith("wild"):
        _, v = card_code.split("_", 1)
        return v
    _, v = card_code.split("_", 1)
    return v


def is_wild(card_code):
    return card_code.startswith("wild")


def create_game(chat_id, owner_id):
    if chat_id in games:
        return False
    games[chat_id] = {
        "owner": owner_id,
        "players": [],
        "deck": [],
        "discard": [],
        "hands": {},
        "started": False,
        "turn_order": [],
        "turn_index": 0,
        "direction": 1,
        "top_color": None,
        "pending_wild": None,
        "winner": None,
        "has_drawn": {},
    }
    return True


def join_game(chat_id, user_id, name):
    if chat_id not in games:
        return "NO_GAME"

    players = games[chat_id]["players"]
    for p in players:
        if p["id"] == user_id:
            return "ALREADY_JOINED"

    players.append({"id": user_id, "name": name})
    return "OK"


def _draw_from_deck(game, n=1):
    """Deste bitince, atılan kartlardan (son üst kart hariç) yeni deste oluşturur."""
    cards = []
    for _ in range(n):
        if not game["deck"]:
            if len(game["discard"]) <= 1:
                break
            top = game["discard"][-1]
            reshuffled = game["discard"][:-1]
            random.shuffle(reshuffled)
            game["deck"] = reshuffled
            game["discard"] = [top]
        if game["deck"]:
            cards.append(game["deck"].pop())
    return cards


def start_game(chat_id):
    game = games[chat_id]
    game["deck"] = create_deck()
    game["turn_order"] = [p["id"] for p in game["players"]]
    game["turn_index"] = 0
    game["direction"] = 1
    game["winner"] = None
    game["has_drawn"] = {p["id"]: False for p in game["players"]}

    for player in game["players"]:
        hand = []
        for _ in range(7):
            hand.append(game["deck"].pop())
        game["hands"][player["id"]] = hand
        user_active_chat[player["id"]] = chat_id

    # Başlangıç üst kartı: joker olmayan bir kart çıkana kadar çek
    first = game["deck"].pop()
    while is_wild(first):
        game["deck"].insert(0, first)
        random.shuffle(game["deck"])
        first = game["deck"].pop()
    game["discard"] = [first]
    game["top_color"] = card_color(first)

    game["started"] = True
    return game


def find_active_game_for_user(user_id):
    chat_id = user_active_chat.get(user_id)
    if chat_id and chat_id in games and games[chat_id].get("started"):
        return chat_id, games[chat_id]
    return None, None


def current_player(chat_id):
    game = games[chat_id]
    if not game["turn_order"]:
        return None
    return game["turn_order"][game["turn_index"] % len(game["turn_order"])]


def top_card(chat_id):
    return games[chat_id]["discard"][-1]


def top_color(chat_id):
    return games[chat_id]["top_color"]


def is_legal_play(chat_id, card_code):
    if is_wild(card_code):
        return True
    game = games[chat_id]
    t_color = game["top_color"]
    t_card = top_card(chat_id)
    if card_color(card_code) == t_color:
        return True
    if not is_wild(t_card) and card_value(card_code) == card_value(t_card):
        return True
    return False


def legal_cards_for(chat_id, user_id):
    game = games[chat_id]
    hand = game["hands"].get(user_id, [])
    return [c for c in hand if is_legal_play(chat_id, c)]


def _advance_turn(game, steps=1):
    n = len(game["turn_order"])
    if n == 0:
        return
    game["turn_index"] = (game["turn_index"] + steps * game["direction"]) % n


def play_card(chat_id, user_id, card_code):
    """
    Dönüş: dict {
      'ok': bool, 'reason': str (hata durumunda),
      'effect': 'normal'|'skip'|'reverse'|'draw2'|'draw4'|None,
      'needs_color': bool, 'win': bool
    }
    """
    game = games[chat_id]

    if game.get("winner"):
        return {"ok": False, "reason": "OYUN_BITTI"}

    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    hand = game["hands"].get(user_id, [])
    if card_code not in hand:
        return {"ok": False, "reason": "KART_YOK"}

    if not is_legal_play(chat_id, card_code):
        return {"ok": False, "reason": "GECERSIZ_HAMLE"}

    hand.remove(card_code)
    game["discard"].append(card_code)

    # Kart oynanınca has_drawn sıfırlanır
    game["has_drawn"][user_id] = False

    if not is_wild(card_code):
        game["top_color"] = card_color(card_code)

    if not hand:
        game["winner"] = user_id
        return {"ok": True, "effect": None, "needs_color": False, "win": True}

    value = card_value(card_code)
    effect = "normal"
    needs_color = False

    if value == "durdur":
        effect = "skip"
        _advance_turn(game, steps=2)
    elif value == "yonvedegis":
        effect = "reverse"
        game["direction"] *= -1
        if len(game["turn_order"]) == 2:
            _advance_turn(game, steps=2)
        else:
            _advance_turn(game, steps=1)
    elif value == "artiiki":
        effect = "draw2"
        next_uid = game["turn_order"][(game["turn_index"] + game["direction"]) % len(game["turn_order"])]
        game["hands"][next_uid].extend(_draw_from_deck(game, 2))
        _advance_turn(game, steps=2)
    elif value == "artidort":
        effect = "draw4"
        next_uid = game["turn_order"][(game["turn_index"] + game["direction"]) % len(game["turn_order"])]
        game["hands"][next_uid].extend(_draw_from_deck(game, 4))
        game["pending_wild"] = user_id
        needs_color = True
        _advance_turn(game, steps=2)
    elif value == "renk":
        game["pending_wild"] = user_id
        needs_color = True
        _advance_turn(game, steps=1)
    else:
        _advance_turn(game, steps=1)

    return {"ok": True, "effect": effect, "needs_color": needs_color, "win": False}


def choose_color(chat_id, user_id, color):
    game = games[chat_id]
    if game.get("pending_wild") != user_id:
        return False
    if color not in COLORS:
        return False
    game["top_color"] = color
    game["pending_wild"] = None
    return True


def draw_card(chat_id, user_id):
    """
    Kart çeker. Sıra OTOMATİK GEÇMEZ.
    Oyuncu çektiği kartı oynayabilir veya pas geçebilir.
    """
    game = games[chat_id]

    if game.get("winner"):
        return {"ok": False, "reason": "OYUN_BITTI"}

    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    drawn = _draw_from_deck(game, 1)
    if drawn:
        game["hands"][user_id].extend(drawn)
        game["has_drawn"][user_id] = True

    # Sıra ilerlemez → oyuncu isterse oynar, isterse pas geçer
    return {"ok": True, "drawn": drawn}


def pass_turn(chat_id, user_id):
    """
    Oyuncu pas geçer.
    Sadece kart çektikten sonra geçerlidir.
    """
    game = games.get(chat_id)
    if not game or not game.get("started") or game.get("winner"):
        return {"ok": False, "reason": "OYUN_YOK"}

    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    # Çekmeden pas geçilemez
    if not game.get("has_drawn", {}).get(user_id, False):
        return {"ok": False, "reason": "ONCE_CEK"}

    game["has_drawn"][user_id] = False
    _advance_turn(game, steps=1)
    return {"ok": True}


def end_game(chat_id):
    for uid in list(games.get(chat_id, {}).get("hands", {}).keys()):
        if user_active_chat.get(uid) == chat_id:
            user_active_chat.pop(uid, None)
    games.pop(chat_id, None)


lobby_messages = {}
