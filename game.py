import random

from config import (
    COLORS,
    NUMBER_VALUES,
    ACTION_VALUES,
    COLOR_EMOJI,
    ACTION_EMOJI,
)


def build_deck():
    deck = []

    for color in COLORS:
        deck.append(f"{color}0")

        for value in NUMBER_VALUES[1:]:
            deck.extend([f"{color}{value}"] * 2)

        for value in ACTION_VALUES:
            deck.extend([f"{color}{value}"] * 2)

    deck.extend(["Wild"] * 4)
    deck.extend(["Wild4"] * 4)

    random.shuffle(deck)
    return deck


def card_label(card):
    if card == "Wild":
        return "🌈 Joker"

    if card == "Wild4":
        return "🌈 +4"

    if not card:
        return "❓"

    color = card[0]
    value = card[1:]

    return (
        f"{COLOR_EMOJI.get(color, color)}"
        f"{ACTION_EMOJI.get(value, value)}"
    )


class UnoGame:

    def __init__(self, chat_id, host_id):
        self.chat_id = chat_id
        self.host_id = host_id

        self.players = {}
        self.order = []

        self.turn_index = 0
        self.direction = 1

        self.deck = []
        self.discard = []

        self.current_color = None

        self.theme = "kedi"

        self.state = "lobby"

        self.pending_message_id = None

        # +2 zinciri
        self.pending_draw = 0
        self.pending_type = None

    # =========================================================
    # LOBİ
    # =========================================================

    def add_player(self, user_id, name):
        if user_id in self.players:
            return False

        self.players[user_id] = {
            "name": name,
            "hand": [],
        }

        self.order.append(user_id)

        return True

    def remove_player(self, user_id):
        if user_id not in self.players:
            return False

        del self.players[user_id]

        if user_id in self.order:
            self.order.remove(user_id)

        if self.order:
            self.turn_index %= len(self.order)
        else:
            self.turn_index = 0

        return True

    # =========================================================
    # OYUNU BAŞLAT
    # =========================================================

    def start(self):
        if len(self.order) < 2:
            return False

        self.deck = build_deck()
        self.discard = []

        self.turn_index = 0
        self.direction = 1

        self.pending_draw = 0
        self.pending_type = None

        for uid in self.order:
            self.players[uid]["hand"] = [
                self.deck.pop()
                for _ in range(7)
            ]

        # İlk kart Wild veya Wild4 olmasın.
        first = self.deck.pop()

        while first in ("Wild", "Wild4"):
            self.deck.insert(0, first)
            random.shuffle(self.deck)
            first = self.deck.pop()

        self.discard.append(first)
        self.current_color = first[0]

        self.state = "playing"

        return True

    # =========================================================
    # PROPERTIES
    # =========================================================

    @property
    def current_player(self):
        if not self.order:
            return None

        return self.order[self.turn_index]

    @property
    def top_card(self):
        if not self.discard:
            return None

        return self.discard[-1]

    # =========================================================
    # SIRA
    # =========================================================

    def next_index(self, steps=1):
        if not self.order:
            return 0

        return (
            self.turn_index
            + self.direction * steps
        ) % len(self.order)

    def advance_turn(self, steps=1):
        if not self.order:
            return

        self.turn_index = self.next_index(steps)

    # =========================================================
    # KART TİPLERİ
    # =========================================================

    @staticmethod
    def is_draw2(card):
        return (
            isinstance(card, str)
            and card.endswith("Draw2")
        )

    @staticmethod
    def is_skip(card):
        return (
            isinstance(card, str)
            and card.endswith("Skip")
        )

    @staticmethod
    def is_reverse(card):
        return (
            isinstance(card, str)
            and card.endswith("Reverse")
        )

    # =========================================================
    # ZİNCİR
    # =========================================================

    def can_play_on_chain(self, card):
        if self.pending_type == "draw2":
            # +2 üzerine +2
            if self.is_draw2(card):
                return True

            # +2 üzerine +4
            if card == "Wild4":
                return True

            return False

        # +4 zinciri tutulmuyor.
        # Wild4 oynandığında doğrudan 4 kart çektiriliyor.
        if self.pending_type == "wild4":
            return False

        return True

    # =========================================================
    # OYNANABİLİRLİK
    # =========================================================

    def is_playable(self, card):

        if self.state != "playing":
            return False

        if card is None:
            return False

        # +2 zinciri
        if self.pending_type == "draw2":
            return self.can_play_on_chain(card)

        # Normal Wild
        if card == "Wild":
            return True

        # +4 normal durumda oynanabilir
        if card == "Wild4":
            return True

        if not self.discard:
            return True

        color = card[0]
        value = card[1:]

        top = self.top_card

        # Aynı renk
        if color == self.current_color:
            return True

        # Aynı değer / aksiyon
        if top not in ("Wild", "Wild4"):
            if value == top[1:]:
                return True

        return False

    # =========================================================
    # OYNANABİLİR KARTLAR
    # =========================================================

    def playable_cards(self, user_id):
        if user_id not in self.players:
            return []

        if self.current_player != user_id:
            return []

        return [
            card
            for card in self.players[user_id]["hand"]
            if self.is_playable(card)
        ]

    # =========================================================
    # KART OYNA
    # =========================================================

    def play_card(
        self,
        user_id,
        card,
        chosen_color=None,
    ):
        if self.state != "playing":
            return False, "Oyun aktif değil."

        if user_id not in self.players:
            return False, "Oyuncu oyunda değil."

        if self.current_player != user_id:
            return False, "Sıra sende değil."

        hand = self.players[user_id]["hand"]

        if card not in hand:
            return False, "Bu kart elinde yok."

        if not self.is_playable(card):
            return False, "Bu kartı şu an oynayamazsın."

        # Wild renk kontrolü
        if card in ("Wild", "Wild4"):
            if chosen_color is not None and chosen_color not in COLORS:
                return False, "Geçersiz renk."

        # Kartı elden çıkar
        hand.remove(card)
        self.discard.append(card)

        # Renk
        if card in ("Wild", "Wild4"):
            if chosen_color:
                self.current_color = chosen_color
            else:
                self.current_color = random.choice(COLORS)
        else:
            self.current_color = card[0]

        # Kazandı
        if not hand:
            self.state = "finished"
            self.pending_draw = 0
            self.pending_type = None
            return True, "WIN"

        # =====================================================
        # +2
        # =====================================================

        if self.is_draw2(card):

            self.pending_type = "draw2"
            self.pending_draw += 2

            # Ceza sıradaki oyuncuda.
            self.advance_turn(1)

            return True, "draw2"

        # =====================================================
        # +4
        # =====================================================

        if card == "Wild4":

            # +2 zincirinden +4 gelebilir.
            #
            # +4 geldiği anda zincir kapanır.
            # Sonraki oyuncu 4 kart çeker.
            # Sonra sıra geçer.

            self.advance_turn(1)

            victim = self.current_player

            self.draw_cards(victim, 4)

            self.pending_draw = 0
            self.pending_type = None

            self.advance_turn(1)

            return True, "wild4"

        # Normal kart
        self.pending_draw = 0
        self.pending_type = None

        # =====================================================
        # SKIP
        # =====================================================

        if self.is_skip(card):
            self.advance_turn(2)
            return True, "skip"

        # =====================================================
        # REVERSE
        # =====================================================

        if self.is_reverse(card):

            self.direction *= -1

            # 2 kişide Reverse = Skip
            if len(self.order) == 2:
                self.advance_turn(2)
            else:
                self.advance_turn(1)

            return True, "reverse"

        # =====================================================
        # NORMAL
        # =====================================================

        self.advance_turn(1)

        return True, None

    # =========================================================
    # KART ÇEK
    # =========================================================

    def draw_cards(self, user_id, amount=1):

        if user_id not in self.players:
            return []

        drawn = []

        for _ in range(max(0, amount)):

            if not self.deck:
                self.reshuffle_from_discard()

            if not self.deck:
                break

            drawn.append(self.deck.pop())

        self.players[user_id]["hand"].extend(drawn)

        return drawn

    # =========================================================
    # NORMAL / CEZALI ÇEKME
    # =========================================================

    def draw_for_current(self):

        if self.state != "playing":
            return []

        uid = self.current_player

        # +2 zinciri
        if self.pending_type == "draw2":

            amount = self.pending_draw

            drawn = self.draw_cards(uid, amount)

            self.pending_draw = 0
            self.pending_type = None

            self.advance_turn(1)

            return drawn

        # Normal
        drawn = self.draw_cards(uid, 1)

        self.advance_turn(1)

        return drawn

    # =========================================================
    # DESTE YENİLE
    # =========================================================

    def reshuffle_from_discard(self):

        if len(self.discard) <= 1:
            return

        top = self.discard.pop()

        self.deck = self.discard[:]

        self.discard = [top]

        random.shuffle(self.deck)

    # =========================================================
    # EL
    # =========================================================

    def get_hand(self, user_id):
        if user_id not in self.players:
            return []

        return list(self.players[user_id]["hand"])

    def card_count(self, user_id):
        if user_id not in self.players:
            return 0

        return len(self.players[user_id]["hand"])
