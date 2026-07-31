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
        await query.answer("🚀 Oyun başlatılıyor...")

        await query.edit_message_text(
            "🎮 Oyun başladı! (Test sürümü)"
        )
