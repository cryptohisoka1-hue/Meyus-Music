import uuid

from game import *
from cards_data import card_image_url, card_display_label
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
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

🃏 Elindeki kartları özel olarak görmek için, oyun başladıktan sonra
grup sohbetinde @{context.bot.username} yazıp bir boşluk bırak — kartların
sadece sana görünen bir önizleme olarak açılır, kimseye gönderilmez.

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
        [InlineKeyboardButton("➕ Katıl", callback_data="join")],
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


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    user = query.from_user

    if query.data == "join":
        result = join_game(chat_id, user.id, user.first_name)

        if result is False or result == "ALREADY_JOINED":
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
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if query.data == "start_game":
        chat_id = query.message.chat.id
        if chat_id not in games:
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return

        if len(games[chat_id]["players"]) < 2:
            await query.answer("En az 2 oyuncu gerekli.", show_alert=True)
            return

        await query.answer("🚀 Oyun başlatılıyor...")
        start_game(chat_id)

        await query.edit_message_text(
            "🚀 <b>Oyun başladı!</b>\n\n"
            f"🃏 Elindeki kartları görmek için gruba @{context.bot.username} yaz "
            "(bir boşluk bırakman yeterli) — sadece sana özel bir önizleme açılır.",
            parse_mode="HTML"
        )
        return

    await query.answer()


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

    start_game(chat_id)

    # DM YOK: kartlar artik ozelden gonderilmiyor.
    # Herkes kendi elini gormek icin inline query kullaniyor (asagida inline_hand).
    await update.message.reply_html(
        "🚀 <b>Oyun başladı!</b>\n\n"
        f"🃏 Elindeki kartları görmek için gruba <code>@{context.bot.username}</code> yaz "
        "(bir boşluk bırakman yeterli) — sadece sana özel, görsel bir önizleme açılır. "
        "Kimseye bir şey gönderilmez, seçmene de gerek yok."
    )


# Inline query: kart gorsellerini SADECE yazan kisiye ozel gosterir
async def inline_hand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_query = update.inline_query
    user = inline_query.from_user

    chat_id, game = find_active_game_for_user(user.id)

    if not game:
        results = []
        await inline_query.answer(
            results,
            switch_pm_text="Aktif bir oyunda değilsin",
            switch_pm_parameter="no_game",
            cache_time=1,
            is_personal=True,
        )
        return

    hand = game["hands"].get(user.id, [])
    results = []
    for card_code in hand:
        url = card_image_url(card_code)
        results.append(
            InlineQueryResultPhoto(
                id=str(uuid.uuid4()),
                photo_url=url,
                thumbnail_url=url,
                title=card_display_label(card_code),
                description="Görüntülemek için dokun, GÖNDERME (sadece sana görünür)",
            )
        )

    await inline_query.answer(
        results,
        cache_time=1,
        is_personal=True,  # kritik: sonuc sadece bu kullaniciya ozel
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

Kartlarını görmek için oyun başladıktan sonra gruba
@botadi yaz — kartların sadece sana özel açılır, gönderilmez.
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
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(InlineQueryHandler(inline_hand))

    print("✅ Meyus UNO çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
