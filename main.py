import asyncio
import io

from PIL import Image, ImageEnhance

from game import (
    games,
    lobby_messages,
    user_active_chat,
    create_game,
    join_game,
    start_game,
    top_card,
    current_player,
    legal_cards_for,
    draw_card,
    pass_turn,
    play_card,
    choose_color,
    end_game,
    find_active_game_for_user,
)

from cards_data import (
    card_display_label,
    DECK_BACK_CODE,
    COLOR_NAME_TR,
    COLOR_LABELS,
    ALL_CARD_CODES,
)

from card_cache import (
    get_card_file_id,
    prewarm_all_cards,
)

from sticker_cache import (
    get_sticker_set,
    get_card_sticker_file_id,
)

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

from config import (
    BOT_TOKEN,
    STORAGE_CHAT_ID,
    STICKER_SET_NAME,
)

from database import db


# =========================================================
# KART TEMALARI
# =========================================================

CARD_THEMES = {
    "meyus": {
        "name": "🌈 Meyus UNO",
        "sticker_set": STICKER_SET_NAME,
    },

    "wolf_arya": {
        "name": "🐺 Wolf Arya",
        "sticker_set": "wolf_arya",
    },

    "arya_winnie": {
        "name": "🧸 Arya Winnie",
        "sticker_set": "arya_winnie_theme_pack",
    },

    "arya_sincap": {
        "name": "🐿️ Arya Sincap",
        "sticker_set": "arya_sincap_theme_pack",
    },

    "arya_fb": {
        "name": "⚽ Arya FB",
        "sticker_set": "arya_fb_theme_pack",
    },
}


def get_user_theme(user_id):
    try:
        theme = db.get_theme(user_id)

        if theme in CARD_THEMES:
            return theme

    except Exception as e:
        print(f"⚠️ Tema okunamadı: {e}")

    return "meyus"


def theme_keyboard():

    rows = []

    for theme_id, theme in CARD_THEMES.items():

        rows.append([
            InlineKeyboardButton(
                theme["name"],
                callback_data=f"theme:{theme_id}"
            )
        ])

    return InlineKeyboardMarkup(rows)

# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def player_name(game, uid):
    for p in game["players"]:
        if p["id"] == uid:
            return p["name"]
    return "?"


def html_escape(value):
    value = "" if value is None else str(value)

    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def mention_html(uid, name):
    return f'<a href="tg://user?id={uid}">{html_escape(name)}</a>'


def get_user_theme(user_id):
    try:
        theme = db.get_theme(user_id)

        if theme in CARD_THEMES:
            return theme

    except Exception as e:
        print(f"⚠️ Tema okunamadı: {e}")

    return "meyus"


def get_theme_info(user_id):
    theme_id = get_user_theme(user_id)
    return theme_id, CARD_THEMES[theme_id]


def theme_keyboard():
    rows = []

    for theme_id, theme in CARD_THEMES.items():
        rows.append([
            InlineKeyboardButton(
                theme["name"],
                callback_data=f"theme:{theme_id}"
            )
        ])

    return InlineKeyboardMarkup(rows)


HAND_BUTTON = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "🎴 Kartlarımı Gör / Oyna",
            switch_inline_query_current_chat=""
        )
    ]
])


# =========================================================
# SİLİK KART GÖRSELİ
# =========================================================

