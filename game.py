import random

from config import (
    COLORS,
    NUMBER_VALUES,
    ACTION_VALUES,
    COLOR_EMOJI,
    ACTION_EMOJI,
)


# ============================================================
# DESTE
# ============================================================

def build_deck():
    """
    Standart 108 kartlık UNO destesi oluşturur.

    Kart örnekleri:
        k0
        k1
        kSkip
        kReverse
        kDraw2
        Wild
        Wild4
    """

    deck = []

    for color in COLORS:
        # 0 kartı 1 adet
        deck.append(f"{color}0")

        # 1-9 kartları 2'şer adet
        for value in NUMBER_VALUES[1:]:
            deck.extend([f"{color}{value}"] * 2)

        # Aksiyon kartları 2'şer adet
        for value in ACTION_VALUES:
            deck.extend([f"{color}{value}"] * 2)

    # 4 Wild
    deck.extend(["Wild"] * 4)

    # 4 Wild +4
    deck.extend(["Wild4"] * 4)

    random.shuffle(deck)
    return deck


# ============================================================
# KART GÖRÜNÜMÜ
# ============================================================

def card_label(card):
    """Kartı Telegram mesajlarında okunabilir hale getirir."""

    if card == "Wild":
        return "🌈 Joker"

    if card == "Wild4":
        return "🌈 +4"

    if not card:
        return "❓"

    color = card[0]
    value = card[1:]

    color_emoji = COLOR_EMOJI.get(color, color)
    value_display = ACTION_EMOJI.get(value, value)

    return f"{color_emoji}{value_display}"


# ============================================================
# UNO GAME
# ============================================================

