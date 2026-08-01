from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_game, save_game
import random

async def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    game = get_game(chat_id)
    if not game:
        await query.answer("Oyun bulunamadı.")
        return

    if data == "join_game":
        if any(p["id"] == user_id for p in game["players"]):
            await query.answer("Zaten oyundasınız.")
            return
        
        if len(game["players"]) >= 4:
            await query.answer("Oyun dolu.")
            return
            
        game["players"].append({
            "id": user_id,
            "name": query.from_user.first_name,
            "hand": []
        })
        save_game(game)
        await query.answer("Oyuna katıldınız!")
        # Mesajı güncelle...