async def tema(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    try:
        db.get_or_create_user(
            user.id,
            user.username,
            user.first_name
        )
    except Exception:
        pass

    current = get_user_theme(user.id)

    await update.message.reply_text(
        "🎨 <b>Meyus UNO Kart Teması</b>\n\n"
        f"Şu anki teman: <b>{CARD_THEMES[current]['name']}</b>\n\n"
        "Kartlarının görünmesini istediğin temayı seç:",
        parse_mode="HTML",
        reply_markup=theme_keyboard()
    )

async def theme_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    user = query.from_user

    await query.answer()

    theme_id = query.data.split(":", 1)[1]

    if theme_id not in CARD_THEMES:

        await query.answer(
            "❌ Tema bulunamadı.",
            show_alert=True
        )

        return

    try:

        db.set_theme(
            user.id,
            theme_id
        )

    except Exception as e:

        print(f"⚠️ Tema kaydedilemedi: {e}")

        await query.answer(
            "❌ Tema kaydedilemedi.",
            show_alert=True
        )

        return

    theme_name = CARD_THEMES[
        theme_id
    ]["name"]

    await query.edit_message_text(
        f"✅ <b>Tema değiştirildi!</b>\n\n"
        f"🎨 {theme_name}\n\n"
        "🎴 Kartlarını görmek için aşağıdaki butona dokun.",
        parse_mode="HTML",
        reply_markup=HAND_BUTTON
    )

async def get_dimmed_card_file_id(
    bot,
    card_code,
    normal_file_id,
    storage_chat_id
):
    """
    Oynanamayan kartı gri/silik hale getirir.

    Telegram inline sonuçlarında opacity özelliği olmadığı için
    kart görselini indirip karartıyoruz ve Telegram'a bir kez
    yükleyerek file_id'sini cache'liyoruz.
    """

    cache_key = card_code

    if cache_key in DIMMED_FILE_IDS:
        return DIMMED_FILE_IDS[cache_key]

    try:
        telegram_file = await bot.get_file(normal_file_id)

        image_bytes = await telegram_file.download_as_bytearray()

        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

        # Önce parlaklığı azalt
        image = ImageEnhance.Brightness(image).enhance(0.48)

        # Hafif desatürasyon
        image = ImageEnhance.Color(image).enhance(0.35)

        output = io.BytesIO()

        image.save(
            output,
            format="PNG",
            optimize=True
        )

        output.seek(0)

        message = await bot.send_photo(
            chat_id=storage_chat_id,
            photo=output,
        )

        if not message.photo:
            return normal_file_id

        dimmed_file_id = message.photo[-1].file_id

        DIMMED_FILE_IDS[cache_key] = dimmed_file_id

        return dimmed_file_id

    except Exception as e:
        print(
            f"⚠️ Silik kart oluşturulamadı "
            f"({card_code}): {e}"
        )

        return normal_file_id


# =========================================================
# SIRA DUYURUSU
# =========================================================

async def announce_turn(context, chat_id):

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

    top_label = card_display_label(
        top_card(chat_id)
    )

    await context.bot.send_message(
        chat_id,

        f"🎯 Sıra sende "
        f"{mention_html(uid, name)}!\n"
        f"🎴 Son atılan kart: "
        f"<b>{top_label}</b>\n"
        f"🎨 Geçerli renk: "
        f"<b>{color_tr}</b>\n\n"
        f"Aşağıdaki butona dokun, "
        f"kartların otomatik açılsın 🎴",

        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )


# =========================================================
# KART ETKİSİ
# =========================================================

async def announce_effect(
    context,
    chat_id,
    actor_mention,
    effect,
    next_mention=None
):

    texts = {
        "skip":
            f"⛔ {actor_mention} "
            f"DUR kartı oynadı, sıra atlandı!",

        "reverse":
            f"🔄 {actor_mention} "
            f"YÖN kartı oynadı, yön değişti!",

        "draw2":
            f"➕2️⃣ {actor_mention} +2 oynadı, "
            f"{next_mention} ceza kartlarını çekip "
            f"sırasını kaçırdı!",

        "draw4":
            f"➕4️⃣ {actor_mention} +4 oynadı, "
            f"{next_mention} ceza kartlarını çekip "
            f"sırasını kaçırdı!",
    }

    text = texts.get(effect)

    if text:
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML"
        )


# =========================================================
# OYUN BİTİR
# =========================================================

