import random
from config import COLORS, NUMBER_VALUES, ACTION_VALUES, COLOR_EMOJI, ACTION_EMOJI


def build_deck():
    deck = []
    for c in COLORS:
        deck.append(f"{c}0")
        for v in NUMBER_VALUES[1:]:
            deck += [f"{c}{v}"] * 2
        for v in ACTION_VALUES:
            deck += [f"{c}{v}"] * 2
    deck += ["Wild"] * 4
    deck += ["Wild4"] * 4
    random.shuffle(deck)
    return deck


def card_label(card):
    if card == "Wild":
        return "🌈 Joker"
    if card == "Wild4":
        return "🌈 +4"
    color, val = card[0], card[1:]
    val_disp = ACTION_EMOJI.get(val, val)
    return f"{COLOR_EMOJI[color]}{val_disp}"


class UnoGame:
    def __init__(self, chat_id, host_id):
        self.chat_id = chat_id
        self.host_id = host_id
        self.players = {}       # user_id -> {"name": str, "hand": [card,...]}
        self.order = []         # user_id sırası
        self.turn_index = 0
        self.direction = 1
        self.deck = []
        self.discard = []
        self.current_color = None
        self.theme = "kedi"
        self.state = "lobby"    # lobby | playing | finished
        self.pending_message_id = None  # son gönderilen "sıra kimde" mesajı

    # ---------- Lobi ----------
    def add_player(self, user_id, name):
        if user_id in self.players:
            return False
        self.players[user_id] = {"name": name, "hand": []}
        self.order.append(user_id)
        return True

    def remove_player(self, user_id):
        if user_id in self.players:
            del self.players[user_id]
            self.order.remove(user_id)

    # ---------- Oyunu başlat ----------
    def start(self):
        self.deck = build_deck()
        for uid in self.order:
            self.players[uid]["hand"] = [self.deck.pop() for _ in range(7)]
        # ilk kart joker olmasın diye kontrol
        first = self.deck.pop()
        while first in ("Wild", "Wild4"):
            self.deck.insert(0, first)
            random.shuffle(self.deck)
            first = self.deck.pop()
        self.discard.append(first)
        self.current_color = first[0] if first not in ("Wild", "Wild4") else random.choice(COLORS)
        self.state = "playing"
        self.turn_index = 0

    @property
    def current_player(self):
        return self.order[self.turn_index]

    @property
    def top_card(self):
        return self.discard[-1]

    def next_index(self, steps=1):
        n = len(self.order)
        return (self.turn_index + self.direction * steps) % n

    def advance_turn(self, steps=1):
        self.turn_index = self.next_index(steps)

    # ---------- Oynanabilirlik ----------
    def is_playable(self, card):
        if card in ("Wild", "Wild4"):
            return True
        color, val = card[0], card[1:]
        top = self.top_card
        top_val = None if top in ("Wild", "Wild4") else top[1:]
        if color == self.current_color:
            return True
        if top_val is not None and val == top_val:
            return True
        return False

    # ---------- Kart oyna ----------
    def play_card(self, user_id, card, chosen_color=None):
        if self.state != "playing":
            return False, "Oyun aktif değil."
        if self.current_player != user_id:
            return False, "Sıra sende değil."
        hand = self.players[user_id]["hand"]
        if card not in hand:
            return False, "Bu kart elinde yok."
        if not self.is_playable(card):
            return False, "Bu kartı şu an oynayamazsın."

        hand.remove(card)
        self.discard.append(card)

        if card in ("Wild", "Wild4"):
            self.current_color = chosen_color or random.choice(COLORS)
        else:
            self.current_color = card[0]

        # kazandı mı
        if not hand:
            self.state = "finished"
            return True, "WIN"

        # efekt
        effect = None
        if card.endswith("Skip"):
            self.advance_turn(2)
            effect = "skip"
        elif card.endswith("Reverse"):
            self.direction *= -1
            if len(self.order) == 2:
                self.advance_turn(2)
            else:
                self.advance_turn(1)
            effect = "reverse"
        elif card.endswith("Draw2"):
            self.advance_turn(1)
            victim = self.current_player
            self.draw_cards(victim, 2)
            self.advance_turn(1)
            effect = "draw2"
        elif card == "Wild4":
            self.advance_turn(1)
            victim = self.current_player
            self.draw_cards(victim, 4)
            self.advance_turn(1)
            effect = "wild4"
        else:
            self.advance_turn(1)

        return True, effect

    def draw_cards(self, user_id, n=1):
        drawn = []
        for _ in range(n):
            if not self.deck:
                self.reshuffle_from_discard()
                if not self.deck:
                    break
            drawn.append(self.deck.pop())
        self.players[user_id]["hand"].extend(drawn)
        return drawn

    def reshuffle_from_discard(self):
        if len(self.discard) <= 1:
            return
        top = self.discard.pop()
        self.deck = self.discard[:]
        self.discard = [top]
        random.shuffle(self.deck)

    def draw_for_current(self):
        uid = self.current_player
        drawn = self.draw_cards(uid, 1)
        self.advance_turn(1)
        return drawn
      
