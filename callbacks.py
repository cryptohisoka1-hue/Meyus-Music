from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import *

async def button(update, context):

    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    if query.data == "join":

        result = join_game(chat_id, user.id, user.first_name)

        if result == "ALREADY_JOINED":
            await query.answer("Zaten oyundasın.", show_alert=True)
            return

        if result == "NO_GAME":
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return

        players = games[chat_id]["players"]

        text = "🎮 <b>Meyus UNO Lobisi</b>\n\n"
        text += f"👥 Oyuncular ({len(players)})\n\n"

        for p in players:
            text += f"• {p['name']}\n"

        keyboard = [
            [InlineKeyboardButton("➕ Katıl", callback_data="join")],
            [InlineKeyboardButton("▶️ Başlat", callback_data="start")]
        ]

        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "start_game":
    game_info = games.get(chat_id)

    if not game_info:
        await query.answer("❌ Oyun bulunamadı.", show_alert=True)
        return

    if user.id != game_info["owner"]:
        await query.answer("❌ Sadece oyunu kuran kişi başlatabilir.", show_alert=True)
        return

    if len(game_info["players"]) < 2:
        await query.answer("En az 2 oyuncu gerekli.", show_alert=True)
        return

    await query.answer("🚀 Oyun başlatılıyor...")

    game = start_game(chat_id)

    await query.edit_message_text("🚀 Oyun başladı!")

    failed_players = []
    for player in game["players"]:
        cards = "\n".join(game["hands"][player["id"]])
        try:
            await context.bot.send_message(
                player["id"],
                f"🃏 Kartların:\n\n{cards}"
            )
        except Exception:
            failed_players.append(player["name"])

    if failed_players:
        names = ", ".join(failed_players)
        await context.bot.send_message(
            chat_id,
            f"⚠️ Şu oyunculara özelden mesaj gönderilemedi (önce botu özelden başlatmaları lazım):\n{names}\n\n"
            f"https://t.me/{context.bot.username}"
        )
