import uuid

from game import *
from cards_data import (
    card_image_url, card_display_label, DECK_BACK_CODE,
    COLOR_NAME_TR, COLOR_LABELS, ALL_CARD_CODES,
)
from card_cache import get_card_file_id, prewarm_all_cards
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

# 1. Pas Butonunu Oluşturma ve Mesaja Ekleme
async def gonder_kartlar(update: Update, context: CallbackContext) -> None:
    """Oyuncunun kartlarını ve pas butonunu gönderen fonksiyon."""
    
    # Pas butonunu tanımlıyoruz. callback_data, butona basıldığında bota ne gideceğini belirler.
    pas_butonu = InlineKeyboardButton("Pas (Kart Çek)", callback_data="pas_eylemi")
    
    # Butonu bir satıra yerleştiriyoruz
    klavye_duzeni = [[pas_butonu]]
    
    # Klavye işaretlemesini (markup) oluşturuyoruz
    reply_markup = InlineKeyboardMarkup(klavye_duzeni)
    
    # Kullanıcıya mesajı ve butonu gönderiyoruz
    await update.message.reply_text(
        "Sıra sende! Kart oyna veya pas geç.", 
        reply_markup=reply_markup
    )

# 2. Pas Butonuna Tıklandığında Yapılacak İşlem (Callback)
async def pas_butonu_tiklandi(update: Update, context: CallbackContext) -> None:
    """Oyuncu 'Pas' butonuna bastığında çalışacak kod."""
    query = update.callback_query
    
    # Telegram'daki yükleniyor animasyonunu durduruyoruz
    await query.answer()
    
    # Pas işlemine özel oyun mantığını buraya yazabilirsin (Örn: Oyuncuya deste kartı verilir)
    # await query.message.reply_text("Pas dedin ve desteden bir kart çektin!")
    
    # Butona basıldıktan sonra butonlu mesajı güncelleyebilir veya kaldırabilirsin
    await query.edit_message_text(text="Pas dediniz. Sıra bir sonraki oyuncuda!")

    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
)
from config import BOT_TOKEN, STORAGE_CHAT_ID
from database import db


def get_storage_chat(chat_id):
    """
    Kart gorsellerini cache'lerken kullanilacak GIZLI sohbet.
    STORAGE_CHAT_ID ayarlanmissa (onerilen) o kullanilir - hicbir kart
    oyuncularin gordugu gruba dusmez. Ayarlanmamissa (onerilmez), eski
    davranisa geri doner: oyunun kendi grubu kullanilir (kucuk bir
    gizlilik/gorunurluk riski tasir).
    """
    return STORAGE_CHAT_ID if STORAGE_CHAT_ID else chat_id


def player_name(game, uid):
    for p in game["players"]:
        if p["id"] == uid:
            return p["name"]
    return "?"


def mention_html(uid, name):
    """Kullanici adi olmasa bile calisan, tiklanabilir/bildirim tetikleyen etiket."""
    safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={uid}">{safe_name}</a>'


HAND_BUTTON = InlineKeyboardMarkup([[
    InlineKeyboardButton("🎴 Kartlarımı Gör / Oyna", switch_inline_query_current_chat="")
]])


async def announce_turn(context: ContextTypes.DEFAULT_TYPE, chat_id):
    game = games.get(chat_id)
    if not game or not game.get("started") or game.get("winner"):
        return

    uid = current_player(chat_id)
    name = player_name(game, uid)
    color_tr = COLOR_NAME_TR.get(game["top_color"], game["top_color"])

    await context.bot.send_message(
        chat_id,
        f"🔁 Sıra sende {mention_html(uid, name)}!\n"
        f"🎨 Geçerli renk: <b>{color_tr}</b>\n\n"
        f"Aşağıdaki butona dokun, kartların otomatik açılsın 👇",
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )


async def announce_effect(context, chat_id, actor_mention, effect, next_mention=None):
    texts = {
        "skip": f"⛔ {actor_mention} DUR kartı oynadı, sıra atlandı!",
        "reverse": f"🔄 {actor_mention} YÖN kartı oynadı, yön değişti!",
        "draw2": f"➕2️⃣ {actor_mention} +2 oynadı, {next_mention} 2 kart çekip sırasını kaçırdı!",
        "draw4": f"➕4️⃣ {actor_mention} +4 oynadı, {next_mention} 4 kart çekip sırasını kaçırdı!",
    }
    text = texts.get(effect)
    if text:
        await context.bot.send_message(chat_id, text, parse_mode="HTML")


async def finish_game(context, chat_id, winner_uid):
    game = games[chat_id]
    winner_mention = mention_html(winner_uid, player_name(game, winner_uid))

    db.add_win(winner_uid)
    for p in game["players"]:
        db.add_game(p["id"])
    db.add_coin(winner_uid, 50)
    db.add_xp(winner_uid, 30)

    await context.bot.send_message(
        chat_id,
        f"🏆 {winner_mention} oyunu kazandı! 🎉\n\n"
        f"+50 coin, +30 XP kazandın.\n\n"
        f"Yeni oyun için /oyun yazabilirsiniz.",
        parse_mode="HTML",
    )
    end_game(chat_id)


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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
/bitir - Oyunu/lobiyi sonlandır
/profil - Profilin

