from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import UnoGame

def hand_keyboard(hand):
    buttons = [[InlineKeyboardButton(card, callback_data=f"play:{i}")] for i, card in enumerate(hand)]
    buttons.append([InlineKeyboardButton("Kart çek", callback_data="draw")])
    return InlineKeyboardMarkup(buttons)

def render_hand(game: UnoGame, player):
    hand = game.hands[player]
    cards = ", ".join(game.card_text(c) for c in hand)
    top = game.card_text(game.discard[-1])
    return f"Sıra: {player}
Üst kart: {top}
Elin: {cards}"