async def finish_game(
    context,
    chat_id,
    winner_uid
):

    game = games[chat_id]

    winner_mention = mention_html(
        winner_uid,
        player_name(game, winner_uid)
    )

    winner_name = player_name(
        game,
        winner_uid
    )

    db.add_win(
        winner_uid,
        winner_name
    )

    for p in game["players"]:
        db.add_game(
            p["id"],
            p["name"]
        )

    db.add_coin(
        winner_uid,
        50
    )

    db.add_xp(
        winner_uid,
        30
    )

    await context.bot.send_message(
        chat_id,

        f"🏆 {winner_mention} "
        f"oyunu kazandı! 🎉\n\n"
        f"💰 +50 coin\n"
        f"⭐ +30 XP\n\n"
        f"Yeni oyun için /oyun",

        parse_mode="HTML"
    )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    db.get_or_create_user(
        user.id,
        user.username,
        user.first_name
    )

    text = (
        f"🎮 <b>MEYUS UNO</b>\n\n"
        f"Merhaba "
        f"<b>{html_escape(user.first_name)}</b>! 🎉\n\n"
        f"Meyus UNO'ya hoş geldin.\n\n"
        f"📜 <b>Komutlar</b>\n\n"
        f"/start - Botu başlat\n"
        f"/yardim - Yardım\n"
        f"/oyun - Yeni oyun\n"
        f"/katil - Oyuna katıl\n"
        f"/baslat - Oyunu başlat\n"
        f"/bitir - Oyunu/lobiyi sonlandır\n"
        f"/profil - Profilin\n"
        f"/tema - Kart temasını seç\n"
        f"/cek - Kart çek\n"
        f"/pas - Pas geç\n\n"
        f"🎨 /tema ile kart görünümünü "
        f"kişiselleştirebilirsin.\n\n"
        f"🎴 Kartlarımı Gör / Oyna butonuyla "
        f"kartlarını açabilirsin."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# /TEMA
# =========================================================

async def tema(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    db.get_or_create_user(
        user.id,
        user.username,
        user.first_name
    )

    current_theme = get_user_theme(
        user.id
    )

    current_name = CARD_THEMES[
        current_theme
    ]["name"]

    await update.message.reply_text(
        f"🎨 <b>Kart Teması</b>\n\n"
        f"Şu an kullandığın tema:\n"
        f"<b>{current_name}</b>\n\n"
        f"👇 Kullanmak istediğin temayı seç:",
        parse_mode="HTML",
        reply_markup=theme_keyboard()
    )


# =========================================================
# TEMA CALLBACK
# =========================================================

async def theme_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    theme_id = query.data.split(
        ":",
        1
    )[1]

    if theme_id not in CARD_THEMES:
        await query.answer(
            "❌ Tema bulunamadı.",
            show_alert=True
        )
        return

    try:
        db.get_or_create_user(
            user.id,
            user.username,
            user.first_name
        )

        db.set_theme(
            user.id,
            theme_id
        )

    except Exception as e:

        print(
            f"⚠️ Tema kaydedilemedi: {e}"
        )

        await query.answer(
            "❌ Tema kaydedilemedi.",
            show_alert=True
        )

        return

    selected = CARD_THEMES[
        theme_id
    ]["name"]

    await query.edit_message_text(
        f"✅ <b>Tema değiştirildi!</b>\n\n"
        f"🎨 Yeni tema: "
        f"<b>{selected}</b>\n\n"
        f"🎴 Kartlarını görmek için "
        f"butona dokun.",
        parse_mode="HTML",
        reply_markup=HAND_BUTTON
    )


# =========================================================
# /OYUN
# =========================================================

async def oyun(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat
    user = update.effective_user

    db.get_or_create_user(
        user.id,
        user.username,
        user.first_name
    )

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
        f"🎮 <b>Meyus UNO Lobisi</b>\n\n"
        f"👥 Oyuncular (1)\n\n"
        f"• {html_escape(user.first_name)}",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),

        parse_mode="HTML"
    )

    lobby_messages[
        chat.id
    ] = msg


# =========================================================
# OYUNU BAŞLAT
# =========================================================

async def _do_start_game(
    context,
    chat_id
):

    if chat_id not in games:
        return False

    game_before = games[
        chat_id
    ]

    if game_before.get("started"):
        return False

    game = start_game(
        chat_id
    )

    if not game:
        return False

    t_card = top_card(
        chat_id
    )

    color_tr = COLOR_NAME_TR.get(
        game["top_color"],
        game["top_color"]
    )

    cache_chat_id = (
        STORAGE_CHAT_ID
        or chat_id
    )

    asyncio.create_task(
        prewarm_all_cards(
            context.bot,
            cache_chat_id,
            ALL_CARD_CODES
        )
    )

    file_id = await get_card_file_id(
        context.bot,
        t_card,
        cache_chat_id
    )

    await context.bot.send_photo(
        chat_id,
        photo=file_id,

        caption=(
            f"🎉 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: "
            f"<b>{color_tr}</b>\n\n"
            f"Herkes istediği zaman "
            f"elini görebilir.\n"
            f"Sadece sırası gelen oynayabilir."
        ),

        parse_mode="HTML",
        reply_markup=HAND_BUTTON
    )

    await announce_turn(
        context,
        chat_id
    )

    return True


# =========================================================
# BUTONLAR
# =========================================================

async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    chat_id = (
        query.message.chat.id
        if query.message
        else None
    )

    user = query.from_user

    # -----------------------------------------------------
    # NOOP
    # -----------------------------------------------------

    if query.data == "noop":

        await query.answer(
            "Bu hamle geçersizdi.",
            show_alert=True
        )

        return

    if query.data.startswith("theme:"):

    await theme_callback(
        update,
        context
    )

    return

    # -----------------------------------------------------
    # TEMA
    # -----------------------------------------------------

    if query.data.startswith("theme:"):

        await theme_callback(
            update,
            context
        )

        return

    # -----------------------------------------------------
    # JOIN
    # -----------------------------------------------------

    if query.data == "join":

        result = join_game(
            chat_id,
            user.id,
            user.first_name
        )

        if (
            result is False
            or result == "ALREADY_JOINED"
        ):

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

        await query.answer()

        players = games[
            chat_id
        ]["players"]

        text = (
            f"🎮 <b>Meyus UNO Lobisi</b>\n\n"
            f"👥 Oyuncular "
            f"({len(players)})\n\n"
        )

        for p in players:

            text += (
                f"• "
                f"{html_escape(p['name'])}\n"
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

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # -----------------------------------------------------
    # START GAME
    # -----------------------------------------------------

    if query.data == "start_game":

        if chat_id not in games:

            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True
            )

            return

        if games[
            chat_id
        ].get("started"):

            await query.answer(
                "Oyun zaten başladı.",
                show_alert=True
            )

            return

        if len(
            games[chat_id]["players"]
        ) < 2:

            await query.answer(
                "En az 2 oyuncu gerekli.",
                show_alert=True
            )

            return

        await query.answer(
            "🎉 Oyun başlatılıyor..."
        )

        await query.edit_message_text(
            "🎉 Oyun başlatılıyor..."
        )

        started = await _do_start_game(
            context,
            chat_id
        )

        if not started:

            await context.bot.send_message(
                chat_id,
                "❌ Oyun başlatılamadı."
            )

        return

    # -----------------------------------------------------
    # RENK
    # -----------------------------------------------------

    if query.data.startswith("renk:"):

        _, color, target_uid = (
            query.data.split(":")
        )

        target_uid = int(
            target_uid
        )

        if user.id != target_uid:

            await query.answer(
                "Sadece kartı oynayan kişi "
                "renk seçebilir.",
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
            f"Renk: "
            f"{COLOR_NAME_TR.get(color, color)}"
        )

        game = games[
            chat_id
        ]

        await context.bot.send_message(
            chat_id,

            f"🎨 "
            f"{mention_html(user.id, player_name(game, user.id))} "
            f"rengi "
            f"<b>{COLOR_NAME_TR.get(color, color)}</b> "
            f"seçti.",

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


# =========================================================
# /KATIL
# =========================================================

async def katil(
    update,
    context
):

    user = update.effective_user

    db.get_or_create_user(
        user.id,
        user.username,
        user.first_name
    )

    result = join_game(
        update.effective_chat.id,
        user.id,
        user.first_name
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

    oyuncu = len(
        games[
            update.effective_chat.id
        ]["players"]
    )

    await update.message.reply_text(
        f"✅ "
        f"{html_escape(user.first_name)} "
        f"oyuna katıldı!\n\n"
        f"👥 Toplam oyuncu: "
        f"{oyuncu}",

        parse_mode="HTML"
    )


# =========================================================
# /BAŞLAT
# =========================================================

async def baslat(
    update,
    context
):

    chat_id = update.effective_chat.id

    if chat_id not in games:

        await update.message.reply_text(
            "Önce /oyun oluştur."
        )

        return

    if games[
        chat_id
    ].get("started"):

        await update.message.reply_text(
            "ℹ️ Oyun zaten başladı."
        )

        return

    if len(
        games[chat_id]["players"]
    ) < 2:

        await update.message.reply_text(
            "En az 2 oyuncu gerekli."
        )

        return

    started = await _do_start_game(
        context,
        chat_id
    )

    if not started:

        await update.message.reply_text(
            "❌ Oyun başlatılamadı."
        )


# =========================================================
# /STICKERLAR
# =========================================================

async def stickerlar(
    update,
    context
):

    try:

        sticker_set = await get_sticker_set(
            context.bot,
            STICKER_SET_NAME
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Sticker paketi alınamadı: {e}"
        )

        return

    lines = [
        f"📦 Paket: "
        f"{sticker_set.name} "
        f"({len(sticker_set.stickers)} sticker)\n"
    ]

    for idx, s in enumerate(
        sticker_set.stickers
    ):

        lines.append(
            f"{idx}: "
            f"{s.emoji or '—'}"
        )

    text = "\n".join(lines)

    for i in range(
        0,
        len(text),
        3500
    ):

        await update.message.reply_text(
            text[i:i + 3500]
        )


# =========================================================
# /CEK
# =========================================================

async def cek(
    update,
    context
):

    user = update.effective_user

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    if not game:

        await update.message.reply_text(
            "❌ Aktif bir oyunda değilsin."
        )

        return

    if chat_id != update.effective_chat.id:

        await update.message.reply_text(
            "❌ Bu komutu oynadığın "
            "oyunun grubunda kullan."
        )

        return

    if current_player(chat_id) != user.id:

        await update.message.reply_text(
            "⏳ Sıra sende değil."
        )

        return

    res = draw_card(
        chat_id,
        user.id
    )

    if not res["ok"]:

        await update.message.reply_text(
            "❌ Kart çekilemedi."
        )

        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id)
    )

    n = len(
        res["drawn"]
    )

    await update.message.reply_html(
        (
            f"🃏 {actor_mention} "
            f"kart çekti ({n} kart)."
        )
        if n
        else
        (
            f"🃏 {actor_mention} "
            f"çekmek istedi ama deste boş."
        )
    )

    if not game.get("winner"):

        await update.message.reply_html(
            "Şimdi çektiğin kartı oynayabilir "
            "ya da /pas ile sırayı geçebilirsin.\n"
            "Elini görmek için 🎴 butonuna dokun."
        )


# =========================================================
# /PAS
# =========================================================

async def pas(
    update,
    context
):

    user = update.effective_user

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    if not game:

        await update.message.reply_text(
            "❌ Aktif bir oyunda değilsin."
        )

        return

    if chat_id != update.effective_chat.id:

        await update.message.reply_text(
            "❌ Bu komutu oynadığın "
            "oyunun grubunda kullan."
        )

        return

    res = pass_turn(
        chat_id,
        user.id
    )

    if not res["ok"]:

        reasons = {
            "SIRA_DEGIL":
                "⏳ Sıra sende değil.",

            "ONCE_CEK":
                "❌ Pas geçmeden önce "
                "kart çekmelisin (/cek).",

            "OYUN_YOK":
                "❌ Aktif bir oyun bulunamadı.",
        }

        await update.message.reply_text(
            reasons.get(
                res["reason"],
                "❌ Pas geçilemedi."
            )
        )

        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id)
    )

    await context.bot.send_message(
        chat_id,

        f"⏭ {actor_mention} pas geçti.",

        parse_mode="HTML"
    )

    await announce_turn(
        context,
        chat_id
    )


