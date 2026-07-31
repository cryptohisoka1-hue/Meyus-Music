# callbacks.py
from telegram import CallbackQuery
from telegram.ext import ContextTypes
from main import show_hand  # <-- Bunu ekle (main.py'deki fonksiyonu buraya çağırıyoruz)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "show_hand":
        # Butona basıldığında main.py'deki show_hand fonksiyonunu çalıştır
        await show_hand(query, context)
        
    elif data == "join":
        # ... mevcut katılma kodunuz ...
        pass
        
    elif data == "start_game":
        # ... mevcut başlatma kodunuz ...
        pass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import *


def _basladi_mesaji(chat_id):
    game = games[chat_id]
    top = game["discard"][-1]
    color_name = COLOR_NAMES.get(game["current_color"], game["current_color"])
    turn_name = get_player_name(chat_id, game["turn_order"][game["turn_index"]])
    return (
        "🚀 Oyun başladı!\n\n"
        f"Üst kart: {top}   Renk: {color_name}\n"
        f"▶️ Sıra: {turn_name}\n\n"
        "Kartlarını görmek için aşağıdaki butona bas (sadece sana görünür).\n"
        "Kart atmak için: /at <numara>\n"
        "Çekmek/pas geçmek için: /cek"
    )


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
            _basladi_mesaji(chat_id),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "show_hand":
        text = hand_alert_text(chat_id, user.id)

        if text is None:
            await query.answer("❌ Aktif bir oyun yok ya da bu oyunda değilsin.", show_alert=True)
            return

        await query.answer(text=text[:190], show_alert=True)
        
