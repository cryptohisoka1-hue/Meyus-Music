import asyncio

from game import *
from cards_data import (
    card_display_label,
    COLOR_NAME_TR,
    COLOR_LABELS,
    ALL_CARD_CODES,
)
from sticker_cache import (
    load_uno_stickers,
    get_card_sticker,
)
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedSticker,
    InlineQueryResultArticle,
    InputTextMessageContent,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
)
from config import BOT_TOKEN
from database import db


# ============================================================
# AYARLAR
# ============================================================

UNO_STICKER_SET = "UnoCardsDeck"


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def player_name(game, uid):
    for p in game["players"]:
        if p["id"] == uid:
            return p["name"]
    return "?"


def mention_html(uid, name):
    safe_name = (
        str(name)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return f'<a href="tg://user?id={uid}">{safe_name}</a>'


HAND_BUTTON = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "🎴 Kartlarımı Gör / Oyna",
            switch_inline_query_current_chat=""
        )
    ]
])


# ============================================================
# KART INDEX BULMA
# ============================================================

def card_index(card_code):
    """
    cards_data.py içindeki ALL_CARD_CODES sırasına göre
    kartın sticker paketindeki indexini bulur.
    """

    try:
        return ALL_CARD_CODES.index(card_code)
    except ValueError:
        return None


# ============================================================
# TUR DUYURUSU
# ============================================================

async def announce_turn(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id
):
    game = games.get(chat_id)

    if not game:
        return

    if not game.get("started"):
        return

    if game.get("winner"):
        return

    uid = current_player(chat_id)
    name = player_name(game, uid)

    color_tr = COLOR_NAME_TR.get(
        game["top_color"],
        game["top_color"]
    )

    await context.bot.send_message(
        chat_id,
        (
            f"🔁 Sıra sende "
            f"{mention_html(uid, name)}!\n\n"
            f"🎨 Geçerli renk: <b>{color_tr}</b>\n\n"
            f"🎴 Kartlarını görmek ve oynamak için "
            f"aşağıdaki butona dokun 👇"
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )


# ============================================================
# KART ETKİSİ DUYURUSU
# ============================================================

async def announce_effect(
    context,
    chat_id,
    actor_mention,
    effect,
    next_mention=None
):

    texts = {
        "skip":
            f"⛔ {actor_mention} DUR kartı oynadı, sıra atlandı!",

        "reverse":
            f"🔄 {actor_mention} YÖN kartı oynadı, yön değişti!",

        "draw2":
            f"➕2️⃣ {actor_mention} +2 oynadı, "
            f"{next_mention} 2 kart çekip sırasını kaçırdı!",

        "draw4":
            f"➕4️⃣ {actor_mention} +4 oynadı, "
            f"{next_mention} 4 kart çekip sırasını kaçırdı!",
    }

    text = texts.get(effect)

    if text:
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML"
        )


# ============================================================
# OYUN BİTİRME
# ============================================================

async def finish_game(
    context,
    chat_id,
    winner_uid
):

    game = games.get(chat_id)

    if not game:
        return

    winner_mention = mention_html(
        winner_uid,
        player_name(game, winner_uid)
    )

    db.add_win(winner_uid)
    db.add_coin(winner_uid, 50)
    db.add_xp(winner_uid, 30)

    for p in game["players"]:
        db.add_game(p["id"])

    user = db.get_user(winner_uid)

    level = user[6] if user else 1
    xp = user[7] if user else 0

    await context.bot.send_message(
        chat_id,
        (
            f"🏆 {winner_mention} "
            f"<b>oyunu kazandı!</b> 🎉\n\n"
            f"🪙 +50 coin\n"
            f"✨ +30 XP\n\n"
            f"⭐ Seviye: {level}\n"
            f"✨ XP: {xp}\n\n"
            f"🎮 Yeni oyun için /oyun yazabilirsiniz."
        ),
        parse_mode="HTML"
    )

    end_game(chat_id)


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

Arkadaşlarınla Telegram üzerinden
UNO oynayabilirsin.

📌 <b>Komutlar</b>

/oyun - Yeni oyun oluştur
/katil - Oyuna katıl
/baslat - Oyunu başlat
/bitir - Oyunu/lobiyi sonlandır
/profil - Profilin
/yardim - Yardım

🃏 <b>Kartlarımı Gör / Oyna</b>
butonuna dokunarak elindeki kartları görebilirsin.

Oynanabilir kartlar otomatik olarak gösterilir.