# =========================================================
# INLINE KARTLAR
# =========================================================

async def inline_hand(
    update,
    context
):

    inline_query = update.inline_query

    user = inline_query.from_user

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    if not game:

        await inline_query.answer(
            [],
            switch_pm_text=(
                "Aktif bir oyunda değilsin"
            ),
            switch_pm_parameter="no_game",
            cache_time=1,
            is_personal=True
        )

        return

    my_turn = (
        current_player(chat_id)
        == user.id
    )

    hand = game[
        "hands"
    ].get(
        user.id,
        []
    )

    legal = set(
        legal_cards_for(
            chat_id,
            user.id
        )
    ) if my_turn else set()

    cache_chat_id = (
        STORAGE_CHAT_ID
        or chat_id
    )

    theme_id, theme = (
        get_theme_info(
            user.id
        )
    )

    sticker_set_name = (
        theme["sticker_set"]
    )

    results = []

    # -----------------------------------------------------
    # KARTLAR
    # -----------------------------------------------------

    for idx, card_code in enumerate(hand):

        is_legal = (
            my_turn
            and card_code in legal
        )

        desc = ""

        if is_legal:

            desc = (
                "✅ Oynamak için dokun"
            )

        elif my_turn:

            desc = (
                "🔘 Şu an oynanamaz"
            )

        else:

            desc = (
                "👀 Sadece görüntüleme"
            )

        # -------------------------------------------------
        # STICKER TEMA
        # -------------------------------------------------

        sticker_file_id = None

        if (
            sticker_set_name
            and card_code
            in CARD_TO_STICKER_INDEX
        ):

            try:

                sticker_file_id = (
                    await get_card_sticker_file_id(
                        context.bot,
                        sticker_set_name,
                        card_code,
                        CARD_TO_STICKER_INDEX[
                            card_code
                        ]
                    )
                )

            except Exception as e:

                print(
                    f"⚠️ Sticker alınamadı "
                    f"({theme_id}/{card_code}): "
                    f"{e}"
                )

        # -------------------------------------------------
        # OYNANABİLİR STICKER
        # -------------------------------------------------

        if sticker_file_id and is_legal:

            results.append(
                InlineQueryResultCachedSticker(
                    id=f"{theme_id}:{card_code}#{idx}",
                    sticker_file_id=sticker_file_id
                )
            )

            continue

        # -------------------------------------------------
        # NORMAL KART GÖRSELİ
        # -------------------------------------------------

        try:

            file_id = await get_card_file_id(
                context.bot,
                card_code,
                cache_chat_id
            )

        except Exception as e:

            print(
                f"⚠️ Kart görseli yüklenemedi "
                f"({card_code}): {e}"
            )

            continue

        # -------------------------------------------------
        # OYNANAMAYAN KARTI SİLİKLEŞTİR
        # -------------------------------------------------

        if my_turn and not is_legal:

            file_id = (
                await get_dimmed_card_file_id(
                    context.bot,
                    card_code,
                    file_id,
                    cache_chat_id
                )
            )

        results.append(
            InlineQueryResultCachedPhoto(
                id=f"{theme_id}:{card_code}#{idx}",

                photo_file_id=file_id,

                title=(
                    f"🎴 "
                    f"{card_display_label(card_code)}"
                ),

                description=desc
            )
        )

    # -----------------------------------------------------
    # KART DURUMU
    # -----------------------------------------------------

    results.append(
        InlineQueryResultArticle(
            id="info",

            title="❓ Kart Durumu",

            description=(
                "Kimde kaç kart olduğunu gruba bildir"
            ),

            input_message_content=(
                InputTextMessageContent(
                    "❓ kart durumu soruldu"
                )
            )
        )
    )

    # -----------------------------------------------------
    # KART ÇEK
    # -----------------------------------------------------

    if my_turn:

        has_drawn = (
            game.get(
                "has_drawn",
                {}
            ).get(
                user.id,
                False
            )
        )

        try:

            deck_file_id = (
                await get_card_file_id(
                    context.bot,
                    DECK_BACK_CODE,
                    cache_chat_id
                )
            )

            results.append(
                InlineQueryResultCachedPhoto(
                    id="draw",

                    photo_file_id=deck_file_id,

                    title="🃏 Kart Çek",

                    description=(
                        "Kart çek"
                    )
                )
            )

        except Exception as e:

            print(
                f"⚠️ Deste görseli "
                f"yüklenemedi: {e}"
            )

        # -------------------------------------------------
        # PAS
        # -------------------------------------------------

        if has_drawn:

            results.append(
                InlineQueryResultArticle(
                    id="pass",

                    title="⏭ Pas Geç",

                    description=(
                        "Çektiğin kartı "
                        "oynamak istemiyorsan "
                        "sırayı geç"
                    ),

                    input_message_content=(
                        InputTextMessageContent(
                            "⏭ pas geçildi"
                        )
                    )
                )
            )

    await inline_query.answer(
        results,
        cache_time=1,
        is_personal=True
    )