class UnoGame:

    def __init__(self, chat_id, host_id):
        self.chat_id = chat_id
        self.host_id = host_id

        # user_id ->
        # {
        #     "name": str,
        #     "hand": [...]
        # }
        self.players = {}

        # Oyuncuların sıra listesi
        self.order = []

        # Sıra
        self.turn_index = 0

        # 1 = ileri
        # -1 = geri
        self.direction = 1

        # Kart destesi
        self.deck = []

        # Atılan kartlar
        self.discard = []

        # Aktif renk
        self.current_color = None

        # Tema
        self.theme = "kedi"

        # lobby | playing | finished
        self.state = "lobby"

        # Son sıra mesajı
        self.pending_message_id = None

        # ====================================================
        # ZİNCİR SİSTEMİ
        # ====================================================

        # +2 zincirinde biriken ceza
        self.pending_draw = 0

        # Zincirin türü:
        #
        # None  -> normal oyun
        # draw2 -> +2 zinciri
        # wild4 -> +4 zinciri
        #
        # Özel kural:
        #
        # +2 -> +2 veya +4
        # +4 -> yalnızca +4
        #
        # +4 oynandığında zincir kapanır.
        self.pending_type = None

        # Son oynanan kartın Wild olup olmadığı
        self.waiting_for_color = False

    # ========================================================
    # LOBİ
    # ========================================================

    def add_player(self, user_id, name):
        """Oyuncuyu oyuna ekler."""

        if user_id in self.players:
            return False

        self.players[user_id] = {
            "name": name,
            "hand": [],
        }

        self.order.append(user_id)

        return True

    def remove_player(self, user_id):
        """Oyuncuyu oyundan çıkarır."""

        if user_id not in self.players:
            return False

        del self.players[user_id]

        if user_id in self.order:
            self.order.remove(user_id)

        # Sıra indexini düzelt
        if self.order:
            self.turn_index %= len(self.order)
        else:
            self.turn_index = 0

        return True

    # ========================================================
    # OYUN BAŞLAT
    # ========================================================

    def start(self):
        """Oyunu başlatır."""

        if len(self.order) < 2:
            return False

        self.deck = build_deck()

        self.discard = []

        self.direction = 1
        self.turn_index = 0

        self.pending_draw = 0
        self.pending_type = None
        self.waiting_for_color = False

        # Her oyuncuya 7 kart
        for uid in self.order:
            self.players[uid]["hand"] = [
                self.deck.pop()
                for _ in range(7)
            ]

        # İlk kart
        first = self.deck.pop()

        # İlk kart Wild / Wild4 olmasın
        while first in ("Wild", "Wild4"):
            self.deck.insert(0, first)
            random.shuffle(self.deck)
            first = self.deck.pop()

        self.discard.append(first)

        self.current_color = first[0]

        self.state = "playing"

        return True

    # ========================================================
    # ÖZELLİKLER
    # ========================================================

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

    # ========================================================
    # SIRA
    # ========================================================

    def next_index(self, steps=1):
        if not self.order:
            return 0

        count = len(self.order)

        return (
            self.turn_index
            + self.direction * steps
        ) % count

    def advance_turn(self, steps=1):
        if not self.order:
            return

        self.turn_index = self.next_index(steps)

    # ========================================================
    # KART TİPİ
    # ========================================================

    @staticmethod
    def is_wild(card):
        return card in ("Wild", "Wild4")

    @staticmethod
    def is_wild4(card):
        return card == "Wild4"

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

    # ========================================================
    # ZİNCİRDE KART OYNANABİLİR Mİ?
    # ========================================================

    def can_play_on_draw_chain(self, card):
        """
        Özel +2 / +4 zinciri.

        Kurallar:

        Normal:
            Her uygun kart oynanabilir.

        +2 zinciri:
            +2 oynanabilir.
            +4 oynanabilir.

        +4 zinciri:
            Sadece +4 oynanabilir.
        """

        if self.pending_type == "draw2":

            # +2 üzerine +2
            if self.is_draw2(card):
                return True

            # +2 üzerine +4
            if card == "Wild4":
                return True

            return False

        if self.pending_type == "wild4":

            # +4 üzerine yalnızca +4
            return card == "Wild4"

        return True

    # ========================================================
    # OYNANABİLİRLİK
    # ========================================================

    def is_playable(self, card):
        """
        Kartın mevcut durumda oynanabilir olup olmadığını kontrol eder.
        """

        if self.state != "playing":
            return False

        if card is None:
            return False

        # Zincir varsa özel kurallar
        if self.pending_type is not None:

            if not self.can_play_on_draw_chain(card):
                return False

            return True

        # Normal Wild
        if card == "Wild":
            return True

        # Wild +4
        if card == "Wild4":
            return True

        if not self.discard:
            return True

        color = card[0]
        value = card[1:]

        top = self.top_card

        # Aktif renk
        if color == self.current_color:
            return True

        # Aynı değer / aksiyon
        if top not in ("Wild", "Wild4"):
            top_value = top[1:]

            if value == top_value:
                return True

        return False

    # ========================================================
    # OYNANABİLİR KARTLAR
    # ========================================================

    def playable_cards(self, user_id):
        """
        Oyuncunun oynayabileceği kartları döndürür.
        """

        if user_id not in self.players:
            return []

        if self.current_player != user_id:
            return []

        hand = self.players[user_id]["hand"]

        return [
            card
            for card in hand
            if self.is_playable(card)
        ]

    # ========================================================
    # KART OYNA
    # ========================================================

    def play_card(
        self,
        user_id,
        card,
        chosen_color=None,
    ):
        """
        Kart oynar.

        Dönen değer:

            (False, hata_mesajı)

        veya:

            (True, efekt)
        """

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

        # ----------------------------------------------------
        # WILD RENK KONTROLÜ
        # ----------------------------------------------------

        if card in ("Wild", "Wild4"):

            if chosen_color is not None:
                if chosen_color not in COLORS:
                    return False, "Geçersiz renk."

        # ----------------------------------------------------
        # KARTI ELİNDEN ÇIKAR
        # ----------------------------------------------------

        hand.remove(card)

        self.discard.append(card)

        # ----------------------------------------------------
        # RENK
        # ----------------------------------------------------

        if card in ("Wild", "Wild4"):

            if chosen_color:
                self.current_color = chosen_color
            else:
                self.current_color = random.choice(COLORS)

        else:
            self.current_color = card[0]

        # ----------------------------------------------------
        # KAZANMA
        # ----------------------------------------------------

        if not hand:

            self.state = "finished"

            self.pending_draw = 0
            self.pending_type = None

            return True, "WIN"

        # ----------------------------------------------------
        # +2
        # ----------------------------------------------------

        if self.is_draw2(card):

            # +2 zinciri başlat / devam ettir
            self.pending_type = "draw2"
            self.pending_draw += 2

            # Sırayı cezalı oyuncuya geçir.
            self.advance_turn(1)

            return True, "draw2"

        # ----------------------------------------------------
        # +4
        # ----------------------------------------------------

        if card == "Wild4":

            # Özel kural:
            #
            # +2 -> +4 mümkün.
            #
            # Ancak +4 atıldıktan sonra zincir kapanır.
            #
            # Bir sonraki oyuncu 4 kart çeker.
            # Sonrasında sıra diğer oyuncuya geçer.

            victim = self.next_index(1)

            # Önce kurbanı belirle
            self.turn_index = victim

            victim_uid = self.current_player

            self.draw_cards(victim_uid, 4)

            # +4 zinciri tamamen kapat
            self.pending_draw = 0
            self.pending_type = None

            # Cezalı oyuncunun sırasını geçir
            self.advance_turn(1)

            return True, "wild4"

        # ----------------------------------------------------
        # NORMAL KART OYNANIYORSA ZİNCİR YOK
        # ----------------------------------------------------

        self.pending_draw = 0
        self.pending_type = None

        # ----------------------------------------------------
        # SKIP
        # ----------------------------------------------------

        if self.is_skip(card):

            # 2 kişilik oyunda zaten diğer oyuncunun
            # sırası atlanmış olur.
            self.advance_turn(2)

            return True, "skip"

        # ----------------------------------------------------
        # REVERSE
        # ----------------------------------------------------

        if self.is_reverse(card):

            self.direction *= -1

            # 2 kişilik UNO'da Reverse = Skip
            if len(self.order) == 2:
                self.advance_turn(2)
            else:
                self.advance_turn(1)

            return True, "reverse"

        # ----------------------------------------------------
        # NORMAL KART
        # ----------------------------------------------------

        self.advance_turn(1)

        return True, None

    # ========================================================
    # KART ÇEK
    # ========================================================

    def draw_cards(self, user_id, n=1):
        """
        Belirtilen oyuncuya kart verir.
        """

        if user_id not in self.players:
            return []

        drawn = []

        for _ in range(max(0, n)):

            if not self.deck:

                self.reshuffle_from_discard()

            if not self.deck:
                break

            drawn.append(self.deck.pop())

        self.players[user_id]["hand"].extend(drawn)

        return drawn

    # ========================================================
    # DESTEDEN 1 KART ÇEK
    # ========================================================

    def draw_one(self, user_id):
        return self.draw_cards(user_id, 1)

    # ========================================================
    # NORMAL SIRA KART ÇEKME
    # ========================================================

    def draw_for_current(self):
        """
        Normal durumda sıradaki oyuncu 1 kart çeker
        ve sırası geçer.

        Ancak +2 zinciri varsa ceza miktarını çeker.
        """

        if self.state != "playing":
            return []

        uid = self.current_player

        # ----------------------------------------------------
        # +2 ZİNCİRİ
        # ----------------------------------------------------

        if self.pending_type == "draw2":

            amount = self.pending_draw

            drawn = self.draw_cards(uid, amount)

            # Zincir kapanır
            self.pending_draw = 0
            self.pending_type = None

            # Sıra geçer
            self.advance_turn(1)

            return drawn

        # ----------------------------------------------------
        # +4 zinciri normalde burada bulunmaz.
        # Çünkü +4 oynandığında kartlar zaten çekilir.
        # ----------------------------------------------------

        if self.pending_type == "wild4":

            drawn = self.draw_cards(uid, 4)

            self.pending_draw = 0
            self.pending_type = None

            self.advance_turn(1)

            return drawn

        # ----------------------------------------------------
        # NORMAL ÇEK
        # ----------------------------------------------------

        drawn = self.draw_cards(uid, 1)

        self.advance_turn(1)

        return drawn

    # ========================================================
    # ZİNCİRİ ÇEKEREK KAPAT
    # ========================================================

    def draw_penalty(self):
        """
        Aktif oyuncunun mevcut cezasını çeker.

        +2 zinciri için kullanılır.
        """

        uid = self.current_player

        if self.pending_type == "draw2":
            amount = self.pending_draw

            drawn = self.draw_cards(uid, amount)

            self.pending_draw = 0
            self.pending_type = None

            self.advance_turn(1)

            return drawn

        if self.pending_type == "wild4":
            drawn = self.draw_cards(uid, 4)

            self.pending_draw = 0
            self.pending_type = None

            self.advance_turn(1)

            return drawn

        return self.draw_for_current()

    # ========================================================
    # DESTEYİ YENİLE
    # ========================================================

    def reshuffle_from_discard(self):
        """
        Atılan kartları yeniden deste haline getirir.

        En üstteki kart korunur.
        """

        if len(self.discard) <= 1:
            return

        top = self.discard.pop()

        self.deck = self.discard[:]

        self.discard = [top]

        random.shuffle(self.deck)

    # ========================================================
    # OYUNCU ELİ
    # ========================================================

    def get_hand(self, user_id):
        if user_id not in self.players:
            return []

        return list(
            self.players[user_id]["hand"]
        )

    # ========================================================
    # OYUNCU ADI
    # ========================================================

    def get_player_name(self, user_id):
        player = self.players.get(user_id)

        if not player:
            return "Bilinmeyen oyuncu"

        return player["name"]

    # ========================================================
    # OYUNCU SAYISI
    # ========================================================

    @property
    def player_count(self):
        return len(self.order)

    # ========================================================
    # KART SAYISI
    # ========================================================

    def card_count(self, user_id):
        if user_id not in self.players:
            return 0

        return len(
            self.players[user_id]["hand"]
        )

    # ========================================================
    # OYUN BİTTİ Mİ?
    # ========================================================

    @property
    def finished(self):
        return self.state == "finished"

    # ========================================================
    # ZİNCİR BİLGİSİ
    # ========================================================

    def chain_info(self):
        """
        Telegram arayüzünde zincir bilgisini göstermek
        için kullanılabilir.
        """

        if self.pending_type == "draw2":
            return {
                "type": "draw2",
                "amount": self.pending_draw,
                "allowed": ["Draw2", "Wild4"],
            }

        if self.pending_type == "wild4":
            return {
                "type": "wild4",
                "amount": 4,
                "allowed": ["Wild4"],
            }

        return {
            "type": None,
            "amount": 0,
            "allowed": [],
        }
