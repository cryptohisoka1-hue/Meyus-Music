import asyncio
from game import *
from cards_data import (
    card_display_label, DECK_BACK_CODE,
    COLOR_NAME_TR, COLOR_LABELS, ALL_CARD_CODES,
)
from card_cache import get_card_file_id, prewarm_all_cards
from sticker_cache import get_sticker_set, get_card_sticker_file_id
from card_sticker_map import CARD_TO_STICKER_INDEX
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedPhoto,
    InlineQueryResultCachedSticker,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
)
from telegram.error import ChatMigrated
from config import BOT_TOKEN, STORAGE_CHAT_ID, STICKER_SET_NAME
from database import db


def player_name(game, uid):
    for p in game["players"]:
        if p["id"] == uid:
            return p["name"]
    return "?"


def html_escape(value):
    """Telegram HTML parse_mode için güvenli metin."""
    value = "" if value is None else str(value)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def mention_html(uid, name):
    """Kullanıcı adı olmasa bile çalışan, tıklanabilir etiket."""
    return f'<a href="tg://user?id={uid}">{html_escape(name)}</a>'


HAND_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("🎴 Kartlarımı Gör / Oyna",
                                                           switch_inline_query_current_chat="")]])


async def announce_turn(context: ContextTypes.DEFAULT_TYPE, chat_id):
    game = games.get(chat_id)
    if not game or not game.get("started") or game.get("winner"):
        return
    uid = current_player(chat_id)
    name = player_name(game, uid)
    color_tr = COLOR_NAME_TR.get(game["top_color"], game["top_color"])
    top_label = card_display_label(top_card(chat_id))
    await context.bot.send_message(
        chat_id,
        f"🎯 Sıra sende {mention_html(uid, name)}!\n"
        f"🎴 Son atılan kart: <b>{top_label}</b>\n"
        f"🎨 Geçerli renk: <b>{color_tr}</b>\n\n"
        f"Aşağıdaki butona dokun, kartların otomatik açılsın 🎴",
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
        f"💰 +50 coin, +30 XP\n\n"
        f"Yeni oyun için /oyun",
        parse_mode="HTML",
    )


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"""🎮 <b>MEYUS UNO</b> Merhaba <b>{html_escape(user.first_name)}</b>! 🎉 Meyus UNO'ya hoş geldin. Bu bot ile arkadaşlarınla tamamen Telegram üzerinden UNO oynayabilirsin. 📜 Komutlar: /start - Botu başlat /yardim - Yardım /oyun - Yeni oyun oluştur /katil - Oyuna katıl /baslat - Oyunu başlat /bitir - Oyunu/lobiyi sonlandır /profil - Profilin /cek - Kart çek (sıra sendeyken) /pas - Pas geç (kart çektikten sonra) 🎴 Her an "Kartlarımı Gör / Oyna" butonuna dokunarak elini görebilirsin (sıra sende değilse sadece görüntülemek için). Sıra sende olduğunda aynı buton oynanabilir kartlarını, kart çekme ve pas geçme seçeneklerini listeler; seçtiğin otomatik uygulanır. İyi eğlenceler ❤️"""
    await update.message.reply_text(text, parse_mode="HTML")


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
        f"🎮 <b>Meyus UNO Lobisi</b>\n\n"
        f"👥 Oyuncular (1)\n"
        f"• {html_escape(user.first_name)}",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
    )
    lobby_messages[chat.id] = msg


