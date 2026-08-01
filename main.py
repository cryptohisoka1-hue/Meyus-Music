'''import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN
from database import Database
from game import UnoGame
from callbacks import hand_keyboard, render_hand

logging.basicConfig(level=logging.INFO)
db = Database()
games = {}


def get_game(chat_id):
    if chat_id in games:
        return games[chat_id]
    raw = db.load_state(chat_id)
    if raw:
        game = UnoGame.deserialize(raw)
        games[chat_id] = game
        return game
    return None


def save_game(chat_id):
    if chat_id in games:
        db.save_state(chat_id, games[chat_id].serialize())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Uno bot hazır. /newgame ile oyun başlat.")


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = UnoGame()
    game.players.append(update.effective_user.first_name)
    games[chat_id] = game
    save_game(chat_id)
    await update.message.reply_text("Yeni oyun oluşturuldu. Diğer oyuncular /join ile katılabilir.")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        await update.message.reply_text("Önce /newgame ile oyun başlat.")
        return
    user = update.effective_user.first_name
    if user not in game.players:
        game.players.append(user)
        save_game(chat_id)
    await update.message.reply_text(f"{user} oyuna katıldı.")


async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        await update.message.reply_text("Önce oyun oluştur.")
        return
    if len(game.players) < 2:
        await update.message.reply_text("En az 2 oyuncu gerekli.")
        return
    game.start()
    save_game(chat_id)
    await update.message.reply_text(f"Oyun başladı. İlk kart: {game.card_text(game.discard[-1])}")
    await send_turn(update, context, chat_id)


async def send_turn(update, context, chat_id):
    game = get_game(chat_id)
    player = game.current_player()
    text = render_hand(game, player)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=hand_keyboard(game.hands[player])
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        await query.edit_message_text("Aktif oyun yok.")
        return

    player = game.current_player()
    user = query.from_user.first_name
    if user != player:
        await query.answer("Sıra sende değil.", show_alert=True)
        return

    if query.data == "draw":
        card = game.deck.pop()
        game.hands[player].append(card)
        game.next_turn()
        save_game(chat_id)
        await query.edit_message_text(f"{player} kart çekti: {game.card_text(card)}")
        await send_turn(update, context, chat_id)
        return

    if query.data.startswith("play:"):
        idx = int(query.data.split(":")[1])
        hand = game.hands[player]
        if idx >= len(hand):
            return
        card = hand[idx]
        if not game.can_play(card):
            await query.answer("Bu kart oynanamaz.", show_alert=True)
            return

        hand.pop(idx)
        game.discard.append(card)

        if card == "REVERSE":
            game.direction *= -1
        elif card == "SKIP":
            game.next_turn()
        elif card == "DRAW2":
            game.next_turn()
            target = game.current_player()
            for _ in range(2):
                game.hands[target].append(game.deck.pop())
        elif card == "WILD":
            game.chosen_color = "R"
        elif card == "WILD4":
            game.chosen_color = "R"
            game.next_turn()
            target = game.current_player()
            for _ in range(4):
                game.hands[target].append(game.deck.pop())

        if len(hand) == 0:
            await query.edit_message_text(f"🎉 {player} kazandı!")
            db.delete_state(chat_id)
            games.pop(chat_id, None)
            return

        game.next_turn()
        save_game(chat_id)
        await query.edit_message_text(f"{player} kart oynadı: {game.card_text(card)}")
        await send_turn(update, context, chat_id)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tanımlı değil.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("begin", begin))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()


if __name__ == "__main__":
    main()
'''

with open('/mnt/agents/output/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Dosya başarıyla oluşturuldu.")
