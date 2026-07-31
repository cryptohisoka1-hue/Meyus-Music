from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import BOT_TOKEN
from database import db


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    db.add_user(
        user.id,
        user.first_name,
        user.username
    )

    text = f"""
🎮 <b>MEYUS UNO</b>

Merhaba <b>{user.first_name}</b> 👋

Meyus UNO'ya hoş geldin.

Bu bot ile arkadaşlarınla tamamen Telegram üzerinden UNO oynayabilirsin.

📌 Komutlar

/start - Botu başlat
/yardim - Yardım
/oyun - Yeni oyun oluştur
/katil - Oyuna katıl
/baslat - Oyunu başlat
/profil - Profilin

İyi eğlenceler ❤️
"""

    await update.message.reply_html(text)


# /yardim
async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
"""
🎮 Yardım

/start
Botu başlatır.

/oyun
Yeni oyun oluşturur.

/katil
Oyuna katılır.

/baslat
Oyunu başlatır.

/profil
Profilini gösterir.
"""
)


def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", yardim))

    print("✅ Meyus UNO çalışıyor...")

    app.run_polling()


if __name__ == "__main__":
    main()