async def _do_start_game(context, chat_id):
    if chat_id not in games:
        return False

    game_before = games[chat_id]
    if game_before.get("started"):
        return False

    game = start_game(chat_id)
    if not game:
        return False

    t_card = top_card(chat_id)
    color_tr = COLOR_NAME_TR.get(game["top_color"], game["top_color"])

    # Tüm kart görsellerini arka planda önceden cache'le (bir sonraki @bot sorgusu bekletmeden anında çalışsın diye).
    # Önbellekleme için oyun grubu DEĞİL, mümkünse gizli depo sohbeti (STORAGE_CHAT_ID) kullanılır ki oyunculara kartlar bot tarafından "kendiliğinden" gönderiliyormuş gibi görünmesin.
    # STORAGE_CHAT_ID ayarlı değilse (önerilmez) oyunun kendi grubuna düşer.
    cache_chat_id = STORAGE_CHAT_ID or chat_id
    asyncio.create_task(prewarm_all_cards(context.bot, cache_chat_id, ALL_CARD_CODES))

    file_id = await get_card_file_id(context.bot, t_card, cache_chat_id)
    await context.bot.send_photo(
        chat_id,
        photo=file_id,
        caption=(
            f"🎉 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: <b>{color_tr}</b>\n\n"
            f"Herkes istediği an elini görebilir, sadece sırası gelen oynayabilir."
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )
    await announce_turn(context, chat_id)
    return True


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
        text = f"🎮 <b>Meyus UNO Lobisi</b>\n\n"
        text += f"👥 Oyuncular ({len(players)})\n\n"
        for p in players:
            text += f"• {html_escape(p['name'])}\n"
        keyboard = [
            [InlineKeyboardButton("➕ Katıl", callback_data="join")],
            [InlineKeyboardButton("▶️ Başlat", callback_data="start_game")]
        ]
        await query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    if query.data == "start_game":
        if chat_id not in games:
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return
        if games[chat_id].get("started"):
            await query.answer("Oyun zaten başladı.", show_alert=True)
            return
        if len(games[chat_id]["players"]) < 2:
            await query.answer("En az 2 oyuncu gerekli.", show_alert=True)
            return
        await query.answer("🎉 Oyun başlatılıyor...")
        await query.edit_message_text("🎉 Oyun başlatılıyor...")
        started = await _do_start_game(context, chat_id)
        if not started:
            await context.bot.send_message(
                chat_id,
                "❌ Oyun başlatılamadı. Lütfen /oyun ile yeni bir lobi oluşturun."
            )
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
    oyuncu = len(games[update.effective_chat.id]["players"])
    await update.message.reply_text(
        f"✅ {html_escape(update.effective_user.first_name)} oyuna katıldı!\n\n"
        f"👥 Toplam oyuncu: {oyuncu}",
        parse_mode="HTML",
    )


# /baslat
async def baslat(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("Önce /oyun oluştur.")
        return
    if games[chat_id].get("started"):
        await update.message.reply_text("ℹ️ Oyun zaten başladı.")
        return
    if len(games[chat_id]["players"]) < 2:
        await update.message.reply_text("En az 2 oyuncu gerekli.")
        return
    started = await _do_start_game(context, chat_id)
    if not started:
        await update.message.reply_text("❌ Oyun başlatılamadı. Lütfen tekrar deneyin.")


# /stickerlar - sticker paketinin içeriğini index+emoji olarak listeler.
# Bu, CARD_TO_STICKER_INDEX eşleşmesini oluşturmak için bir kereye mahsus kullanılır; sonrasında kaldırılabilir.
async def stickerlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sticker_set = await get_sticker_set(context.bot, STICKER_SET_NAME)
    except Exception as e:
        await update.message.reply_text(f"❌ Sticker paketi alınamadı: {e}")
        return
    lines = [f"📦 Paket: {sticker_set.name} ({len(sticker_set.stickers)} sticker)\n"]
    for idx, s in enumerate(sticker_set.stickers):
        lines.append(f"{idx}: {s.emoji or '—'}")
    text = "\n".join(lines)
    # Telegram mesaj limiti 4096 karakter, gerekirse parçala
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500])


# /cek - kart çek (sıra sendeyken)
async def cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id, game = find_active_game_for_user(user.id)
    if not game:
        await update.message.reply_text("❌ Aktif bir oyunda değilsin.")
        return
    if chat_id != update.effective_chat.id:
        await update.message.reply_text("❌ Bu komutu oynadığın oyunun grubunda kullan.")
        return
    if current_player(chat_id) != user.id:
        await update.message.reply_text("⏳ Sıra sende değil.")
        return
    res = draw_card(chat_id, user.id)
    if not res["ok"]:
        await update.message.reply_text("❌ Kart çekilemedi.")
        return
    actor_mention = mention_html(user.id, player_name(game, user.id))
    n = len(res["drawn"])
    await update.message.reply_html(
        f"🃏 {actor_mention} kart çekti ({n} kart)."
        if n else f"🃏 {actor_mention} çekmek istedi ama deste boş."
    )
    if not game.get("winner"):
        await update.message.reply_html(
            f"Şimdi çektiğin kartı oynayabilir ya da /pas ile sırayı geçebilirsin.\n"
            f"Elini görmek için 🎴 butonuna dokun.",
        )


