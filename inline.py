from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import get_card_display

def create_hand_keyboard(hand):
    keyboard = 
    for i in range(0, len(hand), 3):
        chunk = hand[i:i+3]
        row = [InlineKeyboardButton(get_card_display(card), callback_data=f"play_{i}") for i, card in enumerate(chunk)]
        # Gerçek uygulamada callback_data'da kartın kendisini veya indeksini göndermek gerekir
        # Basitlik için burada sadece indeks kullanıyoruz, gerçek mantıkta kart objesi de geçilmeli
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🃏 Kart Çek", callback_data="draw_card")])
    return InlineKeyboardMarkup(keyboard)
    
