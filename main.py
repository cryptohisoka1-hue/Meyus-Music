import logging
from collections import defaultdict
from random import shuffle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "YOUR_BOT_TOKEN"

logging.basicConfig(level=logging.INFO)

games = {}

COLORS = ["R", "G", "B", "Y"]
COLOR_EMOJI = {"R": "🟥", "G": "🟩", "B": "🟦", "Y": "🟨"}

def build_deck():
    deck = []
    for color in COLORS:
        for n in range(0, 10):
            deck.append(f"{color}{n}")
            if n != 0:
                deck.append(f"{color}{n}")
        for card in ["SKIP", "REVERSE", "DRAW2"]:
            deck.extend([f"{color}{card}", f"{color}{card}"])
    wilds = ["WILD", "WILD4"]
    for w in wilds:
        deck.extend([w] * 4)
    shuffle(deck)
    return deck

def card_text(card):
    if card.startswith(tuple(COLORS)):
        color = card[0]
        value = card[1:]
        if value.isdigit():
            return f"{COLOR_EMOJI[color]} {value}"
        if value == "SKIP":
            return f"{COLOR_EMOJI[color]} Skip"
        if value == "REVERSE":
            return f"{COLOR_EMOJI[color]} Reverse"
        if value == "DRAW2":
            return f"{COLOR_EMOJI[color]} +2"
    if card == "WILD":
        return "🃏 Wild"
    if card == "WILD4":
        return "🃏 Wild +4"
    return card

def can_play(card, top_card, chosen_color=None):
    if card in ["WILD", "WILD4"]:
        return True
    if top_card in ["WILD", "WILD4"]:
        return card[0] == chosen_color
    return card[0] == top_card[0] or card[1:] == top_card[1:]

def init_game(chat_id, players):
    deck = build_deck()
    hands = {p: [deck.pop() for _ in range(7)] for p in players}
    top = deck.pop()
    while top in ["WILD", "WILD4"]:
        deck.insert(0, top)
        shuffle(deck)
        top = deck.pop()
    games[chat_id] = {
        "players": players,
        "hands": hands,
        "deck": deck,
        "discard": [top],
        "turn": 0,
        "direction": 1,
        "chosen_color": None,
        "started": True
    }

def current_player(game):
    return game["players"][game["turn"]]

def next_turn(game, step=1):
    game["turn"] = (game["turn"] + step * game["direction"]) % len(game["players"])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Uno bot hazır. /newgame ile oyun başlat.")

async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    games[chat_id] = {
        "players": [user],
        "hands": defaultdict(list),
        "deck": [],
        "discard": [],
        "turn": 0,
        "direction": 1,
        "chosen_color": None,
        "started": False
    }
    await update.message.reply_text(
        "Yeni oyun oluşturuldu. Oyuncuları eklemek için /join kullan. Başlatmak için /begin."
    )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user.first_name
    if chat_id not in games:
        await update.message.reply_text("Önce /newgame ile oyun başlat.")
        return
    game = games[chat_id]
    if user not in game["players"]:
        game["players"].append(user)
    await update.message.reply_text(f"{user} oyuna katıldı.")

async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("Önce /newgame ile oyun başlat.")
        return
    game = games[chat_id]
    if len(game["players"]) < 2:
        await update.message.reply_text("En az 2 oyuncu gerekir.")
        return
    init_game(chat_id, game["players"])
    await update.message.reply_text(f"Oyun başladı. İlk kart: {card_text(games[chat_id]['discard'][-1])}")
    await send_hand(context, chat_id, current_player(games[chat_id]))

async def send_hand(context, chat_id, player):
    game = games[chat_id]
    hand = game["hands"][player]
    buttons = []
    for i, card in enumerate(hand):
        buttons.append([InlineKeyboardButton(card_text(card), callback_data=f"play:{i}")])
    buttons.append([InlineKeyboardButton("Kart çek", callback_data="draw")])
    text = f"Sıra: {player}
Üst kart: {card_text(game['discard'][-1])}
Elin: " + ", ".join(card_text(c) for c in hand)
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await query.edit_message_text("Aktif oyun yok.")
        return
    game = games[chat_id]
    player = current_player(game)
    user = query.from_user.first_name
    if user != player:
        await query.answer("Sıra sende değil.", show_alert=True)
        return

    data = query.data
    if data == "draw":
        card = game["deck"].pop()
        game["hands"][player].append(card)
        next_turn(game)
        await query.edit_message_text(f"{player} kart çekti: {card_text(card)}")
        await send_hand(context, chat_id, current_player(game))
        return

    if data.startswith("play:"):
        idx = int(data.split(":")[1])
        hand = game["hands"][player]
        if idx >= len(hand):
            return
        card = hand[idx]
        top = game["discard"][-1]
        if not can_play(card, top, game["chosen_color"]):
            await query.answer("Bu kart oynanamaz.", show_alert=True)
            return
        hand.pop(idx)
        game["discard"].append(card)
        game["chosen_color"] = None

        if card == "REVERSE":
            game["direction"] *= -1
        elif card == "SKIP":
            next_turn(game)
        elif card == "DRAW2":
            next_turn(game)
            target = current_player(game)
            for _ in range(2):
                game["hands"][target].append(game["deck"].pop())
        elif card == "WILD":
            game["chosen_color"] = "R"
        elif card == "WILD4":
            game["chosen_color"] = "R"
            next_turn(game)
            target = current_player(game)
            for _ in range(4):
                game["hands"][target].append(game["deck"].pop())

        if len(hand) == 0:
            await query.edit_message_text(f"🎉 {player} kazandı!")
            del games[chat_id]
            return

        next_turn(game)
        await query.edit_message_text(f"{player} kart oynadı: {card_text(card)}")
        await send_hand(context, chat_id, current_player(game))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_han