# /pas - kart çektikten sonra pas geçme
async def pas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id, game = find_active_game_for_user(user.id)
    if not game:
        await update.message.reply_text("❌ Aktif bir oyunda değilsin.")
        return
    if chat_id != update.effective_chat.id:
        await update.message.reply_text("❌ Bu komutu oynadığın oyunun grubunda kullan.")
        return
    res = pass_turn(chat_id, user.id)
    if not res["ok"]:
        reasons = {
            "SIRA_DEGIL": "⏳ Sıra sende değil.",
            "ONCE_CEK": "❌ Pas geçmeden önce kart çekmelisin (/cek).",
            "OYUN_YOK": "❌ Aktif bir oyun bulunamadı.",
        }
        await update.message.reply_text(reasons.get(res["reason"], "❌ Pas geçilemedi."))
        return
    actor_mention = mention_html(user.id, player_name(game, user.id))
    await context.bot.send_message(
        chat_id,
        f"⏭ {actor_mention} pas geçti.",
        parse_mode="HTML",
    )
    await announce_turn(context, chat_id)


# Inline query: sıra kimdeyse SADECE ona özel oynanabilir kartları + kart çekme/pas seçeneğini gösterir
async def inline_hand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_query = update.inline_query
    user = inline_query.from_user
    chat_id, game = find_active_game_for_user(user.id)
    if not game:
        await inline_query.answer(
            [],
            switch_pm_text="Aktif bir oyunda değilsin",
            switch_pm_parameter="no_game",
            cache_time=1,
            is_personal=True,
        )
        return
    my_turn = current_player(chat_id) == user.id
    hand = game["hands"].get(user.id, [])
    legal = set(legal_cards_for(chat_id, user.id)) if my_turn else set()
    cache_chat_id = STORAGE_CHAT_ID or chat_id
    results = []
    for idx, card_code in enumerate(hand):
        sticker_file_id = None
        if card_code in CARD_TO_STICKER_INDEX:
            try:
                sticker_file_id = await get_card_sticker_file_id(
                    context.bot, STICKER_SET_NAME, card_code,
                    CARD_TO_STICKER_INDEX[card_code]
                )
            except Exception as e:
                print(f"⚠️ Sticker alınamadı ({card_code}): {e}")
        if my_turn and card_code in legal:
            desc = "✅ Oynamak için dokun"
        elif my_turn:
            desc = "❌ Şu an geçersiz (renk/sayı uymuyor)"
        else:
            desc = "👀 Sadece görüntüleme — sıra sende değil"
        if sticker_file_id:
            results.append(
                InlineQueryResultCachedSticker(
                    id=f"{card_code}#{idx}",
                    sticker_file_id=sticker_file_id,
                )
            )
            continue
        try:
            file_id = await get_card_file_id(context.bot, card_code, cache_chat_id)
        except Exception as e:
            print(f"⚠️ Kart görseli yüklenemedi ({card_code}): {e}")
            continue
        results.append(
            InlineQueryResultCachedPhoto(
                id=f"{card_code}#{idx}",
                photo_file_id=file_id,
                title=f"🎴 {card_display_label(card_code)}",
                description=desc,
            )
        )
    if my_turn:
        has_drawn = game.get("has_drawn", {}).get(user.id, False)
        try:
            deck_file_id = await get_card_file_id(context.bot, DECK_BACK_CODE, cache_chat_id)
            results.append(
                InlineQueryResultCachedPhoto(
                    id="draw",
                    photo_file_id=deck_file_id,
                    title="🃏 Kart Çek",
                    description="Elinde oynanabilir kart yoksa (veya istemiyorsan) çek",
                )
            )
        except Exception as e:
            print(f"⚠️ Deste görseli yüklenemedi: {e}")
        # Sadece kart çektikten sonra pas geçilebilir
        if has_drawn:
            results.append(
                InlineQueryResultArticle(
                    id="pass",
                    title="⏭ Pas Geç",
                    description="Çektiğin kartı oynamak istemiyorsan sırayı geç",
                    input_message_content=InputTextMessageContent("⏭ pas geçildi"),
                )
            )
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
            f"🃏 {actor_mention} kart çekti ({n} kart)."
            if n else f"🃏 {actor_mention} çekmek istedi ama deste boş.",
            parse_mode="HTML",
        )
        if not game.get("winner"):
            await announce_turn(context, chat_id)
        return
    if result_id == "pass":
        res = pass_turn(chat_id, user.id)
        if not res["ok"]:
            reasons = {
                "SIRA_DEGIL": "sıra artık sende değildi",
                "ONCE_CEK": "önce kart çekmen gerekiyordu",
                "OYUN_YOK": "aktif bir oyun bulunamadı",
            }
            await context.bot.send_message(
                chat_id,
                f"⚠️ {actor_mention} pas geçmeye çalıştı ama işlenmedi "
                f"({reasons.get(res['reason'], res['reason'])}).",
                parse_mode="HTML",
            )
            return
        await context.bot.send_message(
            chat_id,
            f"⏭ {actor_mention} pas geçti.",
            parse_mode="HTML",
        )
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
            f"⚠️ {actor_mention} geçersiz bir kart gönderdi "
            f"({reasons.get(res['reason'], res['reason'])}), hamle işlenmedi.",
            parse_mode="HTML",
        )
        return
    if res.get("win"):
        await finish_game(context, chat_id, user.id)
        return
    if res.get("remaining") == 1:
        await context.bot.send_message(
            chat_id,
            f"🎉 {actor_mention} <b>UNO!</b> Elinde sadece 1 kart kaldı!",
            parse_mode="HTML",
        )
    if res.get("needs_color"):
        keyboard = [[
            InlineKeyboardButton(
                f"{COLOR_LABELS[c]} {COLOR_NAME_TR[c]}",
                callback_data=f"renk:{c}:{user.id}"
            ) for c in ["kirmizi", "yesil"]
        ], [
            InlineKeyboardButton(
                f"{COLOR_LABELS[c]} {COLOR_NAME_TR[c]}",
                callback_data=f"renk:{c}:{user.id}"
            ) for c in ["mavi", "sari"]
        ]]
        await context.bot.send_message(
            chat_id,
            f"🎨 {actor_mention}, joker için bir renk seç:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML",
        )
        return
    if res["effect"] in ("skip", "reverse"):
        await announce_effect(context, chat_id, actor_mention, res["effect"])
    elif res["effect"] in ("draw2", "draw4"):
        next_mention = mention_html(
            current_player(chat_id),
            player_name(game, current_player(chat_id))
        )
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
    is_owner = game.get("owner") == user.id
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
            f"🛑 Oyun {html_escape(user.first_name)} tarafından sonlandırıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"🛑 Lobi {html_escape(user.first_name)} tarafından kapatıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz.",
            parse_mode="HTML",
        )


