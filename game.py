import random
from cards_data import build_deck, card_color, can_play

# Bellek içi oyun verisi
games = {}
lobby_messages = {}
user_active_chat = {}


def create_game(chat_id, owner_id):
    """Yeni oyun lobisi oluşturur."""
    if chat_id in games:
        return False
    games[chat_id] = {
        "owner": owner_id,
        "players": [],
        "started": False,
        "deck": [],
        "discard": [],
        "hands": {},
        "top_color": None,
        "turn": 0,
        "direction": 1,
        "winner": None,
        "has_drawn": {},
        "needs_color": False,
    }
    return True


def join_game(chat_id, user_id, user_name):
    """Oyuncuyu lobiye ekler."""
    if chat_id not in games:
        return "NO_GAME"
    game = games[chat_id]
    if game["started"]:
        return False
    for p in game["players"]:
        if p["id"] == user_id:
            return "ALREADY_JOINED"
    game["players"].append({"id": user_id, "name": user_name})
    user_active_chat[user_id] = chat_id
    return True


def start_game(chat_id):
    """Oyunu başlatır."""
    game = games[chat_id]
    game["started"] = True
    game["deck"] = build_deck()
    game["discard"] = []
    game["hands"] = {}
    game["turn"] = 0
    game["direction"] = 1
    game["winner"] = None
    game["has_drawn"] = {}

    # Her oyuncuya 7 kart dağıt
    for p in game["players"]:
        hand = [game["deck"].pop() for _ in range(7)]
        game["hands"][p["id"]] = hand

    # İlk kartı aç
    while True:
        first = game["deck"].pop()
        if not first.startswith("wild_"):
            break
        game["deck"].insert(0, first)

    game["discard"].append(first)
    game["top_color"] = card_color(first)
    return game


def top_card(chat_id):
    """Üstteki kartı döndürür."""
    return games[chat_id]["discard"][-1]


def current_player(chat_id):
    """Sıradaki oyuncunun ID'sini döndürür."""
    game = games[chat_id]
    idx = game["turn"] % len(game["players"])
    return game["players"][idx]["id"]


def legal_cards_for(chat_id, user_id):
    """Kullanıcının oynayabileceği kartları döndürür."""
    game = games[chat_id]
    hand = game["hands"].get(user_id, [])
    top = top_card(chat_id)
    color = game["top_color"]
    return [c for c in hand if can_play(c, top, color)]


def draw_card(chat_id, user_id):
    """Kart çeker."""
    game = games[chat_id]
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    drawn = []
    if game["deck"]:
        card = game["deck"].pop()
        game["hands"][user_id].append(card)
        drawn.append(card)

    game["has_drawn"][user_id] = True
    return {"ok": True, "drawn": drawn}


def pass_turn(chat_id, user_id):
    """Pas geçer."""
    game = games[chat_id]
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}
    if not game["has_drawn"].get(user_id, False):
        return {"ok": False, "reason": "ONCE_CEK"}

    game["has_drawn"][user_id] = False
    _next_turn(chat_id)
    return {"ok": True}


def play_card(chat_id, user_id, card_code):
    """Kart oynar.

    Dönen dict HER ZAMAN şu key'leri içerir (tutarlı şekil, KeyError'ları
    önlemek için): ok, reason (sadece ok=False iken), win, needs_color, effect.
    """
    game = games[chat_id]

    if game.get("winner"):
        return {"ok": False, "reason": "OYUN_BITTI"}
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    hand = game["hands"].get(user_id, [])
    if card_code not in hand:
        return {"ok": False, "reason": "KART_YOK"}

    top = top_card(chat_id)
    color = game["top_color"]
    if not can_play(card_code, top, color):
        return {"ok": False, "reason": "GECERSIZ_HAMLE"}

    # Başarılı hamle için varsayılan (default) sonuç şekli.
    # Aşağıdaki tüm dallar bu sözlüğü doldurup döndürür; hiçbir dal
    # eksik key ile dönmez.
    result = {"ok": True, "win": False, "needs_color": False, "effect": None}

    # Kartı elinden çıkar ve desteye at
    hand.remove(card_code)
    game["discard"].append(card_code)
    game["has_drawn"][user_id] = False

    # Joker rengi
    if card_code.startswith("wild_"):
        game["needs_color"] = True
        result["needs_color"] = True
        return result

    game["top_color"] = card_color(card_code)

    # Kazanma kontrolü
    if len(hand) == 0:
        game["winner"] = user_id
        result["win"] = True
        return result

    # Efekt kartları
    effect = None
    val = card_code.split("_")[1]

    if val == "dur":
        effect = "skip"
        _next_turn(chat_id)
    elif val == "yon":
        effect = "reverse"
        game["direction"] *= -1
    elif val == "arti2":
        effect = "draw2"
        _next_turn(chat_id)
        next_id = current_player(chat_id)
        for _ in range(2):
            if game["deck"]:
                game["hands"][next_id].append(game["deck"].pop())
        _next_turn(chat_id)
        result["effect"] = effect
        return result

    _next_turn(chat_id)
    result["effect"] = effect
    return result


def choose_color(chat_id, user_id, color):
    """Joker sonrası renk seçimi."""
    game = games[chat_id]
    if not game.get("needs_color"):
        return False
    game["top_color"] = color
    game["needs_color"] = False

    # Son atılan jokeri kontrol et
    last = game["discard"][-1]
    if last == "wild_artidort":
        _next_turn(chat_id)
        next_id = current_player(chat_id)
        for _ in range(4):
            if game["deck"]:
                game["hands"][next_id].append(game["deck"].pop())
        _next_turn(chat_id)
        return True

    _next_turn(chat_id)
    return True


def _next_turn(chat_id):
    """Sırayı bir sonraki oyuncuya geçirir."""
    game = games[chat_id]
    n = len(game["players"])
    game["turn"] = (game["turn"] + game["direction"]) % n


def end_game(chat_id):
    """Oyunu sonlandırır."""
    if chat_id in games:
        game = games[chat_id]
        for p in game.get("players", []):
            user_active_chat.pop(p["id"], None)
        games.pop(chat_id, None)


def find_active_game_for_user(user_id):
    """Kullanıcının aktif oyununu bulur."""
    chat_id = user_active_chat.get(user_id)
    if chat_id and chat_id in games:
        return chat_id, games[chat_id]
    return None, None
        
