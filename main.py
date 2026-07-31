from game import *
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
# /oyun
async def oyun(update, context):

    chat = update.effective_chat

    ok = create_game(chat.id, update.effective_user.id)

    if not ok:
        await update.message.reply_text(
            "❌ Bu grupta zaten açık bir oyun var."
        )
        return

    join_game(
        chat.id,
        update.effective_user.id,
        update.effective_user.first_name
    )

    await update.message.reply_text(
        "🎮 Meyus UNO oluşturuldu.\n\n"
        "Katılmak için:\n"
        "/katil"
    )

# /katil
async def katil(update, context):

    ok = join_game(
        update.effective_chat.id,
        update.effective_user.id,
        update.effective_user.first_name
    )

    if not ok:
        await update.message.reply_text(
            "Oyuna katılamadın."
        )
        return

    oyuncu = len(
        games[update.effective_chat.id]["players"]
    )

    await update.message.reply_text(
        f"✅ {update.effective_user.first_name} katıldı.\n\n"
        f"Toplam oyuncu: {oyuncu}"
    )

# /baslat
async def baslat(update, context):

    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text(
            "Önce /oyun oluştur."
        )
        return

    if len(games[chat_id]["players"]) < 2:
        await update.message.reply_text(
            "En az 2 oyuncu gerekli."
        )
        return

    game = start_game(chat_id)

    await update.message.reply_text(
        "🚀 Oyun başladı!"
    )

    for player in game["players"]:

        cards = "\n".join(
            game["hands"][player["id"]]
        )

        try:
            await context.bot.send_message(
                player["id"],
                f"🃏 Kartların:\n\n{cards}"
            )
        except:
            pass

# /profil
async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = db.get_user(update.effective_user.id)

    if not user:
        await update.message.reply_text("Önce /start kullan.")
        return

    await update.message.reply_text(
        f"""👤 Profil

🪙 Coin: {user[3]}
🏆 Galibiyet: {user[4]}
🎮 Oyun: {user[5]}
⭐ Seviye: {user[6]}
✨ XP: {user[7]}
"""
    )
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
    app.add_handler(CommandHandler("oyun", oyun))
    app.add_handler(CommandHandler("katil", katil))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("profil", profil))

    print("✅ Meyus UNO çalışıyor...")

    app.run_polling()


if __name__ == "__main__":
    main()
