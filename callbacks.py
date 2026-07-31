from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import *


async def button(update, context):
    query = update.callback_query
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

        await query.answer()

        players = games[chat_id]["players"]
        text = "🎮 <b>Meyus UNO Lobisi</b>\n\n"
        text += f"👥 Oyuncular ({len(players)})\n\n"
        for p in players:
            text += f"• {p['name']}\n"

        keyboard = [
            [InlineKeyboardButton("➕ Katıl", callback_data="join")],
            [InlineKeyboardButton("▶️ Başlat", callback_data="start_game")]
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

        start_game(chat_id)

        keyboard = [[InlineKeyboardButton("🃏 Kartlarımı Gör", callback_data="show_hand")]]
        await query.edit_message_text(
            "🚀 Oyun başladı!\n\n"
            "Kartlarını görmek için aşağıdaki butona bas (sadece sana görünür).",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "show_hand":
        game_info = games.get(chat_id)

        if not game_info or not game_info.get("started"):
            await query.answer("❌ Aktif bir oyun yok.", show_alert=True)
            return

        hand = game_info["hands"].get(user.id)
        if hand is None:
            await query.answer("❌ Bu oyunda değilsin.", show_alert=True)
            return

        text = "🃏 Kartların:\n" + "\n".join(hand)
        await query.answer(text=text[:190], show_alert=True)
        
