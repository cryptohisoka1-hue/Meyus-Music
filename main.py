'''import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN
from database import Database
from game import UnoGame
from callbacks import make_card_keyboard, make_color_keyboard, game_status_text

logging.basicConfig(level=logging.INFO)
db = Database()
games = {}          # chat_id -> UnoGame
user_games = {}     # user_id -> chat_id (hangi grupta oynuyor)
waiting_color = {}  # chat_id -> user_id (hangi oyuncu renk seçiyor)


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


def get_player_name(game, user_id):
    return game.player_names.get(str(user_id), "Bilinmiyor")


# ========== KOMUTLAR ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 **Meyus Uno Bot**\n\n"
        "📋 Komutlar:\\n"
        "`/oyun` - Yeni oyun başlat\\n"
        "`/katil` - Oyuna katıl\\n"
        "`/basla` - Oyunu başlat\\n\n"
        "Kartlarınız butonlarla özel mesajda gösterilir."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    game = UnoGame()
    game.players.append(user.id)
    game.player_names = {str(user.id): user.first_name}
    games[chat_id] = game
    user_games[user.id] = chat_id
    save_game(chat_id)
    
    await update.message.reply_text(
        f"🚀 **Yeni oyun oluşturuldu!**\\n"
        f"👤 Başlatan: {user.first_name}\\n"
        f"➡️ Diğer oyuncular `/katil` yazarak katılabilir."
    )


async def katil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        await update.message.reply_text("❌ Önce `/oyun` ile oyun başlat.")
        return
    
    user = update.effective_user
    if user.id not in game.players:
        game.players.append(user.id)
        game.player_names[str(user.id)] = user.first_name
        user_games[user.id] = chat_id
        save_game(chat_id)
        await update.message.reply_text(
            f"✅ **{user.first_name}** oyuna katıldı! ({len(game.players)} oyuncu)"
        )
    else:
        await update.message.reply_text("⚠️ Zaten oyundasın.")


async def basla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        await update.message.reply_text("❌ Önce `/oyun` ile oyun oluştur.")
        return
    if len(game.players) < 2:
        await update.message.reply_text("❌ En az **2 oyuncu** gerekli!")
        return
    if game.started:
        await update.message.reply_text("⚠️ Oyun zaten başladı.")
        return

    game.start()
    save_game(chat_id)

    status = game_status_text(game)
    await update.message.reply_text(f"🚀 **Oyun başladı!**\\n\\n{status}")
    
    # Sıradaki oyuncuya özel mesajla kartlarını gönder
    await send_turn_to_player(context, chat_id)


# ========== OYUN İŞLEMLERİ ==========

async def send_turn_to_player(context, chat_id):
    """Sıradaki oyuncuya özel mesajda kartlarını gönder."""
    game = get_game(chat_id)
    if not game or not game.started:
        return
    
    player_id = game.current_player()
    hand = game.hands.get(player_id, [])
    player_name = get_player_name(game, player_id)
    
    status = game_status_text(game)
    
    try:
        await context.bot.send_message(
            chat_id=player_id,
            text=f"🎮 **Meyus Uno**\\n\\n{status}\\n\\nKartını seç:",
            reply_markup=make_card_keyboard(hand, chat_id)
        )
    except Exception as e:
        # Bot'a önce mesaj atmadıysa hata verir
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ **{player_name}**, önce bana (@{context.bot.username}) özel mesaj atmalısın!"
        )


async def update_group_status(context, chat_id, text):
    """Grup sohbetinde oyun durumunu güncelle."""
    await context.bot.send_message(chat_id=chat_id, text=text)


# ========== CALLBACK HANDLER ==========

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    user_id = user.id
    
    # Callback format: action:chat_id:... 
    parts = data.split(":")
    action = parts[0]
    
    if action == "help":
        await query.edit_message_text(
            "🎮 **Meyus Uno**\\n\\n"
            "Kartlarına basarak oyna.\\n"
            "🃏 Çek = Kart çek\\n"
            "❓ = Yardım\\n\\n"
            "İyi eğlenceler!"
        )
        return
    
    chat_id = int(parts[1])
    game = get_game(chat_id)
    
    if not game or not game.started:
        await query.edit_message_text("❌ Aktif oyun yok.")
        return
    
    # Renk seçimi
    if action == "color":
        await handle_color_choice(query, context, game, chat_id, parts, user_id)
        return
    
    # Sıra kontrolü
    player_id = game.current_player()
    if user_id != player_id:
        await query.answer("⛔ Sıra sende değil!", show_alert=True)
        return
    
    if action == "draw":
        await handle_draw(query, context, game, chat_id, user_id)
    elif action == "play":
        card_idx = int(parts[2])
        await handle_play(query, context, game, chat_id, user_id, card_idx)


async def handle_draw(query, context, game, chat_id, user_id):
    """Kart çekme işlemi."""
    if not game.deck:
        top = game.discard.pop()
        game.deck = game.discard[:]
        random.shuffle(game.deck)
        game.discard = [top]
    
    card = game.deck.pop()
    game.hands[user_id].append(card)
    game.next_turn()
    save_game(chat_id)
    
    player_name = get_player_name(game, user_id)
    status = game_status_text(game)
    
    await query.edit_message_text(
        f"🃏 **{player_name}** kart çekti: {game.card_text(card)}\\n\\n{status}"
    )
    
    await update_group_status(
        context, chat_id,
        f"🃏 **{player_name}** kart çekti.\\n\\n{status}"
    )
    await send_turn_to_player(context, chat_id)


async def handle_play(query, context, game, chat_id, user_id, card_idx):
    """Kart oynama işlemi."""
    hand = game.hands.get(user_id, [])
    if card_idx < 0 or card_idx >= len(hand):
        await query.answer("❌ Geçersiz kart.", show_alert=True)
        return
    
    card = hand[card_idx]
    if not game.can_play(card):
        await query.answer("❌ Bu kart oynanamaz!", show_alert=True)
        return
    
    hand.pop(card_idx)
    game.discard.append(card)
    player_name = get_player_name(game, user_id)
    
    # Wild kart kontrolü
    if card['value'] in ('wild', '+4'):
        waiting_color[chat_id] = user_id
        save_game(chat_id)
        await query.edit_message_text(
            f"🌈 **Wild kart seçtin!** Renk seç:\\n"
            f"Kart: {game.card_text(card)}",
            reply_markup=make_color_keyboard(chat_id)
        )
        await update_group_status(
            context, chat_id,
            f"🌈 **{player_name}** Wild kart oynadı, renk seçiyor..."
        )
        return
    
    # Normal kart efektleri
    msg = f"✅ **{player_name}** kart oynadı: {game.card_text(card)}"
    
    if card['value'] == 'reverse':
        game.direction *= -1
        msg += "\\n🔄 **Yön değişti!**"
    elif card['value'] == 'skip':
        game.next_turn()
        skipped_name = get_player_name(game, game.current_player())
        msg += f"\\n⏭️ **{skipped_name}** atlandı!"
    elif card['value'] == '+2':
        game.next_turn()
        target_id = game.current_player()
        target_name = get_player_name(game, target_id)
        for _ in range(2):
            if game.deck:
                game.hands[target_id].append(game.deck.pop())
        msg += f"\\n➕2️⃣ **{target_name}** 2 kart çekti!"
    
    # Kazanma kontrolü
    if len(hand) == 0:
        await query.edit_message_text(f"🎉 **{player_name}** elini bitirdi!")
        await update_group_status(
            context, chat_id,
            f"🎉🎉🎉 **{player_name} KAZANDI!** 🎉🎉🎉"
        )
        db.delete_state(chat_id)
        games.pop(chat_id, None)
        return
    
    game.next_turn()
    save_game(chat_id)
    
    status = game_status_text(game)
    await query.edit_message_text(f"{msg}\\n\\n{status}")
    await update_group_status(context, chat_id, f"{msg}\\n\\n{status}")
    await send_turn_to_player(context, chat_id)


async def handle_color_choice(query, context, game, chat_id, parts, user_id):
    """Renk seçimi işlemi."""
    if chat_id not in waiting_color or waiting_color[chat_id] != user_id:
        await query.answer("Sıra sende değil.", show_alert=True)
        return
    
    color = parts[2]
    game.chosen_color = color
    del waiting_color[chat_id]
    
    player_name = get_player_name(game, user_id)
    last_card = game.discard[-1]
    msg = f"🌈 **{player_name}** renk seçti: **{color.capitalize()}**"
    
    if last_card['value'] == '+4':
        game.next_turn()
        target_id = game.current_player()
        target_name = get_player_name(game, target_id)
        for _ in range(4):
            if game.deck:
                game.hands[target_id].append(game.deck.pop())
        msg += f"\\n➕4️⃣ **{target_name}** 4 kart çekti!"
    
    # Kazanma kontrolü
    player_hand = game.hands.get(user_id, [])
    if len(player_hand) == 0:
        await query.edit_message_text(f"🎉 **{player_name}** elini bitirdi!")
        await update_group_status(
            context, chat_id,
            f"🎉🎉🎉 **{player_name} KAZANDI!** 🎉🎉🎉"
        )
        db.delete_state(chat_id)
        games.pop(chat_id, None)
        return
    
    game.next_turn()
    save_game(chat_id)
    
    status = game_status_text(game)
    await query.edit_message_text(f"{msg}\\n\\n{status}")
    await update_group_status(context, chat_id, f"{msg}\\n\\n{status}")
    await send_turn_to_player(context, chat_id)


# ========== MAIN ==========

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("❌ Lütfen config.py dosyasına geçerli bir BOT_TOKEN girin!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("oyun", oyun))
    app.add_handler(CommandHandler("katil", katil))
    app.add_handler(CommandHandler("basla", basla))
    
    # Buton callback'leri
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Meyus Uno Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
'''

with open('/mnt/agents/output/main.py', 'w', encoding='utf-8') as f:
    f.write(main_content)
print("✅ main.py")
