import random

COLORS = ['red', 'blue', 'green', 'yellow']
VALUES = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'skip', 'reverse', '+2']
WILD_VALUES = ['wild', '+4']

def create_deck():
    deck = 
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

def is_valid_move(card, top_card):
    if card['color'] == 'wild' or top_card['color'] == 'wild':
        return True
    if card['color'] == top_card['color']:
        return True
    if card['value'] == top_card['value']:
        return True
    return False
    
