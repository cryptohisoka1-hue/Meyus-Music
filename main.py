from game import *
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from callbacks import button
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

    # Gruptaki "Katıl" deep-link butonundan geldiyse
    if context.args and context.args[0].startswith("join_"):
        chat_id = int(context.args[0].split("_")[1])
        result = join_game(chat_id, user.id, user.first_name)

        if result == "NO_GAME":
            await update.message.reply_text("❌ Bu oyun artık mevcut değil.")
            return

        if result == "ALREADY_JOINED":
            await update.message.reply_text("ℹ️ Zaten bu oyuna katıldın.")
        else:
            await update.message.reply_text(
                "✅ Oyuna katıldın! Oyun başlayınca kartların buradan (özelden) gelecek."
            )

        # Grup lobisindeki mesajı güncelle
        players = games[chat_id]["players"]
        text = "🎮 <b>Meyus UNO Lobisi</b>\n\n"
        text += f"👥 Oyuncular ({len(players)})\n\n"
        for p in players:
            text += f"• {p['name']}\n"

        group_keyboard = [
            [InlineKeyboardButton(
                "➕ Katıl",
                url=f"https://t.me/{context.bot.username}?start=join_{chat_id}"
            )],
            [InlineKeyboardButton("▶️ Başlat", callback_data="start_game")]
        ]

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=lobby_messages[chat_id],
                text=text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(group_keyboard)
            )
        except Exception:
            pass
        return

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
/bitir - Oyunu bitir
/profil - Profilin

İyi eğlenceler ❤️
"""
    await update.message.reply_html(text)


# /oyun
async def oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not create_game(chat.id, user.id):
        await update.message.reply_text(
            "❌ Bu grupta zaten açık bir oyun var."
        )
        return

    join_game(chat.id, user.id, user.first_name)

    keyboard = [
        [InlineKeyboardButton(
            "➕ Katıl",
            url=f"https://t.me/{context.bot.username}?start=join_{chat.id}"
        )],
        [InlineKeyboardButton("▶️ Başlat", callback_data="start_game")]
    ]

    msg = await update.message.reply_text(
        "🎮 <b>Meyus UNO Lobisi</b>\n\n"
        f"👤 Oyuncular (1)\n"
        f"• {user.first_name}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    lobby_messages[chat.id] = msg.message_id


# /katil
async def katil(update, context):
    result = join_game(
        update.effective_chat.id,
        update.effective_user.id,
        update.effective_user.first_name
    )

    if result == "NO_GAME":
        await update.message.reply_text(
            "❌ Önce /oyun komutu ile bir oyun oluşturulmalı."
        )
        return

    if result == "ALREADY_JOINED":
        await update.message.reply_text(
            "ℹ️ Zaten oyuna katıldın."
        )
        return

    oyuncu = len(games[update.effective_chat.id]["players"])
    await update.message.reply_text(
        f"✅ {update.effective_user.first_name} oyuna katıldı!\n\n👥 Toplam oyuncu: {oyuncu}"
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

    failed_players = []
    for player in game["players"]:
        cards = "\n".join(
            game["hands"][player["id"]]
        )
        try:
            await context.bot.send_message(
                player["id"],
                f"🃏 Kartların:\n\n{cards}"
            )
        except Exception:
            failed_players.append(player["name"])

    if failed_players:
        names = ", ".join(failed_players)
        await update.message.reply_text(
            f"⚠️ Şu oyunculara özelden mesaj gönderilemedi (önce botu özelden başlatmaları lazım):\n{names}\n\n"
            f"https://t.me/{context.bot.username}"
        )


# /bitir
async def bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:
        await update.message.reply_text(
            "❌ Bu grupta aktif bir oyun yok."
        )
        return

    game = games[chat_id]

    # Sadece oyunu kuran kişi ya da grup yöneticisi bitirebilsin
    is_owner = user.id == game["owner"]
    is_admin = False
    if not is_owner:
        member = await context.bot.get_chat_member(chat_id, user.id)
        is_admin = member.status in ("administrator", "creator")

    if not is_owner and not is_admin:
        await update.message.reply_text(
            "❌ Oyunu sadece oyunu kuran kişi veya grup yöneticisi bitirebilir."
        )
        return

    end_game(chat_id)
    await update.message.reply_text(
        "🛑 Oyun sonlandırıldı. Yeni bir oyun için /oyun kullanabilirsiniz."
    )


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

/bitir
Aktif oyunu sonlandırır.

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
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CallbackQueryHandler(button))

    print("✅ Meyus UNO çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
        
