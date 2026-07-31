import os
import logging
import uuid
from telegram import (
    Update, 
    InlineQueryResultPhoto, 
    InlineQueryResultArticle, 
    InputTextMessageContent
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler, 
    InlineQueryHandler,
    ContextTypes
)

# Logging ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- AYARLAR ---
# GitHub'a yüklediğiniz kartların klasör yolu
BASE_URL = "https://raw.githubusercontent.com/cryptohisoka1-hue/Meyus-Music/main/uno/cards/"

# --- MÜZİK VE GENEL KOMUTLAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Merhaba! Meyus Bot hazır.\n\n"
        "🃏 UNO oynamak için mesaj alanına @bot_adinizi yazabilirsiniz!"
    )

# --- UNO INLINE MODU ---
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline aramaları yanıtlar."""
    results = []
    
    # Örnek: Kırmızı 0 kartını göster
    results.append(
        InlineQueryResultPhoto(
            id=str(uuid.uuid4()),
            photo_url=f"{BASE_URL}card_000_red_0.png",
            thumbnail_url=f"{BASE_URL}card_000_red_0.png",
            caption="Meyus UNO: Kırmızı 0!",
            title="Kırmızı 0"
        )
    )

    await update.inline_query.answer(results, cache_time=0)

# --- ANA FONKSİYON ---
def main():
    # Railway'de ayarladığınız Token'ı alır
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    
    if not TOKEN:
        logger.error("HATA: TELEGRAM_TOKEN bulunamadı!")
        return

    application = Application.builder().token(TOKEN).build()

    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))

    # Botu çalıştır
    logger.info("Bot başlatılıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
    
