import json
import random

COLORS = ["R", "G", "B", "Y"]
COLOR_EMOJI = {"R": "🟥", "G": "🟩", "B": "🟦", "Y": "🟨"}

class UnoGame:
    def __init__(self):
        self.players = []
        self.hands = {}
        self.deck = []
        self.discard = []
        self.turn = 0
        self.direction = 1
        self.chosen_color = None
        self.started = False

    def to_dict(self):
        return {
            "players": self.players,
            "hands": self.hands,
            "deck": self.deck,
            "discard": self.discard,
            "turn": self.turn,
            "direction": self.direction,
            "chosen_color": self.chosen_color,
            "started": self.started,
        }

    @classmethod
    def from_dict(cls, data):
        g = cls()
        g.players = data["players"]
        g.hands = data["hands"]
        g.deck = data["deck"]
        g.discard = data["discard"]
        g.turn = data["turn"]
        g.direction = data["direction"]
        g.chosen_color = data["chosen_color"]
        g.started = data["started"]
        return g

    def serialize(self):
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, raw):
        return cls.from_dict(json.loads(raw))

    def build_deck(self):
        deck = []
        for color in COLORS:
            for n in range(0, 10):
                deck.append(f"{color}{n}")
                if n != 0:
                    deck.append(f"{color}{n}")
            for card in ["SKIP", "REVERSE", "DRAW2"]:
                deck.extend([f"{color}{card}", f"{color}{card}"])
        deck.extend(["WILD"] * 4)
        deck.extend(["WILD4"] * 4)
        random.shuffle(deck)
        return deck

    def start(self):
        self.deck = self.build_deck()
        self.hands = {p: [self.deck.pop() for _ in range(7)] for p in self.players}
        top = self.deck.pop()
        while top in ["WILD", "WILD4"]:
            self.deck.insert(0, top)
            random.shuffle(self.deck)
            top = self.deck.pop()
        self.discard = [top]
        self.turn = 0
        self.direction = 1
        self.chosen_color = None
        self.started = True

    def current_player(self):
        return self.players[self.turn]

    def next_turn(self, step=1):
        self.turn = (self.turn + step * self.direction) % len(self.players)

    def can_play(self, card):
        top = self.discard[-1]
        if card in ["WILD", "WILD4"]:
            return True
        if top in ["WILD", "WILD4"]:
            return card[0] == self.chosen_color
        return card[0] == top[0] or card[1:] == top[1:]

    def card_text(self, card):
        if card.startswith(tuple(COLORS)):
            color = COLOR_EMOJI[card[0]]
            value = card[1:]
            if value.isdigit():
                return f"{color} {value}"
            if value == "SKIP":
                return f"{color} Skip"
            if value == "REVERSE":
                return f"{color} Reverse"
            if value == "DRAW2":
                return f"{color} +2"
        if card == "WILD":
            return "🃏 Wild"
        if card == "WILD4":
            return "🃏 Wild +4"
        return card
