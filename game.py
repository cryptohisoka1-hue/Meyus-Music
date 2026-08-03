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
        "pending_draw": 0,
        "pending_effect": None,
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
    game["turn"] = random.randrange(len(game["players"]))
    game["direction"] = 1
    game["winner"] = None
    game["has_drawn"] = {}
    game["pending_draw"] = 0
    game["pending_effect"] = None

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
    """Kullanıcının oynayabileceği kartları döndürür.

    Bekleyen bir +2/+4 cezası varsa (pending_draw > 0), sadece üstüne
    eklenebilecek (stacklenebilecek) kartlar geçerlidir:
      - pending_effect == "arti2" -> sadece +2 kartları
      - pending_effect == "arti4" -> sadece +4 (joker) kartları
    Ceza yoksa normal can_play kuralına göre değerlendirilir.
    """
    game = games[chat_id]
    hand = game["hands"].get(user_id, [])
    pending = game.get("pending_draw", 0)

    if pending:
        pending_effect = game.get("pending_effect")
        if pending_effect == "arti2":
            return [c for c in hand
                    if not c.startswith("wild_") and c.split("_")[1] == "arti2"]
        if pending_effect == "arti4":
            return [c for c in hand
                    if c.startswith("wild_") and c.split("_")[1] == "artidort"]
        return []

    top = top_card(chat_id)
    color = game["top_color"]
    return [c for c in hand if can_play(c, top, color)]


def draw_card(chat_id, user_id):
    """Kart çeker.

    Bekleyen bir ceza varsa (pending_draw > 0), o kadar kart birden çekilir,
    ceza sıfırlanır ve sıra otomatik olarak bir sonraki oyuncuya geçer
    (yani zorunlu çekimden sonra oynama hakkı yoktur).
    Ceza yoksa normal tek kart çekilir ve sıra oyuncuda kalır
    (isterse çektiği kartı oynayabilir ya da /pas ile geçebilir).
    """
    game = games[chat_id]
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    pending = game.get("pending_draw", 0)
    count = pending if pending else 1

    drawn = []
    for _ in range(count):
        if game["deck"]:
            card = game["deck"].pop()
            game["hands"][user_id].append(card)
            drawn.append(card)

    if pending:
        game["pending_draw"] = 0
        game["pending_effect"] = None
        game["has_drawn"][user_id] = True
        _next_turn(chat_id)
        return {"ok": True, "drawn": drawn, "forced": True}

    game["has_drawn"][user_id] = True
    return {"ok": True, "drawn": drawn}


def pass_turn(chat_id, user_id):
    """Pas geçer (sadece normal kart çekiminden sonra kullanılabilir)."""
    game = games[chat_id]
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}
    if not game["has_drawn"].get(user_id, False):
        return {"ok": False, "reason": "ONCE_CEK"}

    game["has_drawn"][user_id] = False
    _next_turn(chat_id)
    return {"ok": True}


def play_card(chat_id, user_id, card_code):
    """Kart oynar."""
    game = games[chat_id]
    if game.get("winner"):
        return {"ok": False, "reason": "OYUN_BITTI"}
    if current_player(chat_id) != user_id:
        return {"ok": False, "reason": "SIRA_DEGIL"}

    hand = game["hands"].get(user_id, [])
    if card_code not in hand:
        return {"ok": False, "reason": "KART_YOK"}

    pending = game.get("pending_draw", 0)
    pending_effect = game.get("pending_effect")

    if pending:
        # Bekleyen ceza varken sadece stackleme kuralına uyan kartlar geçerli
        is_arti2 = (not card_code.startswith("wild_")) and card_code.split("_")[1] == "arti2"
        is_arti4 = card_code.startswith("wild_") and card_code.split("_")[1] == "artidort"
        if pending_effect == "arti2" and not is_arti2:
            return {"ok": False, "reason": "GECERSIZ_HAMLE"}
        if pending_effect == "arti4" and not is_arti4:
            return {"ok": False, "reason": "GECERSIZ_HAMLE"}
    else:
        top = top_card(chat_id)
        color = game["top_color"]
        if not can_play(card_code, top, color):
            return {"ok": False, "reason": "GECERSIZ_HAMLE"}

    # Kartı elinden çıkar ve desteye at
    hand.remove(card_code)
    game["discard"].append(card_code)
    game["has_drawn"][user_id] = False

    # Joker (renk seçimi gerektiren kartlar)
    if card_code.startswith("wild_"):
        game["needs_color"] = True
        if card_code.split("_")[1] == "artidort":
            game["pending_draw"] = game.get("pending_draw", 0) + 4
            game["pending_effect"] = "arti4"
        return {"ok": True, "needs_color": True, "remaining": len(hand)}

    game["top_color"] = card_color(card_code)

    # Kazanma kontrolü
    if len(hand) == 0:
        game["winner"] = user_id
        return {"ok": True, "win": True}

    # Efekt kartları
    effect = None
    val = card_code.split("_")[1]

    if val == "dur":
        effect = "skip"
        _next_turn(chat_id)
    elif val == "yon":
        effect = "reverse"
        game["direction"] *= -1
        # 2 kişilik oyunlarda YÖN kartı resmi UNO kurallarına göre DUR gibi davranır:
        # sıra karşıya geçmez, kartı oynayan kişi tekrar oynar.
        if len(game["players"]) == 2:
            _next_turn(chat_id)
    elif val == "arti2":
        effect = "draw2"
        # Ceza hemen çektirilmez; bir sonraki oyuncuya sıra geçer, oyuncu
        # elinde +2 varsa üstüne koyup cezayı katlayabilir, yoksa /cek ile
        # birikmiş cezanın tamamını çeker.
        game["pending_draw"] = game.get("pending_draw", 0) + 2
        game["pending_effect"] = "arti2"
        _next_turn(chat_id)
        return {"ok": True, "effect": effect, "remaining": len(hand),
                "stacked_total": game["pending_draw"]}

    _next_turn(chat_id)
    return {"ok": True, "effect": effect, "remaining": len(hand)}


def choose_color(chat_id, user_id, color):
    """Joker sonrası renk seçimi.

    Ceza (varsa) artık pending_draw ile ertelendiği için burada hiçbir kart
    çektirilmez; sadece renk belirlenip sıra bir sonraki oyuncuya geçer.
    O oyuncu, elinde uygun bir kart varsa cezayı stackleyebilir, yoksa
    /cek ile birikmiş cezayı çeker.
    """
    game = games[chat_id]
    if not game.get("needs_color"):
        return False
    game["top_color"] = color
    game["needs_color"] = False
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
    
