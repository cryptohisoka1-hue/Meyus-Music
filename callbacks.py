'''from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from game import get_card_display


def make_card_keyboard(hand, chat_id):
    """Oyuncunun elindeki kartlar için inline keyboard oluşturur.
    
    Format: Her satırda 4-5 kart butonu
    En altta: [🃏 Çek] [❓]
    Callback: play:<chat_id>:<index>  veya  draw:<chat_id>
    """
    buttons = []
    for i, card in enumerate(hand):
        text = get_card_display(card)
        # Buton metni çok uzun olmasın
        buttons.append(InlineKeyboardButton(text, callback_data=f"play:{chat_id}:{i}"))
    
    # Her satırda 4 kart
    keyboard = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    
    # Alt satır: Çek ve ? butonları
    keyboard.append([
        InlineKeyboardButton("🃏 Çek", callback_data=f"draw:{chat_id}"),
        InlineKeyboardButton("❓", callback_data=f"help:{chat_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def make_color_keyboard(chat_id):
    """Wild kart atıldığında renk seçim butonları."""
    keyboard = [
        [InlineKeyboardButton("🔴 Kırmızı", callback_data=f"color:{chat_id}:red"),
         InlineKeyboardButton("🔵 Mavi", callback_data=f"color:{chat_id}:blue")],
        [InlineKeyboardButton("🟢 Yeşil", callback_data=f"color:{chat_id}:green"),
         InlineKeyboardButton("🟡 Sarı", callback_data=f"color:{chat_id}:yellow")]
    ]
    return InlineKeyboardMarkup(keyboard)


def game_status_text(game):
    """Oyun durumunu metin olarak döndürür (grup mesajı için)."""
    top_card = game.discard[-1] if game.discard else None
    top_text = get_card_display(top_card) if top_card else "Yok"
    
    current = game.current_player()
    
    color_map = {
        'red': 'Kırmızı',
        'blue': 'Mavi', 
        'green': 'Yeşil',
        'yellow': 'Sarı'
    }
    
    color_text = "Yok"
    if top_card:
        if top_card['color'] == 'wild':
            color_text = color_map.get(game.chosen_color, "Bilinmiyor")
        else:
            color_text = color_map.get(top_card['color'], top_card['color'].capitalize())
    
    return f"Üst:{top_text} Renk:{color_text} Sıra:{current}"


def hand_text(hand):
    """Eli numaralı liste olarak döndürür."""
    parts = []
    for i, card in enumerate(hand, 1):
        parts.append(f"{i}:{get_card_display(card)}")
    return " ".join(parts)
'''

with open('/mnt/agents/output/callbacks.py', 'w', encoding='utf-8') as f:
    f.write(callbacks_content)
print("✅ callbacks.py")
