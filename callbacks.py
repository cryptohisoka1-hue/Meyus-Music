from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import *

async def button(update, context):

    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    # Oyuna katıl
    if query.data == "join":
            elif query.data == "start":

        if chat_id not in games:
            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True
            )
            return

        if len(games[chat_id]["players"]) < 2:
            await query.answer(
                "En az 2 oyuncu gerekli!",
                show_alert=True
            )
            return

        game = start_game(chat_id)

        text = "🎮 <b>Meyus UNO</b>\n\n"
        text += "✅ Oyun başladı!\n\n"
        text += f"👥 Oyuncu Sayısı: {len(game['players'])}\n"
        text += f"🃏 Ortadaki Kart: {game['deck'].pop()}"

        await query.edit_message_text(
            text,
            parse_mode="HTML"
        )

        result = join_game(
            chat_id,
            user.id,
            user.first_name
        )

        if result == "ALREADY_JOINED":
            await query.answer(
                "Zaten oyundasın.",
                show_alert=True
            )
            return

        if result == "NO_GAME":
            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True
            )
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
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
