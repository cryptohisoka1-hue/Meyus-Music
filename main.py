import asyncio
from game import *
from cards_data import (
    card_display_label, DECK_BACK_CODE,
    COLOR_NAME_TR, COLOR_LABELS, ALL_CARD_CODES,
    PASS_ICON_CODE, INFO_ICON_CODE, LOCKED_ICON_CODE,
)
from card_cache import get_card_file_id, get_local_icon_file_id, prewarm_all_cards
from icon_assets import pass_icon_bytes, info_icon_bytes, locked_icon_bytes
from sticker_cache import get_sticker_set, get_card_sticker_file_id
from card_sticker_map import get_card_map_for_theme
from themes import THEMES, DEFAULT_THEME, get_theme_by_id
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


HAND_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton(
    "🃏 Kartlarımı Gör / Oyna",
    switch_inline_query_current_chat="")]])


async def announce_turn(context: ContextTypes.DEFAULT_TYPE, chat_id):
    game = games.get(chat_id)
    if not game or not game.get("started") or game.get("winner"):
        return
    uid = current_player(chat_id)
    name = player_name(game, uid)
    color_tr = COLOR_NAME_TR.get(game["top_color"], game["top_color"])
    top_label = card_display_label(top_card(chat_id))

    pending = game.get("pending_draw", 0)
    extra = ""
    if pending:
        extra = (
            f"\n⚠️ Üzerinde <b>{pending}</b> kart çekme cezası var! "
            f"Üstüne uygun bir kart oynayabilir ya da /cek ile çekebilirsin."
        )

    await context.bot.send_message(
        chat_id,
        f"🎯 Sıra sende {mention_html(uid, name)}!\n"
        f"🃏 Son atılan kart: <b>{top_label}</b>\n"
        f"🎨 Geçerli renk: <b>{color_tr}</b>"
        f"{extra}\n\n"
        f"Aşağıdaki butona dokun, kartların otomatik açılsın 👇",
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )


async def announce_effect(context, chat_id, actor_mention, effect, next_mention=None, stacked_total=None):
    if effect == "draw2" and stacked_total:
        text = (
            f"➕2️⃣ {actor_mention} +2 oynadı! "
            f"Toplam ceza: <b>{stacked_total}</b> kart. "
            f"Sıradaki oyuncu üstüne +2 koyabilir ya da /cek ile çekebilir."
        )
        await context.bot.send_message(chat_id, text, parse_mode="HTML")
        return

    texts = {
        "skip": f"⛔ {actor_mention} DUR kartı oynadı, sıra atlandı!",
        "reverse": f"🔄 {actor_mention} YÖN kartı oynadı, yön değişti!",
        "draw4": f"➕4️⃣ {actor_mention} +4 oynadı, {next_mention} 4 kart çekip sırasını kaçırdı!",
    }
    text = texts.get(effect)
    if text:
        await context.bot.send_message(chat_id, text, parse_mode="HTML")


async def finish_game(context, chat_id, winner_uid):
    game = games[chat_id]
    winner_mention = mention_html(winner_uid, player_name(game, winner_uid))
    db.add_win(winner_uid, player_name(game, winner_uid))
    for p in game["players"]:
        db.add_game(p["id"], p["name"])
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
    db.add_user(user.id, user.username, user.first_name)
    text = f"""🎴 <b>MEYUS UNO</b>

Merhaba <b>{html_escape(user.first_name)}</b>! 👋 Meyus UNO'ya hoş geldin.
Bu bot ile arkadaşlarınla tamamen Telegram üzerinden UNO oynayabilirsin.

📋 Komutlar:
/start - Botu başlat
/yardim - Yardım
/oyun - Yeni oyun oluştur
/katil - Oyuna katıl
/baslat - Oyunu başlat
/bitir - Oyunu/lobiyi sonlandır
/profil - Profilin
/tema - Kart görseli temanı seç
/siralama - Haftalık ilk 10 sıralaması
/cek - Kart çek (sıra sendeyken)
/pas - Pas geç (kart çektikten sonra)

🃏 Her an "Kartlarımı Gör / Oyna" butonuna dokunarak elini görebilirsin
(sıra sende değilse sadece görüntülemek için). Sıra sende olduğunda aynı
buton oynanabilir kartlarını, kart çekme ve pas geçme seçeneklerini
listeler; seçtiğin otomatik uygulanır.

İyi eğlenceler ❤️"""
    await update.message.reply_text(text, parse_mode="HTML")