İyi eğlenceler ❤️
"""

    await update.message.reply_html(text)


# ============================================================
# OYUN OLUŞTUR
# ============================================================

async def oyun(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat
    user = update.effective_user

    if not create_game(
        chat.id,
        user.id
    ):
        await update.message.reply_text(
            "❌ Bu grupta zaten açık bir oyun var."
        )
        return

    join_game(
        chat.id,
        user.id,
        user.first_name
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Katıl",
                callback_data="join"
            )
        ],
        [
            InlineKeyboardButton(
                "▶️ Başlat",
                callback_data="start_game"
            )
        ]
    ]

    msg = await update.message.reply_text(
        (
            "🎮 <b>Meyus UNO Lobisi</b>\n\n"
            "👤 Oyuncular (1)\n"
            f"• {user.first_name}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    lobby_messages[chat.id] = msg.message_id


# ============================================================
# OYUNU BAŞLAT
# ============================================================

async def _do_start_game(
    context,
    chat_id
):

    game = start_game(chat_id)

    if not game:
        await context.bot.send_message(
            chat_id,
            "❌ Oyun başlatılamadı."
        )
        return

    t_card = top_card(chat_id)

    color_tr = COLOR_NAME_TR.get(
        game["top_color"],
        game["top_color"]
    )

    index = card_index(t_card)

    if index is not None:

        sticker_id = await get_card_sticker(
            context.bot,
            index
        )

        if sticker_id:

            await context.bot.send_sticker(
                chat_id,
                sticker=sticker_id
            )

    await context.bot.send_message(
        chat_id,
        (
            "🚀 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: "
            f"<b>{color_tr}</b>\n\n"
            "🎴 Herkes istediği zaman "
            "elini görebilir.\n\n"
            "⚡ Sadece sırası gelen oyuncu "
            "kart oynayabilir."
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON
    )

    await announce_turn(
        context,
        chat_id
    )


# ============================================================
# BUTONLAR
# ============================================================

async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user

    # --------------------------------------------------------
    # KATIL
    # --------------------------------------------------------

    if query.data == "join":

        result = join_game(
            chat_id,
            user.id,
            user.first_name
        )

        if result is False or result == "ALREADY_JOINED":

            await query.answer(
                "Zaten oyundasın.",
                show_alert=True
            )
            return

        if result == "NO_GAME":

            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True
            )
            return

        players = games[chat_id]["players"]

        text = (
            "🎮 <b>Meyus UNO Lobisi</b>\n\n"
            f"👥 Oyuncular ({len(players)})\n\n"
        )

        for p in players:
            text += f"• {p['name']}\n"

        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Katıl",
                    callback_data="join"
                )
            ],
            [
                InlineKeyboardButton(
                    "▶️ Başlat",
                    callback_data="start_game"
                )
            ]
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # --------------------------------------------------------
    # OYUNU BAŞLAT
    # --------------------------------------------------------

    if query.data == "start_game":

        if chat_id not in games:

            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True
            )
            return

        if len(games[chat_id]["players"]) < 2:

            await query.answer(
                "En az 2 oyuncu gerekli.",
                show_alert=True
            )
            return

        await query.answer(
            "🚀 Oyun başlatılıyor..."
        )

        await query.edit_message_text(
            "🚀 Oyun başlatılıyor..."
        )

        await _do_start_game(
            context,
            chat_id
        )

        return

    # --------------------------------------------------------
    # RENK SEÇ
    # --------------------------------------------------------

    if query.data.startswith("renk:"):

        _, color, target_uid = query.data.split(":")

        target_uid = int(target_uid)

        if user.id != target_uid:

            await query.answer(
                "Sadece kartı oynayan kişi "
                "rengi seçebilir.",
                show_alert=True
            )
            return

        ok = choose_color(
            chat_id,
            user.id,
            color
        )

        if not ok:

            await query.answer(
                "Bu işlem artık geçerli değil.",
                show_alert=True
            )
            return

        await query.answer(
            f"Renk: {COLOR_NAME_TR.get(color, color)}"
        )

        await query.edit_message_reply_markup(
            reply_markup=None
        )

        game = games[chat_id]

        await context.bot.send_message(
            chat_id,
            (
                f"🎨 {mention_html(user.id, player_name(game, user.id))} "
                f"rengi "
                f"<b>{COLOR_NAME_TR.get(color, color)}</b> seçti."
            ),
            parse_mode="HTML"
        )

        if game.get("winner"):

            await finish_game(
                context,
                chat_id,
                game["winner"]
            )

        else:

            await announce_turn(
                context,
                chat_id
            )

        return


# ============================================================
# KATIL KOMUTU
# ============================================================

async def katil(
    update,
    context
):

    result = join_game(
        update.effective_chat.id,
        update.effective_user.id,
        update.effective_user.first_name
    )

    if result == "NO_GAME":

        await update.message.reply_text(
            "❌ Önce /oyun komutu ile "
            "bir oyun oluşturulmalı."
        )
        return

    if result == "ALREADY_JOINED":

        await update.message.reply_text(
            "ℹ️ Zaten oyuna katıldın."
        )
        return

    db.add_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username
    )

    oyuncu = len(
        games[
            update.effective_chat.id
        ]["players"]
    )

    await update.message.reply_text(
        (
            f"✅ {update.effective_user.first_name} "
            f"oyuna katıldı!\n\n"
            f"👥 Toplam oyuncu: {oyuncu}"
        )
    )


# ============================================================
# BAŞLAT KOMUTU
# ============================================================

async def baslat(
    update,
    context
):

    chat_id = update.effective_chat.id

    if chat_id not in games:

        await update.message.reply_text(
            "❌ Önce /oyun oluştur."
        )
        return

    if len(games[chat_id]["players"]) < 2:

        await update.message.reply_text(
            "❌ En az 2 oyuncu gerekli."
        )
        return

    await _do_start_game(
        context,
        chat_id
    )


# ============================================================
# INLINE EL
# ============================================================

async def inline_hand(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    inline_query = update.inline_query
    user = inline_query.from_user

    chat_id, game = find_active_game_for_user(
        user.id
    )

    if not game:

        await inline_query.answer(
            [],
            switch_pm_text="Aktif bir oyunda değilsin",
            switch_pm_parameter="no_game",
            cache_time=1,
            is_personal=True
        )

        return

    my_turn = (
        current_player(chat_id) == user.id
    )

    hand = game["hands"].get(
        user.id,
        []
    )

    legal = (
        set(
            legal_cards_for(
                chat_id,
                user.id
            )
        )
        if my_turn
        else set()
    )

    tasks = []

    for card_code in hand:

        index = card_index(card_code)

        if index is None:

            tasks.append(
                asyncio.sleep(
                    0,
                    result=None
                )
            )

        else:

            tasks.append(
                get_card_sticker(
                    context.bot,
                    index
                )
            )

    file_ids = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    playable_results = []
    unplayable_results = []

    for idx, (card_code, file_id) in enumerate(
        zip(hand, file_ids)
    ):

        if isinstance(file_id, Exception):
            continue

        if not file_id:
            continue

        # ----------------------------------------------------
        # OYNANABİLİR KART
        # ----------------------------------------------------

        if my_turn and card_code in legal:

            playable_results.append(
                InlineQueryResultCachedSticker(
                    id=f"{card_code}#{idx}",
                    sticker_file_id=file_id,
                    title=(
                        f"✅ "
                        f"{card_display_label(card_code)}"
                    )
                )
            )

        # ----------------------------------------------------
        # OYNANAMAYAN KART
        # ----------------------------------------------------

        else:

            unplayable_results.append(
                InlineQueryResultCachedSticker(
                    id=f"{card_code}#{idx}",
                    sticker_file_id=file_id,
                    title=(
                        f"🚫 "
                        f"{card_display_label(card_code)}"
                    )
                )
            )

    results = (
        playable_results +
        unplayable_results
    )

    # ========================================================
    # KART ÇEK
    # ========================================================

    if my_turn:

        results.append(
            InlineQueryResultArticle(
                id="draw",
                title="🂠 Kart Çek",
                description="Desteden 1 kart çek",
                input_message_content=
                InputTextMessageContent(
                    "🂠 Kart çekiyorum."
                )
            )
        )

        # ----------------------------------------------------
        # PAS
        # ----------------------------------------------------

        has_drawn = (
            game
            .get("has_drawn", {})
            .get(user.id, False)
        )

        if has_drawn:

            results.append(
                InlineQueryResultArticle(
                    id="pass",
                    title="⏭ Pas Geç",
                    description=(
                        "Kart çektin, "
                        "oynamak istemiyorsan pas geç"
                    ),
                    input_message_content=
                    InputTextMessageContent(
                        "⏭ Pas geçiyorum."
                    )
                )
            )

    await inline_query.answer(
        results,
        cache_time=1,
        is_personal=True
    )


# ============================================================
# CHOSEN INLINE RESULT
# ============================================================

async def chosen_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chosen = update.chosen_inline_result

    user = chosen.from_user

    result_id = chosen.result_id

    chat_id, game = find_active_game_for_user(
        user.id
    )

    if not game:
        return

    if current_player(chat_id) != user.id:
        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id)
    )

    # ========================================================
    # KART ÇEK
    # ========================================================

    if result_id == "draw":

        res = draw_card(
            chat_id,
            user.id
        )

        if not res["ok"]:
            return

        n = len(
            res.get("drawn", [])
        )

        if n:

            text = (
                f"🂠 {actor_mention} "
                f"kart çekti ({n} kart)."
            )

        else:

            text = (
                f"🂠 {actor_mention} "
                f"çekmek istedi ama deste boş."
            )

        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML"
        )

        if not game.get("winner"):

            await announce_turn(
                context,
                chat_id
            )

        return

    # ========================================================
    # PAS
    # ========================================================

    if result_id == "pass":

        res = pass_turn(
            chat_id,
            user.id
        )

        if not res["ok"]:
            return

        await context.bot.send_message(
            chat_id,
            f"⏭ {actor_mention} pas geçti.",
            parse_mode="HTML"
        )

        if not game.get("winner"):

            await announce_turn(
                context,
                chat_id
            )

        return

    # ===================