🃏 Her an "🎴 Kartlarımı Gör / Oyna" butonuna dokunarak elini
görebilirsin (sıra sende değilse sadece görüntülemek için).
Sıra sende olduğunda aynı buton oynanabilir kartlarını ve kart
çekme seçeneğini listeler; seçtiğin otomatik oynanır.

İyi eğlenceler ❤️
"""
    await update.message.reply_html(text)


# /oyun
async def oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

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
    lobby_messages[chat.id] = msg.message_id


async def _do_start_game(context, chat_id):
    game = start_game(chat_id)
    t_card = top_card(chat_id)
    color_tr = COLOR_NAME_TR.get(game["top_color"], game["top_color"])

    file_id = await get_card_file_id(context.bot, t_card, get_storage_chat(chat_id))
    await context.bot.send_photo(
        chat_id,
        photo=file_id,
        caption=(
            "🚀 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: <b>{color_tr}</b>\n\n"
            f"Herkes istediği an elini görebilir, sadece sırası gelen oynayabilir."
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )
    await announce_turn(context, chat_id)


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
            text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if query.data == "start_game":
        if chat_id not in games:
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return
        if len(games[chat_id]["players"]) < 2:
            await query.answer("En az 2 oyuncu gerekli.", show_alert=True)
            return

        await query.answer("🚀 Oyun başlatılıyor...")
        await query.edit_message_text("🚀 Oyun başlatılıyor...")
        await _do_start_game(context, chat_id)
        return

    if query.data.startswith("renk:"):
        _, color, target_uid = query.data.split(":")
        target_uid = int(target_uid)

        if user.id != target_uid:
            await query.answer("Sadece kartı oynayan kişi rengi seçebilir.", show_alert=True)
            return

        ok = choose_color(chat_id, user.id, color)
        if not ok:
            await query.answer("Bu işlem artık geçerli değil.", show_alert=True)
            return

        await query.answer(f"Renk: {COLOR_NAME_TR.get(color, color)}")
        await query.edit_message_reply_markup(reply_markup=None)

        game = games[chat_id]
        await context.bot.send_message(
            chat_id,
            f"🎨 {mention_html(user.id, player_name(game, user.id))} rengi "
            f"<b>{COLOR_NAME_TR.get(color, color)}</b> seçti.",
            parse_mode="HTML",
        )

        if game.get("winner"):
            await finish_game(context, chat_id, game["winner"])
        else:
            await announce_turn(context, chat_id)
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
        await update.message.reply_text("❌ Önce /oyun komutu ile bir oyun oluşturulmalı.")
        return
    if result == "ALREADY_JOINED":
        await update.message.reply_text("ℹ️ Zaten oyuna katıldın.")
        return

    db.add_user(update.effective_user.id, update.effective_user.first_name, update.effective_user.username)
    oyuncu = len(games[update.effective_chat.id]["players"])
    await update.message.reply_text(
        f"✅ {update.effective_user.first_name} oyuna katıldı!\n\n👥 Toplam oyuncu: {oyuncu}"
    )


# /baslat
async def baslat(update, context):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text("Önce /oyun oluştur.")
        return
    if len(games[chat_id]["players"]) < 2:
        await update.message.reply_text("En az 2 oyuncu gerekli.")
        return

    await _do_start_game(context, chat_id)


# Inline query: sira kimdeyse SADECE ona ozel oynanabilir kartlari + kart cekme secenegini gosterir
async def inline_hand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_query = update.inline_query
    user = inline_query.from_user

    chat_id, game = find_active_game_for_user(user.id)

    if not game:
        await inline_query.answer(
            [], switch_pm_text="Aktif bir oyunda değilsin", switch_pm_parameter="no_game",
            cache_time=1, is_personal=True,
        )
        return

    my_turn = current_player(chat_id) == user.id
    hand = game["hands"].get(user.id, [])
    legal = set(legal_cards_for(chat_id, user.id)) if my_turn else set()
    storage_chat = get_storage_chat(chat_id)

    results = []
    for idx, card_code in enumerate(hand):
        try:
            file_id = await get_card_file_id(context.bot, card_code, storage_chat)
        except Exception:
            continue

        if my_turn and card_code in legal:
            desc = "✅ Oynamak için dokun"
        elif my_turn:
            desc = "🚫 Şu an geçersiz (renk/sayı uymuyor)"
        else:
            desc = "👁 Sadece görüntüleme — sıra sende değil"

        results.append(
            InlineQueryResultCachedPhoto(
                id=f"{card_code}#{idx}",
                photo_file_id=file_id,
                title=f"🎴 {card_display_label(card_code)}",
                description=desc,
            )
        )

    if my_turn:
        try:
            deck_file_id = await get_card_file_id(context.bot, DECK_BACK_CODE, storage_chat)
            results.append(
                InlineQueryResultCachedPhoto(
                    id="draw",
                    photo_file_id=deck_file_id,
                    title="🂠 Kart Çek",
                    description="Elinde oynanabilir kart yoksa (veya istemiyorsan) çek",
                )
            )
        except Exception:
            pass

    await inline_query.answer(results, cache_time=1, is_personal=True)


async def chosen_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    user = chosen.from_user
    result_id = chosen.result_id

    chat_id, game = find_active_game_for_user(user.id)
    if not game:
        return

    actor_mention = mention_html(user.id, player_name(game, user.id))

    if result_id == "draw":
        res = draw_card(chat_id, user.id)
        if not res["ok"]:
            return
        n = len(res["drawn"])
        await context.bot.send_message(
            chat_id,
            f"🂠 {actor_mention} kart çekti ({n} kart)."
            if n else f"🂠 {actor_mention} çekmek istedi ama deste boş.",
            parse_mode="HTML",
        )
        if not game.get("winner"):
            await announce_turn(context, chat_id)
        return

    card_code = result_id.split("#", 1)[0]

    res = play_card(chat_id, user.id, card_code)
    if not res["ok"]:
        reasons = {
            "SIRA_DEGIL": "sıra sende değildi",
            "KART_YOK": "bu kart elinde yoktu",
            "GECERSIZ_HAMLE": "bu hamle geçerli değildi (renk/sayı uymuyor)",
            "OYUN_BITTI": "oyun zaten bitmiş",
        }
        await context.bot.send_message(
            chat_id,
            f"⚠️ {actor_mention} geçersiz bir kart gönderdi ({reasons.get(res['reason'], res['reason'])}), "
            f"hamle işlenmedi.",
            parse_mode="HTML",
        )
        return

    if res["win"]:
        await finish_game(context, chat_id, user.id)
        return

    if res["needs_color"]:
        keyboard = [[
            InlineKeyboardButton(f"{COLOR_LABELS[c]} {COLOR_NAME_TR[c]}", callback_data=f"renk:{c}:{user.id}")
            for c in ["kirmizi", "yesil"]
        ], [
            InlineKeyboardButton(f"{COLOR_LABELS[c]} {COLOR_NAME_TR[c]}", callback_data=f"renk:{c}:{user.id}")
            for c in ["mavi", "sari"]
        ]]
        await context.bot.send_message(
            chat_id,
            f"🌈 {actor_mention}, joker için bir renk seç:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return

    if res["effect"] in ("skip", "reverse"):
        await announce_effect(context, chat_id, actor_mention, res["effect"])
    elif res["effect"] in ("draw2", "draw4"):
        next_mention = mention_html(current_player(chat_id), player_name(game, current_player(chat_id)))
        await announce_effect(context, chat_id, actor_mention, res["effect"], next_mention)

    await announce_turn(context, chat_id)


# /bitir
async def bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:
        await update.message.reply_text("❌ Bu grupta açık bir oyun yok.")
        return

    game = games[chat_id]
    is_owner = user.id == game.get("owner")

    is_admin = False
    if not is_owner:
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            is_admin = member.status in ("administrator", "creator")
        except Exception:
            is_admin = False

    if not (is_owner or is_admin):
        await update.message.reply_text(
            "⛔ Sadece oyunu açan kişi veya grup yöneticileri /bitir kullanabilir."
        )
        return

    was_started = game.get("started", False)
    end_game(chat_id)
    lobby_messages.pop(chat_id, None)

    if was_started:
        await update.message.reply_text(
            f"🛑 Oyun {user.first_name} tarafından sonlandırıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz."
        )
    else:
        await update.message.reply_text(
            f"🛑 Lobi {user.first_name} tarafından kapatıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz."
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

/start - Botu başlatır
/oyun - Yeni oyun oluşturur
/katil - Oyuna katılır
/baslat - Oyunu başlatır
/bitir - Oyunu/lobiyi sonlandırır (oyunu açan veya yöneticiler)
/profil - Profilini gösterir

Her an "🎴 Kartlarımı Gör / Oyna" butonuna dokunarak elini görebilirsin.
Sıra sende olduğunda aynı buton oynanabilir kartları listeler,
seçtiğin otomatik oynanır.
"""
    )


async def _on_startup(application):
    if not STORAGE_CHAT_ID:
        print(
            "⚠️  STORAGE_CHAT_ID ayarlanmamış — kartlar ihtiyaç anında oyunun "
            "kendi grubunda cache'lenecek (küçük bir gizlilik/gorunurluk riski). "
            "Ozel bir depo sohbeti ayarlamanı öneririm."
        )
        return

    print("⏳ Kartlar önceden yükleniyor (bir kereye mahsus)...")
    await prewarm_all_cards(application.bot, STORAGE_CHAT_ID, ALL_CARD_CODES)
    print("✅ Tüm kartlar cache'lendi.")


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(_on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("oyun", oyun))
    app.add_handler(CommandHandler("katil", katil))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(InlineQueryHandler(inline_hand))
    app.add_handler(ChosenInlineResultHandler(chosen_result))
    # app.add_handler(CommandHandler("kartlar", gonder_kartlar))
# app.add_handler(CallbackQueryHandler(pas_butonu_tiklandi, pattern="^pas_eylemi$"))

    print("✅ Meyus UNO çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