# /oyun
async def oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    if not create_game(chat.id, user.id):
        await update.message.reply_text("❌ Bu grupta zaten açık bir oyun var.")
        return
    join_game(chat.id, user.id, user.first_name)
    keyboard = [
        [InlineKeyboardButton("➕ Katıl", callback_data="join")],
        [InlineKeyboardButton("▶️ Başlat", callback_data="start_game")]
    ]
    msg = await update.message.reply_text(
        f"🎴 <b>Meyus UNO Lobisi</b>\n\n"
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

    # Tüm kart görsellerini arka planda önceden cache'le (bir sonraki @bot
    # sorgusu bekletmeden anında çalışsın diye).
    # Önbellekleme için oyun grubu DEĞİL, mümkünse gizli depo sohbeti
    # (STORAGE_CHAT_ID) kullanılır ki oyunculara kartlar bot tarafından
    # "kendiliğinden" gönderiliyormuş gibi görünmesin.
    # STORAGE_CHAT_ID ayarlı değilse (önerilmez) oyunun kendi grubuna düşer.
    cache_chat_id = STORAGE_CHAT_ID or chat_id
    asyncio.create_task(prewarm_all_cards(context.bot, cache_chat_id, ALL_CARD_CODES))
    asyncio.create_task(get_local_icon_file_id(context.bot, PASS_ICON_CODE, pass_icon_bytes))
    asyncio.create_task(get_local_icon_file_id(context.bot, INFO_ICON_CODE, info_icon_bytes))
    asyncio.create_task(get_local_icon_file_id(context.bot, LOCKED_ICON_CODE, locked_icon_bytes))

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
    chat_id = query.message.chat.id if query.message else None
    user = query.from_user

    if query.data == "noop":
        await query.answer("Bu hamle geçersizdi, işlenmedi.", show_alert=True)
        return

    if query.data == "join":
        db.add_user(user.id, user.username, user.first_name)
        result = join_game(chat_id, user.id, user.first_name)
        if result is False or result == "ALREADY_JOINED":
            await query.answer("Zaten oyundasın.", show_alert=True)
            return
        if result == "NO_GAME":
            await query.answer("Oyun bulunamadı.", show_alert=True)
            return
        await query.answer()
        players = games[chat_id]["players"]
        text = f"🎴 <b>Meyus UNO Lobisi</b>\n\n"
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
        await query.answer("🎲 Oyun başlatılıyor...")
        await query.edit_message_text("🎲 Oyun başlatılıyor...")
        started = await _do_start_game(context, chat_id)
        if not started:
            await context.bot.send_message(
                chat_id,
                "❌ Oyun başlatılamadı. Lütfen /oyun ile yeni bir lobi oluşturun."
            )
        return

    if query.data.startswith("tema:"):
        _, theme_id = query.data.split(":", 1)
        theme = get_theme_by_id(theme_id)
        db.add_user(user.id, user.username, user.first_name)
        db.set_theme(user.id, theme["id"])
        await query.answer(f"Tema: {theme['name']}")

        rows = []
        row = []
        for t in THEMES:
            mark = " ✅" if t["id"] == theme["id"] else ""
            row.append(InlineKeyboardButton(f"{t['name']}{mark}", callback_data=f"tema:{t['id']}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        await query.edit_message_text(
            f"🎨 Tema güncellendi: <b>{theme['name']}</b>\n\n"
            f"Bir sonraki elini gördüğünde yeni temanla karşılaşacaksın.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
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
    db.add_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name
    )
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
# Bu, CARD_TO_STICKER_INDEX eşleşmesini oluşturmak için bir kereye mahsus
# kullanılır; sonrasında kaldırılabilir.
async def stickerlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /stickerlar <paket_adı> -> belirtilen paketi listeler (yeni tema eşlemesi
    # çıkarmak için). Argüman verilmezse varsayılan STICKER_SET_NAME kullanılır.
    pack_name = context.args[0] if context.args else STICKER_SET_NAME
    try:
        sticker_set = await get_sticker_set(context.bot, pack_name)
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

    if res.get("forced"):
        await update.message.reply_html(
            f"🃏 {actor_mention} ceza kartlarını çekti ({n} kart), sırası geçti."
            if n else f"🃏 {actor_mention} ceza kartlarını çekmek istedi ama deste boş."
        )
        if not game.get("winner"):
            await announce_turn(context, chat_id)
        return

    await update.message.reply_html(
        f"🃏 {actor_mention} kart çekti ({n} kart)."
        if n else f"🃏 {actor_mention} çekmek istedi ama deste boş."
    )
    if not game.get("winner"):
        await update.message.reply_html(
            f"Şimdi çektiğin kartı oynayabilir ya da /pas ile sırayı geçebilirsin.\n"
            f"Elini görmek için 🃏 butonuna dokun.",
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


# /profil
async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_obj = update.effective_user
    # Kullanıcı hiç /start yazmadan direkt /profil yazsa bile kayıt oluştursun.
    # INSERT OR IGNORE olduğu için zaten kayıtlıysa mevcut veriye dokunmaz.
    db.add_user(user_obj.id, user_obj.username, user_obj.first_name)

    user = db.get_user(user_obj.id)
    if not user:
        await update.message.reply_text("❌ Profil oluşturulamadı, tekrar dener misin?")
        return

    await update.message.reply_text(
        f"""👤 Profil
💰 Coin: {user[3]}
🏆 Galibiyet: {user[4]}
🎮 Oyun: {user[5]}
⭐ Seviye: {user[6]}
✨ XP: {user[7]}"""
    )


# /tema - kart görseli teması seç
async def tema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    current = db.get_theme(user.id)

    rows = []
    row = []
    for t in THEMES:
        mark = " ✅" if t["id"] == current else ""
        row.append(InlineKeyboardButton(f"{t['name']}{mark}", callback_data=f"tema:{t['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    await update.message.reply_text(
        "🎨 Kart görseli teman:\n\n"
        "Seçtiğin tema sadece sana özel görünür, diğer oyuncuları etkilemez.",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# /siralama - Türkiye saatine göre haftanın ilk 10 oyuncusu
async def siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = db.get_weekly_leaderboard(10)
    if not top:
        await update.message.reply_text("🎴 Bu hafta henüz kimse oyun bitirmedi.")
        return

    madalya = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Haftalık Sıralama</b> (ilk 10)\n"]
    for i, (uid, name, wins, played) in enumerate(top):
        rank = madalya[i] if i < 3 else f"{i + 1}."
        lines.append(f"{rank} {html_escape(name)} — 🏆 {wins} galibiyet ({played} oyun)")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


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

    # Oyuncunun kendi seçtiği tema (varsayılan: classic_colorblind)
    theme_id = db.get_theme(user.id)
    theme = get_theme_by_id(theme_id)
    theme_sticker_set = theme["sticker_set"]
    theme_card_map = get_card_map_for_theme(theme_id)

    results = []
    for idx, card_code in enumerate(hand):
        is_illegal = my_turn and card_code not in legal
        result_id_prefix = "illegal:" if is_illegal else ""

        if is_illegal:
            # O an oynanamayacak kartlar için gerçek görsel yerine tek tip
            # soluk/kilitli bir ikon gösteriyoruz. Böylece hangi kart olduğu
            # görsel olarak belirsizleşir ve "dokunulamaz" hissi verir
            # (Telegram inline sonuçları teknik olarak hep seçilebilir olsa
            # da, seçilse bile chosen_result bunu "illegal:" ön ekinden
            # tanıyıp oyuna hiçbir etkisi olmadan sessizce çıkar).
            try:
                locked_file_id = await get_local_icon_file_id(
                    context.bot, LOCKED_ICON_CODE, locked_icon_bytes()
                )
                results.append(
                    InlineQueryResultCachedPhoto(
                        id=f"{result_id_prefix}{card_code}#{idx}",
                        photo_file_id=locked_file_id,
                    )
                )
            except Exception as e:
                print(f"⚠️ Kilitli kart ikonu yüklenemedi: {e}")
            continue

        sticker_file_id = None

        if card_code in theme_card_map:
            try:
                sticker_file_id = await get_card_sticker_file_id(
                    context.bot, theme_sticker_set, card_code,
                    theme_card_map[card_code]
                )
            except Exception as e:
                print(f"⚠️ Sticker alınamadı ({theme_sticker_set}/{card_code}): {e}")

        if sticker_file_id:
            # title/description YOK -> Telegram bunu grid modunda (yan yana, yazısız) gösterir
            results.append(
                InlineQueryResultCachedSticker(
                    id=f"{result_id_prefix}{card_code}#{idx}",
                    sticker_file_id=sticker_file_id,
                )
            )
            continue

        try:
            file_id = await get_card_file_id(context.bot, card_code, cache_chat_id)
        except Exception as e:
            print(f"⚠️ Kart görseli yüklenemedi ({card_code}): {e}")
            continue

        # title/description YOK -> grid görünüm, kart üzerinde yazı yok
        results.append(
            InlineQueryResultCachedPhoto(
                id=f"{result_id_prefix}{card_code}#{idx}",
                photo_file_id=file_id,
            )
        )

    # ❓ Kart durumu bilgisi: sıra kimde olursa olsun her zaman gösterilir
    try:
        info_file_id = await get_local_icon_file_id(
            context.bot, INFO_ICON_CODE, info_icon_bytes
        )
        results.append(
            InlineQueryResultCachedPhoto(
                id="info",
                photo_file_id=info_file_id,
                # title/description YOK -> grid'e girer, sadece ikon görünür
            )
        )
    except Exception as e:
        print(f"⚠️ Bilgi ikonu yüklenemedi: {e}")
        results.append(
            InlineQueryResultArticle(
                id="info",
                title="❓",
                input_message_content=InputTextMessageContent("❓ kart durumu soruldu"),
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
                    # title/description YOK -> grid'e girer, sadece kart arkası görünür
                )
            )
        except Exception as e:
            print(f"⚠️ Deste görseli yüklenemedi: {e}")

        # Sadece kart çektikten sonra pas geçilebilir
        if has_drawn:
            try:
                pass_file_id = await get_local_icon_file_id(
                    context.bot, PASS_ICON_CODE, pass_icon_bytes
                )
                results.append(
                    InlineQueryResultCachedPhoto(
                        id="pass",
                        photo_file_id=pass_file_id,
                        # title/description YOK -> grid'e girer, sadece ikon görünür
                    )
                )
            except Exception as e:
                print(f"⚠️ Pas ikonu yüklenemedi: {e}")
                results.append(
                    InlineQueryResultArticle(
                        id="pass",
                        title="⏭",
                        input_message_content=InputTextMessageContent("⏭ pas geçildi"),
                    )
                )

    await inline_query.answer(results, cache_time=1, is_personal=True)


async def chosen_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    user = chosen.from_user
    result_id = chosen.result_id

    # Pasif/geçersiz kart seçildiyse: "⛔ geçersiz hamle" mesajı zaten
    # inline sonuç olarak gönderildi, oyuna hiçbir etkisi olmasın diye
    # burada sessizce çıkıyoruz.
    if result_id.startswith("illegal:"):
        return

    chat_id, game = find_active_game_for_user(user.id)
    if not game:
        return

    actor_mention = mention_html(user.id, player_name(game, user.id))

    if result_id == "info":
        lines = ["📊 <b>Kart Durumu</b>\n"]
        for p in game["players"]:
            count = len(game["hands"].get(p["id"], []))
            lines.append(f"• {html_escape(p['name'])}: {count} kart")
        await context.bot.send_message(
            chat_id,
            "\n".join(lines),
            parse_mode="HTML",
        )
        return

    if result_id == "draw":
        res = draw_card(chat_id, user.id)
        if not res["ok"]:
            return
        n = len(res["drawn"])

        if res.get("forced"):
            await context.bot.send_message(
                chat_id,
                f"🃏 {actor_mention} ceza kartlarını çekti ({n} kart), sırası geçti."
                if n else f"🃏 {actor_mention} ceza kartlarını çekmek istedi ama deste boş.",
                parse_mode="HTML",
            )
            if not game.get("winner"):
                await announce_turn(context, chat_id)
            return

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
        # Gruba bildirim göndermek yerine, mesajın üzerine küçük bir
        # "❌ Geçersiz" etiketi ekleyip kartı işlevsiz bırakıyoruz.
        # (Telegram inline mesajı seçildiği an gönderdiği için mesajın
        # kendisini engellemek mümkün değil, sadece işaretleyebiliyoruz.)
        if chosen.inline_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    inline_message_id=chosen.inline_message_id,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("❌ Geçersiz hamle", callback_data="noop")]]
                    ),
                )
            except Exception as e:
                print(f"⚠️ Geçersiz kart işaretlenemedi: {e}")
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
    elif res["effect"] == "draw2":
        await announce_effect(
            context, chat_id, actor_mention, res["effect"],
            stacked_total=res.get("stacked_total")
        )
    elif res["effect"] == "draw4":
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


async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """📋 Yardım

/start - Botu başlatır
/oyun - Yeni oyun oluşturur
/katil - Oyuna katılır
/baslat - Oyunu başlatır
/bitir - Oyunu/lobiyi sonlandırır (oyunu açan veya yöneticiler)
/profil - Profilini gösterir
/tema - Kart görseli temanı seçmeni sağlar (kişisel, sadece sende görünür)
/siralama - Haftalık ilk 10 sıralaması (Türkiye saatine göre)
/cek - Sıra sendeyken kart çeker
/pas - Kart çektikten sonra sırayı geçer

🃏 Her an "Kartlarımı Gör / Oyna" butonuna dokunarak elini görebilirsin.
Sıra sende olduğunda aynı buton oynanabilir kartları, kart çekme ve pas
geçme seçeneklerini listeler, seçtiğin otomatik uygulanır."""
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
                "Devam etmek için tekrar 🃏 Kartlarımı Gör / Oyna butonuna dokunabilirsiniz.",
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
    app.add_handler(CommandHandler("tema", tema))
    app.add_handler(CommandHandler("siralama", siralama))
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