# /profil
async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Önce /start kullan.")
        return
    await update.message.reply_text(
        f"""👤 Profil 💰 Coin: {user[3]} 🏆 Galibiyet: {user[4]} 🎮 Oyun: {user[5]} ⭐ Seviye: {user[6]} ✨ XP: {user[7]}"""
    )


async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """📖 Yardım /start - Botu başlatır /oyun - Yeni oyun oluşturur /katil - Oyuna katılır /baslat - Oyunu başlatır /bitir - Oyunu/lobiyi sonlandırır (oyunu açan veya yöneticiler) /profil - Profilini gösterir /cek - Sıra sendeyken kart çeker /pas - Kart çektikten sonra sırayı geçer 🎴 Her an "Kartlarımı Gör / Oyna" butonuna dokunarak elini görebilirsin. Sıra sende olduğunda aynı buton oynanabilir kartları, kart çekme ve pas geçme seçeneklerini listeler, seçtiğin otomatik uygulanır."""
    )


def _migrate_chat(old_chat_id, new_chat_id):
    """Grup süper gruba yükseltilince oyun/lobi verisini yeni chat_id'ye taşır."""
    if old_chat_id in games:
        game = games.pop(old_chat_id)
        games[new_chat_id] = game
        for uid in game.get("hands", {}).keys():
            if user_active_chat.get(uid) == old_chat_id:
                user_active_chat[uid] = new_chat_id
    if old_chat_id in lobby_messages:
        lobby_messages[new_chat_id] = lobby_messages.pop(old_chat_id)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, ChatMigrated):
        old_chat_id = None
        if update and getattr(update, "effective_chat", None):
            old_chat_id = update.effective_chat.id
        new_chat_id = err.new_chat_id
        if old_chat_id is not None:
            _migrate_chat(old_chat_id, new_chat_id)
        try:
            await context.bot.send_message(
                new_chat_id,
                "ℹ️ Bu grup süper gruba yükseltildi, oyun verisi yeni gruba taşındı. "
                "Devam etmek için tekrar 🎴 Kartlarımı Gör / Oyna butonuna dokunabilirsiniz.",
            )
        except Exception:
            pass
        return
    print(f"⚠️ Beklenmeyen hata: {err}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", yardim))
    app.add_handler(CommandHandler("oyun", oyun))
    app.add_handler(CommandHandler("katil", katil))
    app.add_handler(CommandHandler("baslat", baslat))
    app.add_handler(CommandHandler("bitir", bitir))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CommandHandler("cek", cek))
    app.add_handler(CommandHandler("pas", pas))
    app.add_handler(CommandHandler("stickerlar", stickerlar))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(InlineQueryHandler(inline_hand))
    app.add_handler(ChosenInlineResultHandler(chosen_result))
    app.add_error_handler(error_handler)
    print("✅ Meyus UNO başlatıldı!")
    app.run_polling()


if __name__ == "__main__":
    main()
