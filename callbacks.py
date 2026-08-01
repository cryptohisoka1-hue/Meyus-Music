from telegram import Update
from telegram.ext import ContextTypes
import json
from database import get_player_hand, add_player, save_game
from game import is_valid_move, get_card_display

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game_id = str(chat_id)
    
    # Oyunu başlat
    deck = create_deck()
    discard = [deck.pop()]
    players = {}
    
    # Herkes için kart dağıt (örnek: 7 kart)
    for member in await context.bot.get_chat_member(chat_id, update.effective_user.id):
        pass # Basitlik için tek oyunculu simülasyon
    
    player_hand = [deck.pop() for _ in range(7)]
    await add_player(update.effective_user.id, game_id, player_hand)
    
    game_data = {
        'deck': json.dumps([c for c in deck]),
        'discard': json.dumps(discard),
        'turn': 0,
        'direction': 1,
        'players': {update.effective_user.id: player_hand}
    }
    await save_game(game_id, game_data)
    
    await update.message.reply_text(f"Oyun başladı! Sıra sizde.\n\n{get_card_display(discard)} üstte yatıyor.")

async def play_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if "play_" in query.data:
        # Kart oynama mantığı burada devreye girer
        await query.edit_message_text("Kartınız kontrol ediliyor...")
        # Gerçek uygulamada kartı seçip oyun mantığını tetiklersiniz
        