# =========================================================
# INLINE SONUÇ
# =========================================================

async def chosen_result(
    update,
    context
):

    chosen = (
        update.chosen_inline_result
    )

    user = chosen.from_user

    result_id = chosen.result_id

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    if not game:
        return

    actor_mention = mention_html(
        user.id,
        player_name(
            game,
            user.id
        )
    )

    # -----------------------------------------------------
    # KART DURUMU
    # -----------------------------------------------------

    if result_id == "info":

        lines = [
            "📊 <b>Kart Durumu</b>\n"
        ]

        for p in game["players"]:

            count = len(
                game["hands"].get(
                    p["id"],
                    []
                )
            )

            lines.append(
                f"• "
                f"{html_escape(p['name'])}: "
                f"{count} kart"
            )

        await context.bot.send_message(
            chat_id,
            "\n".join(lines),
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # KART ÇEK
    # -----------------------------------------------------

    if result_id == "draw":

        res = draw_card(
            chat_id,
            user.id
        )

        if not res["ok"]:
            return

        n = len(
            res["drawn"]
        )

        await context.bot.send_message(
            chat_id,

            (
                f"🃏 {actor_mention} "
                f"kart çekti ({n} kart)."
            )
            if n
            else
            (
                f"🃏 {actor_mention} "
                f"çekmek istedi ama deste boş."
            ),

            parse_mode="HTML"
        )

        if not game.get("winner"):

            await announce_turn(
                context,
                chat_id
            )

        return

    # -----------------------------------------------------
    # PAS
    # -----------------------------------------------------

    if result_id == "pass":

        res = pass_turn(
            chat_id,
            user.id
        )

        if not res["ok"]:

            reasons = {
                "SIRA_DEGIL":
                    "sıra artık sende değildi",

                "ONCE_CEK":
                    "önce kart çekmen gerekiyordu",

                "OYUN_YOK":
                    "aktif bir oyun bulunamadı",
            }

            await context.bot.send_message(
                chat_id,

                f"⚠️ {actor_mention} "
                f"pas geçmeye çalıştı ama "
                f"işlenmedi "
                f"({reasons.get(res['reason'], res['reason'])}).",

                parse_mode="HTML"
            )

            return

        await context.bot.send_message(
            chat_id,

            f"⏭ {actor_mention} pas geçti.",

            parse_mode="HTML"
        )

        await announce_turn(
            context,
            chat_id
        )

        return

    # -----------------------------------------------------
    # KART OYNAMA
    # -----------------------------------------------------

    # result_id:
    # theme:card#idx

    raw_id = result_id

    if ":" in raw_id:

        raw_id = raw_id.split(
            ":",
            1
        )[1]

    card_code = raw_id.split(
        "#",
        1
    )[0]

    res = play_card(
        chat_id,
        user.id,
        card_code
    )

    if not res["ok"]:

        if chosen.inline_message_id:

            try:

                await context.bot.edit_message_reply_markup(

                    inline_message_id=(
                        chosen.inline_message_id
                    ),

                    reply_markup=(
                        InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton(
                                    "❌ Geçersiz hamle",
                                    callback_data="noop"
                                )
                            ]
                        ])
                    )
                )

            except Exception as e:

                print(
                    f"⚠️ Geçersiz kart "
                    f"işaretlenemedi: {e}"
                )

        return

    # -----------------------------------------------------
    # KAZANDI
    # -----------------------------------------------------

    if res.get("win"):

        await finish_game(
            context,
            chat_id,
            user.id
        )

        return

    # -----------------------------------------------------
    # UNO
    # -----------------------------------------------------

    if res.get("remaining") == 1:

        await context.bot.send_message(
            chat_id,

            f"🎉 {actor_mention} "
            f"<b>UNO!</b> "
            f"Elinde sadece 1 kart kaldı!",

            parse_mode="HTML"
        )

    # -----------------------------------------------------
    # JOKER RENK SEÇİMİ
    # -----------------------------------------------------

    if res.get("needs_color"):

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{COLOR_LABELS[c]} "
                    f"{COLOR_NAME_TR[c]}",
                    callback_data=(
                        f"renk:{c}:{user.id}"
                    )
                )

                for c in [
                    "kirmizi",
                    "yesil"
                ]
            ],

            [
                InlineKeyboardButton(
                    f"{COLOR_LABELS[c]} "
                    f"{COLOR_NAME_TR[c]}",
                    callback_data=(
                        f"renk:{c}:{user.id}"
                    )
                )

                for c in [
                    "mavi",
                    "sari"
                ]
            ]
        ]

        await context.bot.send_message(
            chat_id,

            f"🎨 {actor_mention}, "
            f"joker için bir renk seç:",

            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),

            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # ETKİ
    # -----------------------------------------------------

    if res.get("effect") in (
        "skip",
        "reverse"
    ):

        await announce_effect(
            context,
            chat_id,
            actor_mention,
            res["effect"]
        )

    elif res.get("effect") in (
        "draw2",
        "draw4"
    ):

        next_uid = current_player(
            chat_id
        )

        next_mention = mention_html(
            next_uid,
            player_name(
                game,
                next_uid
            )
        )

        await announce_effect(
            context,
            chat_id,
            actor_mention,
            res["effect"],
            next_mention
        )

    await announce_turn(
        context,
        chat_id
    )


