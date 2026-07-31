from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    InlineQueryHandler
)

# game.py'deki fonksiyonları ve değişkenleri içe aktarıyoruz
# NOT: game.py dosyanızda bu isimler mutlaka tanımlı olmalıdır.
from game import (
    create_game,
    join_game,
    start_game,
    play_card,
    draw_turn,
    choose_color,
    end_game,
    COLOR_NAMES,
    NAME_TO_COLOR,
    get_player_name,
    games,
    lobby_messages
)

from database import db
from callbacks import button
from config import BOT_TOKEN


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    
    db.add_user(user.id, user.first_name, user.username)

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
/at - Kart at (örn: /at 3)
/cek - Kart çek, sırayı geç
/renk - Joker sonrası renk seç
/bitir - Oyunu bitir
/profil - Profilin

İyi eğlenceler ❤️
"""
    await update.message.reply_html(text)


async def oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    if not create_game(chat.id, user.id):
        await update.message.reply_text("❌ Bu grupta zaten açık bir oyun var.")
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
    
    if chat.id in games:
        lobby_messages[chat.id] = msg.message_id


async def katil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    result = join_game(chat.id, user.id, user.first_name)

    if result == "NO_GAME":
        await update.message.reply_text("❌ Önce /oyun komutu ile bir oyun oluşturulmalı.")
        return

    if result == "ALREADY_JOINED":
        await update.message.reply_text("ℹ️ Zaten oyuna katıldın.")
        return

    oyuncu = len(games[chat.id]["players"])
    await update.message.reply_text(
        f"✅ {user.first_name} oyuna katıldı!\n\n👥 Toplam oyuncu: {oyuncu}"
    )


def _basladi_mesaji(chat_id):
    game = games[chat_id]
    top = game["discard"][-1]
    color_name = COLOR_NAMES.get(game["current_color"], game["current_color"])
    turn_name = get_player_name(chat_id, game["turn_order"][game["turn_index"]])
    return (
        "🚀 Oyun başladı!\n\n"
        f"Üst kart: {top} Renk: {color_name}\n"
        f"▶️ Sıra: {turn_name}\n\n"
        "Kartlarını görmek için aşağıdaki butona bas (sadece sana görünür).\n"
        "Kart atmak için: /at <numara>\n"
        "Çekmek/pas geçmek için: /cek"
    )


async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not chat_id or not user:
        return

    if chat_id not in games:
        await update.message.reply_text("Önce /oyun oluştur.")
        return

    game_info = games[chat_id]

    if user.id != game_info["owner"]:
        await update.message.reply_text("❌ Oyunu sadece oyunu kuran kişi başlatabilir.")
        return

    if len(game_info["players"]) < 2:
        await update.message.reply_text("En az 2 oyuncu gerekli.")
        return

    start_game(chat_id)

    keyboard = [[InlineKeyboardButton("🃏 Kartlarımı Gör", callback_data="show_hand")]]
    await update.message.reply_text(
        _basladi_mesaji(chat_id),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def at(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not chat_id or not user:
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /at <kart numarası>\nÖrnek: /at 3")
        return

    try:
        index = int(context.args) - 1
    except ValueError:
        await update.message.reply_text("Kart numarası bir sayı olmalı. Örnek: /at 3")
        return

    result = play_card(chat_id, user.id, index)
    status = result.get("status")

    if status == "NO_GAME":
        await update.message.reply_text("❌ Aktif bir oyun yok.")
        return
    if status == "GAME_OVER":
        await update.message.reply_text("🏁 Oyun zaten bitti.")
        return
    if status == "WAITING_COLOR":
        await update.message.reply_text("🌈 Önce renk seçilmesi bekleniyor: /renk kirmizi | yesil | mavi | sari")
        return
    if status == "NOT_YOUR_TURN":
        await update.message.reply_text("⏳ Sıra sende değil.")
        return
    if status == "NOT_PLAYER":
        await update.message.reply_text("❌ Bu oyunda değilsin.")
        return
    if status == "INVALID_INDEX":
        await update.message.reply_text("❌ Geçersiz kart numarası. Kartlarını kontrol et.")
        return
    if status == "INVALID_CARD":
        await update.message.reply_text("❌ Bu kartı şu an oynayamazsın (renk/numara uymuyor).")
        return

    name = get_player_name(chat_id, user.id)

    if status == "WIN":
        card = result.get("card")
        card_str = f"{card['color']} {card['value']}" if isinstance(card, dict) else str(card)
        
        text = (
            f"🏆 <b>Tebrikler!</b> 🏆\n\n"
            f"<b>{name}</b>, UNO oyununu kazandı!\n"
            f"Son oynanan kart: {card_str}\n\n"
            "Yeni bir oyun için /oyun komutunu kullanabilirsiniz."
        )
        await update.message.reply_html(text)
        end_game(chat_id)
        return

    if status == "WILD_PLAYED":
        card = result.get("card")
        card_str = f"{card['color']} {card['value']}" if isinstance(card, dict) else str(card)
        await update.message.reply_text(
            f"🌈 {name} {card_str} attı!\n"
            f"Renk seçmesi gerekiyor: /renk kirmizi | yesil | mavi | sari"
        )
        return

    card = result.get("card")
    effect = result.get("effect")
    next_id = games[chat_id]["turn_order"][games[chat_id]["turn_index"]]
    next_name = get_player_name(chat_id, next_id)

    msg = f"{name} {card} attı."
    if effect == "reverse":
        msg += " 🔄 Yön değişti!"
    elif effect == "skip":
        skipped_name = get_player_name(chat_id, result.get("skipped"))
        msg += f" ⛔ {skipped_name} pas geçti!"
    elif effect == "+2":
        target_name = get_player_name(chat_id, result.get("target"))
        msg += f" {target_name} 2 kart çekti ve pas geçti!"

    msg += f"\n\n▶️ Sıra: {next_name}"
    await update.message.reply_text(msg)


async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    result = draw_turn(chat_id, user.id)
    status = result.get("status")

    if status == "NO_GAME":
        await update.message.reply_text("❌ Aktif bir oyun yok.")
        return
    if status == "GAME_OVER":
        await update.message.reply_text("🏁 Oyun zaten bitti.")
        return
    if status == "WAITING_COLOR":
        await update.message.reply_text("🌈 Önce renk seçilmesi bekleniyor: /renk kirmizi | yesil | mavi | sari")
        return
    if status == "NOT_YOUR_TURN":
        await update.message.reply_text("⏳ Sıra sende değil.")
        return

    name = get_player_name(chat_id, user.id)
    next_id = games[chat_id]["turn_order"][games[chat_id]["turn_index"]]
    next_name = get_player_name(chat_id, next_id)
    await update.message.reply_text(
        f"🎴 {name} bir kart çekti ve pas geçti.\n\n▶️ Sıra: {next_name}"
    )


async def renk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if not context.args:
        await update.message.reply_text("Kullanım: /renk kirmizi | yesil | mavi | sari")
        return

    renk_adi = context.args.lower()
    color = NAME_TO_COLOR.get(renk_adi)
    if not color:
        await update.message.reply_text("Geçersiz renk. Kullanım: /renk kirmizi | yesil | mavi | sari")
        return

    result = choose_color(chat_id, user.id, color)
    status = result.get("status")

    if status == "NO_GAME":
        await update.message.reply_text("❌ Aktif bir oyun yok.")
        return
    if status == "NOT_PENDING":
        await update.message.reply_text("❌ Şu an renk seçmen gerekmiyor.")
        return

    name = get_player_name(chat_id, user.id)
    next_id = games[chat_id]["turn_order"][games[chat_id]["turn_index"]]
    next_name = get_player_name(chat_id, next_id)

    msg = f"{name} rengi {COLOR_NAMES[color]} seçti."
    if result.get("effect") == "+4":
        target_name = get_player_name(chat_id, result.get("target"))
        msg += f" {target_name} 4 kart çekti ve pas geçti!"

    msg += f"\n\n▶️ Sıra: {next_name}"
    await update.message.reply_text(msg)


async def bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:
        await update.message.reply_text("❌ Bu grupta aktif bir oyun yok.")
        return

    game = games[chat_id]

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


async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Önce /start kullan.")
        return

    await update.message.reply_text(
        f"""👤 Profil

🪙 Coin: {user} [3]
🏆 Galibiyet: {user} [4]
🎮 Oyun: {user} [5]
⭐ Seviye: {user} [6]
✨ XP: {user} [7]
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

/at <numara>
Elindeki o numaralı kartı atar. Örnek: /at 3

/cek
Elinden oynayacak kart yoksa bir kart çeker ve sırayı geçer.

/renk <renk>
Joker (🌈) attıktan sonra renk seçmek için. Örnek: /renk kirmizi

/bitir
Aktif oyunu sonlandırır.

/profil
Profilini gösterir.
"""
    )


# Inline Query Handler - HATA YOK: Boş liste  doğru yazıldı
async def inline_query(update, context):
    await update.inline_query.answer([], cache_time=0)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("oyun", oyun))
    app.add_handler(CommandHandler("katil", katil))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("at", at))
    app.add_handler(CommandHandler("cek", cek))
    app.add_handler(CommandHandler("renk", renk))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("profil", profil))
    
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(InlineQueryHandler(inline_query))
    
    print("✅ Meyus UNO çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
        
