import random
import json

COLORS = ['red', 'blue', 'green', 'yellow']
VALUES = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'skip', 'reverse', '+2']


def create_deck():
    deck = []
    for color in COLORS:
        for value in VALUES:
            deck.append({'color': color, 'value': value})
            if value != '0':
                deck.append({'color': color, 'value': value})
    for _ in range(4):
        deck.append({'color': 'wild', 'value': 'wild'})
        deck.append({'color': 'wild', 'value': '+4'})
    random.shuffle(deck)
    return deck


def get_card_display(card):
    if card['color'] == 'wild':
        return f"🌈 {card['value'].upper()}"
    colors_map = {'red': '🔴', 'blue': '🔵', 'green': '🟢', 'yellow': '🟡'}
    return f"{colors_map[card['color']]} {card['value'].upper()}"


def is_valid_move(card, top_card, chosen_color=None):
    if card['color'] == 'wild':
        return True
    if top_card['color'] == 'wild' and chosen_color:
        if card['color'] == chosen_color:
            return True
    if card['color'] == top_card['color']:
        return True
    if card['value'] == top_card['value']:
        return True
    return False


class UnoGame:
    def __init__(self):
        self.players = []           # user_id listesi
        self.player_names = {}      # {str(user_id): first_name}
        self.deck = create_deck()
        self.discard = []
        self.hands = {}             # {user_id: [kartlar]}
        self.turn = 0
        self.direction = 1
        self.chosen_color = None
        self.started = False

    def start(self):
        self.discard = [self.deck.pop()]
        while self.discard[-1]['color'] == 'wild':
            self.deck.insert(0, self.discard.pop())
            self.discard.append(self.deck.pop())
        for player_id in self.players:
            self.hands[player_id] = [self.deck.pop() for _ in range(7)]
        self.started = True

    def current_player(self):
        if not self.players:
            return None
        return self.players[self.turn % len(self.players)]

    def next_turn(self):
        self.turn = (self.turn + self.direction) % len(self.players)
        self.chosen_color = None

    def can_play(self, card):
        if not self.discard:
            return True
        top = self.discard[-1]
        return is_valid_move(card, top, self.chosen_color)

    def card_text(self, card):
        return get_card_display(card)

    def serialize(self):
        return {
            'players': self.players,
            'player_names': self.player_names,
            'deck': self.deck,
            'discard': self.discard,
            'hands': {str(k): v for k, v in self.hands.items()},
            'turn': self.turn,
            'direction': self.direction,
            'chosen_color': self.chosen_color,
            'started': self.started
        }

    @classmethod
    def deserialize(cls, data):
        game = cls()
        game.players = data['players']
        game.player_names = data.get('player_names', {})
        game.deck = data['deck']
        game.discard = data['discard']
        # hands key'leri string olarak saklandı, int'e çevir
        game.hands = {int(k): v for k, v in data['hands'].items()}
        game.turn = data['turn']
        game.direction = data['direction']
        game.chosen_color = data.get('chosen_color')
        game.started = data.get('started', False)
        return game
'''
