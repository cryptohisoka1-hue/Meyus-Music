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

        # Joker renk seçimi
        "needs_color": False,

        # +2 / +4 zincir sistemi
        #
        # None       = zincir yok
        # "draw2"    = +2 zinciri aktif
        # "draw4"    = +4 zinciri aktif
        #
        # Örnek:
        # +2 -> +2 -> +4
        # burada draw_chain = "draw4"
        "draw_chain": None,

        # Birikmiş ceza
        #
        # +2 -> +2 = 4
        # +2 -> +4 = 6
        # +4 -> +4 = 8
        "pending_draw": 0,

        # +4 üzerine sadece 1 adet +4 karşılık hakkı
        #
        # +4 -> +4 yapılınca True olur.
        # Bir sonraki oyuncu artık +4 atamaz.
        "draw4_response_used": False,
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

    game["players"].append({
        "id": user_id,
        "name": user_name
    })

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

    game["needs_color"] = False
    game["draw_chain"] = None
    game["pending_draw"] = 0
    game["draw4_response_used"] = False

    # Her oyuncuya 7 kart
    for p in game["players"]:
        hand = [
            game["deck"].pop()
            for _ in range(7)
        ]

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


def _card_value(card_code):
    """Kartın değerini döndürür."""
    parts = card_code.split("_", 1)

    if len(parts) == 2:
        return parts[1]

    return ""


def _is_draw2(card_code):
    return _card_value(card_code) == "arti2"


def _is_draw4(card_code):
    return card_code == "wild_artidort"


def _normal_card_can_play(game, card_code):
    """
    Normal UNO kartının mevcut renge/sayıya göre oynanıp
    oynanamayacağını kontrol eder.
    """
    top = top_card_from_game(game)
    color = game["top_color"]

    return can_play(card_code, top, color)


def top_card_from_game(game):
    return game["discard"][-1]


def _can_stack_draw_card(game, card_code):
    """
    +2 / +4 zinciri için özel oynama kuralları.

    Kural:
      +2 -> +2 veya +4
      +2 -> +4 mümkündür.

      +4 -> yalnızca bir adet +4 karşılığı mümkündür.

      +4 -> +4 yapıldıktan sonra zincir tekrar +4 alamaz.
    """

    chain = game.get("draw_chain")

    if not chain:
        return False

    if chain == "draw2":
        # +2 üzerine +2 veya +4
        return _is_draw2(card_code) or _is_draw4(card_code)

    if chain == "draw4":
        # +4 üzerine sadece TEK bir +4 karşılığı
        if game.get("draw4_response_used"):
            return False

        return _is_draw4(card_code)

    return False


def legal_cards_for(chat_id, user_id):
    """
    Kullanıcının oynayabileceği kartları döndürür.

    Normal durumda:
      renk veya sembol/sayı eşleşmesi.

    +2 zincirinde:
      sadece +2 veya +4.

    +4 zincirinde:
      sadece bir adet +4.
    """

    game = games[chat_id]

    hand = game["hands"].get(user_id, [])

    if current_player(chat_id) != user_id:
        return []

    chain = game.get("draw_chain")

    if chain:
        return [
            card
            for card in hand
            if _can_stack_draw_card(game, card)
        ]

    top = top_card(chat_id)
    color = game["top_color"]

    return [
        card
        for card in hand
        if can_play(card, top, color)
    ]


def draw_card(chat_id, user_id):
    """
    Normal kart çekme.

    Eğer +2/+4 zinciri aktifse ceza miktarının tamamını çeker.
    """

    game = games[chat_id]

    if current_player(chat_id) != user_id:
        return {
            "ok": False,
            "reason": "SIRA_DEGIL"
        }

    drawn = []

    # +2/+4 cezası varsa cezanın tamamını çek
    pending = game.get("pending_draw", 0)

    if pending > 0:

        for _ in range(pending):
            if not game["deck"]:
                break

            card = game["deck"].pop()
            game["hands"][user_id].append(card)
            drawn.append(card)

        # Zincir sıfırlanır
        game["pending_draw"] = 0
        game["draw_chain"] = None
        game["draw4_response_used"] = False

        game["has_drawn"][user_id] = True

        return {
            "ok": True,
            "drawn": drawn,
            "penalty": pending,
            "stack_broken": True,
        }

    # Normal kart çek
    if game["deck"]:
        card = game["deck"].pop()
        game["hands"][user_id].append(card)
        drawn.append(card)

    game["has_drawn"][user_id] = True

    return {
        "ok": True,
        "drawn": drawn,
        "penalty": 0,
        "stack_broken": False,
    }


def pass_turn(chat_id, user_id):
    """Kart çektikten sonra pas geçer."""
    game = games[chat_id]

    if current_player(chat_id) != user_id:
        return {
            "ok": False,
            "reason": "SIRA_DEGIL"
        }

    if not game["has_drawn"].get(user_id, False):
        return {
            "ok": False,
            "reason": "ONCE_CEK"
        }

    game["has_drawn"][user_id] = False

    _next_turn(chat_id)

    return {
        "ok": True
    }