# =========================================================
# /BİTİR
# =========================================================

async def bitir(
    update,
    context
):

    chat_id = update.effective_chat.id

    user = update.effective_user

    if chat_id not in games:

        await update.message.reply_text(
            "❌ Bu grupta açık bir oyun yok."
        )

        return

    game = games[
        chat_id
    ]

    is_owner = (
        game.get("owner")
        == user.id
    )

    is_admin = False

    if not is_owner:

        try:

            member = (
                await context.bot.get_chat_member(
                    chat_id,
                    user.id
                )
            )

            is_admin = (
                member.status
                in (
                    "administrator",
                    "creator"
                )
            )

        except Exception:

            is_admin = False

    if not (
        is_owner
        or is_admin
    ):

        await update.message.reply_text(
            "⛔ Sadece oyunu açan kişi "
            "veya grup yöneticileri "
            "/bitir kullanabilir."
        )

        return

    was_started = game.get(
        "started",
        False
    )

    end_game(
        chat_id
    )

    lobby_messages.pop(
        chat_id,
        None
    )

    if was_started:

        await update.message.reply_text(
            f"🛑 Oyun "
            f"{html_escape(user.first_name)} "
            f"tarafından sonlandırıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz.",

            parse_mode="HTML"
        )

    else:

        await update.message.reply_text(
            f"🛑 Lobi "
            f"{html_escape(user.first_name)} "
            f"tarafından kapatıldı.\n\n"
            f"Yeni oyun için /oyun yazabilirsiniz.",

            parse_mode="HTML"
        )