def play_card(chat_id, user_id, card_code):
    """
    Kart oynar.

    +2 / +4 zinciri burada yönetilir.
    """

    game = games[chat_id]

    if game.get("winner"):
        return {
            "ok": False,
            "reason": "OYUN_BITTI"
        }

    if current_player(chat_id) != user_id:
        return {
            "ok": False,
            "reason": "SIRA_DEGIL"
        }

    hand = game["hands"].get(user_id, [])

    if card_code not in hand:
        return {
            "ok": False,
            "reason": "KART_YOK"
        }

    chain = game.get("draw_chain")

    # -------------------------------------------------
    # +2 / +4 ZİNCİR KONTROLÜ
    # -------------------------------------------------

    if chain:

        if not _can_stack_draw_card(game, card_code):
            return {
                "ok": False,
                "reason": "CEZA_ZINCIRINE_UYGUN_DEGIL"
            }

    else:

        top = top_card(chat_id)
        color = game["top_color"]

        if not can_play(card_code, top, color):
            return {
                "ok": False,
                "reason": "GECERSIZ_HAMLE"
            }

    # Kartı elden çıkar
    hand.remove(card_code)

    game["discard"].append(card_code)

    game["has_drawn"][user_id] = False

    # -------------------------------------------------
    # KART DEĞERLERİ
    # -------------------------------------------------

    is_draw2 = _is_draw2(card_code)
    is_draw4 = _is_draw4(card_code)

    # -------------------------------------------------
    # JOKER
    # -------------------------------------------------

    if card_code.startswith("wild_"):

        game["needs_color"] = True

        # +4
        if is_draw4:

            game["pending_draw"] += 4

            game["draw_chain"] = "draw4"

            # Henüz +4 karşılığı kullanılmadı
            game["draw4_response_used"] = False

        return {
            "ok": True,
            "needs_color": True,
            "remaining": len(hand),
            "effect": "draw4" if is_draw4 else None,
            "draw_chain": game["draw_chain"],
            "pending_draw": game["pending_draw"],
        }

    # Normal kartın rengini güncelle
    game["top_color"] = card_color(card_code)

    # -------------------------------------------------
    # KAZANMA
    # -------------------------------------------------

    if len(hand) == 0:

        game["winner"] = user_id

        return {
            "ok": True,
            "win": True,
            "remaining": 0
        }

    # -------------------------------------------------
    # DUR
    # -------------------------------------------------

    val = _card_value(card_code)

    if val == "dur":

        # Eğer ceza zinciri yoksa normal DUR
        if not game.get("draw_chain"):

            _next_turn(chat_id)

            _next_turn(chat_id)

            return {
                "ok": True,
                "effect": "skip",
                "remaining": len(hand)
            }

    # -------------------------------------------------
    # YÖN
    # -------------------------------------------------

    if val == "yon":

        effect = "reverse"

        game["direction"] *= -1

        # 2 kişilik oyunda YÖN, oyuncuyu tekrar oynatır
        if len(game["players"]) == 2:
            _next_turn(chat_id)

        _next_turn(chat_id)

        return {
            "ok": True,
            "effect": effect,
            "remaining": len(hand)
        }

    # -------------------------------------------------
    # +2
    # -------------------------------------------------

    if is_draw2:

        game["pending_draw"] += 2
        game["draw_chain"] = "draw2"

        # +2 zincirine geçildiğinde +4 hakkı sıfırlanır
        game["draw4_response_used"] = False

        _next_turn(chat_id)

        return {
            "ok": True,
            "effect": "draw2",
            "remaining": len(hand),
            "pending_draw": game["pending_draw"],
            "draw_chain": game["draw_chain"],
        }

    # -------------------------------------------------
    # NORMAL AKIŞ
    # -------------------------------------------------

    _next_turn(chat_id)

    return {
        "ok": True,
        "effect": None,
        "remaining": len(hand)
    }


def choose_color(chat_id, user_id, color):
    """
    Joker sonrası renk seçimi.

    +4 oynandıysa renk seçildikten sonra rakibe geçer.
    Rakip +4 atabilir; fakat +4 üzerine yalnızca bir adet
    +4 karşılığı vardır.
    """

    game = games[chat_id]

    if not game.get("needs_color"):
        return False

    game["top_color"] = color
    game["needs_color"] = False

    last = game["discard"][-1]

    # +4
    if last == "wild_artidort":

        _next_turn(chat_id)

        return True

    # Normal joker
    _next_turn(chat_id)

    return True


def _next_turn(chat_id):
    """Sırayı bir sonraki oyuncuya geçirir."""

    game = games[chat_id]

    n = len(game["players"])

    game["turn"] = (
        game["turn"] + game["direction"]
    ) % n


def end_game(chat_id):
    """Oyunu sonlandırır."""

    if chat_id in games:

        game = games[chat_id]

        for p in game.get("players", []):
            user_active_chat.pop(
                p["id"],
                None
            )

        games.pop(chat_id, None)


def find_active_game_for_user(user_id):
    """Kullanıcının aktif oyununu bulur."""

    chat_id = user_active_chat.get(user_id)

    if chat_id and chat_id in games:
        return chat_id, games[chat_id]

    return None, None