# =========================================================
# /PROFİL
# =========================================================

async def profil(
    update,
    context
):

    user_obj = update.effective_user

    user = db.get_or_create_user(
        user_obj.id,
        user_obj.username,
        user_obj.first_name
    )

    theme_id = (
        user[8]
        if len(user) > 8
        else "meyus"
    )

    theme_name = CARD_THEMES.get(
        theme_id,
        CARD_THEMES["meyus"]
    )["name"]

    await update.message.reply_text(
        f"👤 <b>Profil</b>\n\n"
        f"💰 Coin: <b>{user[3]}</b>\n"
        f"🏆 Galibiyet: <b>{user[4]}</b>\n"
        f"🎮 Oyun: <b>{user[5]}</b>\n"
        f"⭐ Seviye: <b>{user[6]}</b>\n"
        f"✨ XP: <b>{user[7]}</b>\n"
        f"🎨 Tema: <b>{theme_name}</b>",

        parse_mode="HTML"
    )


# =========================================================
# /YARDIM
# =========================================================

async def yardim(
    update,
    context
):

    await update.message.reply_text(
        "📖 <b>Meyus UNO Yardım</b>\n\n"
        "/start - Botu başlatır\n"
        "/oyun - Yeni oyun oluşturur\n"
        "/katil - Oyuna katılır\n"
        "/baslat - Oyunu başlatır\n"
        "/bitir - Oyunu/lobiyi sonlandırır\n"
        "/profil - Profilini gösterir\n"
        "/tema - Kart temasını seçer\n"
        "/cek - Sıra sendeyken kart çeker\n"
        "/pas - Kart çektikten sonra pas geçer\n\n"
        "🎴 Kartlarımı Gör / Oyna butonuyla "
        "elini görebilirsin.\n\n"
        "🟢 Oynanabilir kartlar normal görünür.\n"
        "🔘 Oynanamayan kartlar silik görünür.\n"
        "🎨 Seçtiğin tema yalnızca senin kartlarını etkiler.",

        parse_mode="HTML"
    )


# =========================================================
# CHAT MIGRATION
# =========================================================

def _migrate_chat(
    old_chat_id,
    new_chat_id
):

    if old_chat_id in games:

        game = games.pop(
            old_chat_id
        )

        games[
            new_chat_id
        ] = game

        for uid in game.get(
            "hands",
            {}
        ).keys():

            if user_active_chat.get(
                uid
            ) == old_chat_id:

                user_active_chat[
                    uid
                ] = new_chat_id

    if old_chat_id in lobby_messages:

        lobby_messages[
            new_chat_id
        ] = lobby_messages.pop(
            old_chat_id
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    err = context.error

    if isinstance(
        err,
        ChatMigrated
    ):

        old_chat_id = None

        if (
            update
            and getattr(
                update,
                "effective_chat",
                None
            )
        ):

            old_chat_id = (
                update.effective_chat.id
            )

        new_chat_id = (
            err.new_chat_id
        )

        if old_chat_id is not None:

            _migrate_chat(
                old_chat_id,
                new_chat_id
            )

        try:

            await context.bot.send_message(
                new_chat_id,

                "ℹ️ Bu grup süper gruba "
                "yükseltildi.\n\n"
                "Oyun verisi yeni gruba taşındı."
            )

        except Exception:

            pass

        return

    print(
        f"⚠️ Beklenmeyen hata: {err}"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Komutlar
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "yardim",
            yardim
        )
    )

    app.add_handler(
        CommandHandler(
            "oyun",
            oyun
        )
    )

    app.add_handler(
        CommandHandler(
            "katil",
            katil
        )
    )

    app.add_handler(
        CommandHandler(
            "baslat",
            baslat
        )
    )

    app.add_handler(
        CommandHandler(
            "bitir",
            bitir
        )
    )

    app.add_handler(
        CommandHandler(
            "profil",
            profil
        )
    )

    app.add_handler(
        CommandHandler(
            "tema",
            tema
        )
    )

    app.add_handler(
        CommandHandler(
            "cek",
            cek
        )
    )

    app.add_handler(
        CommandHandler(
            "pas",
            pas
        )
    )

    app.add_handler(
        CommandHandler(
            "stickerlar",
            stickerlar
        )
    )

    # Callback
    app.add_handler(
        CallbackQueryHandler(
            button
        )
    )

    # Inline
    app.add_handler(
        InlineQueryHandler(
            inline_hand
        )
    )

    app.add_handler(
        ChosenInlineResultHandler(
            chosen_result
        )
    )

    # Hatalar
    app.add_error_handler(
        error_handler
    )

    print(
        "✅ Meyus UNO başlatıldı!"
    )

    app.run_polling()


if __name__ == "__main__":
    main()
