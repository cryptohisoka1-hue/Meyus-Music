import asyncio

from game import *
from cards_data import (
    card_display_label,
    COLOR_NAME_TR,
    COLOR_LABELS,
    ALL_CARD_CODES,
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

# Sticker paketindeki file_id'ler
UNO_STICKERS = []

# Kart kodu -> sticker file_id
CARD_STICKERS = {}

# Deste arkası
DECK_BACK_STICKER = None


# ============================================================
# YARDIMCI
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
# 108 KARTLIK STANDART UNO SIRASI
# ============================================================

def build_standard_card_order():
    """
    Standart 108 kartın sırasını oluşturur.

    Her renk:
        0  -> 1 adet
        1-9 -> 2 adet
        +2 -> 2 adet
        DUR -> 2 adet
        YÖN -> 2 adet

    4 renk = 100 kart

    Joker = 4
    Joker +4 = 4

    Toplam = 108
    """

    cards = []

    colors = [
        "kirmizi",
        "yesil",
        "mavi",
        "sari",
    ]

    symbols = [
        "artiiki",
        "durdur",
        "yonvedegis",
    ]

    for color in colors:

        # 0
        cards.append(f"{color}_0")

        # 1-9
        for number in range(1, 10):
            cards.append(f"{color}_{number}")
            cards.append(f"{color}_{number}")

        # Özel kartlar
        for symbol in symbols:
            cards.append(f"{color}_{symbol}")
            cards.append(f"{color}_{symbol}")

    # 4 Joker
    for _ in range(4):
        cards.append("wild_renk")

    # 4 Joker +4
    for _ in range(4):
        cards.append("wild_artidort")

    return cards


# ============================================================
# STICKER PAKETİNİ YÜKLE
# ============================================================

async def load_uno_stickers(bot):

    global UNO_STICKERS
    global CARD_STICKERS
    global DECK_BACK_STICKER

    print(
        f"⏳ Telegram sticker paketi yükleniyor: "
        f"{UNO_STICKER_SET}"
    )

    try:

        sticker_set = await bot.get_sticker_set(
            UNO_STICKER_SET
        )

    except Exception as e:

        print(
            "❌ Sticker paketi alınamadı:"
        )
        print(
            repr(e)
        )

        return False

    if not sticker_set:
        print(
            "❌ Sticker seti bulunamadı."
        )
        return False

    stickers = sticker_set.stickers

    if not stickers:

        print(
            "❌ Sticker paketi boş."
        )

        return False

    UNO_STICKERS = [
        sticker.file_id
        for sticker in stickers
    ]

    print(
        f"📦 Sticker sayısı: "
        f"{len(UNO_STICKERS)}"
    )

    # --------------------------------------------------------
    # 108 KART KONTROLÜ
    # --------------------------------------------------------

    if len(UNO_STICKERS) < 108:

        print(
            "⚠️ UYARI:"
        )

        print(
            "UnoCardsDeck içinde 108'den az "
            "sticker bulunuyor."
        )

        print(
            "Kart eşleştirmesi eksik olabilir."
        )

    # --------------------------------------------------------
    # STICKERLARI KART KODLARINA EŞLEŞTİR
    # --------------------------------------------------------

    standard_cards = build_standard_card_order()

    CARD_STICKERS = {}

    for index, card_code in enumerate(
        standard_cards
    ):

        if index >= len(UNO_STICKERS):
            break

        sticker_id = UNO_STICKERS[index]

        # Aynı kartın iki kopyası varsa
        # aynı card_code üzerine aynı stickerı yazıyoruz.
        CARD_STICKERS[card_code] = sticker_id

    # --------------------------------------------------------
    # DESTE ARKASI
    # --------------------------------------------------------

    # Eğer pakette 109. sticker varsa
    # bunu deste arkası olarak kullanıyoruz.
    if len(UNO_STICKERS) >= 109:
        DECK_BACK_STICKER = UNO_STICKERS[108]
    else:
        DECK_BACK_STICKER = None

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    print(
        f"✅ {len(CARD_STICKERS)} farklı kart "
        f"başarıyla eşleştirildi."
    )

    if DECK_BACK_STICKER:
        print(
            "✅ Deste arkası stickerı bulundu."
        )
    else:
        print(
            "ℹ️ Deste arkası stickerı bulunamadı."
        )

    return True


# ============================================================
# KART STICKERINI AL
# ============================================================

def get_card_sticker(card_code):

    return CARD_STICKERS.get(
        card_code
    )


# ============================================================
# TUR DUYURUSU
# ============================================================

async def announce_turn(
    context,
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

    if uid is None:
        return

    name = player_name(
        game,
        uid
    )

    color_tr = COLOR_NAME_TR.get(
        game["top_color"],
        game["top_color"]
    )

    await context.bot.send_message(
        chat_id,
        (
            f"🔁 Sıra sende "
            f"{mention_html(uid, name)}!\n\n"
            f"🎨 Geçerli renk: "
            f"<b>{color_tr}</b>\n\n"
            f"🎴 Kartlarını görmek ve "
            f"oynamak için aşağıdaki "
            f"butona dokun 👇"
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON
    )


# ============================================================
# KART ETKİSİ
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
            f"⛔ {actor_mention} "
            f"DUR kartı oynadı, sıra atlandı!",

        "reverse":
            f"🔄 {actor_mention} "
            f"YÖN kartı oynadı, yön değişti!",

        "draw2":
            f"➕2️⃣ {actor_mention} "
            f"+2 oynadı, {next_mention} "
            f"2 kart çekip sırasını kaçırdı!",

        "draw4":
            f"➕4️⃣ {actor_mention} "
            f"+4 oynadı, {next_mention} "
            f"4 kart çekip sırasını kaçırdı!",
    }

    text = texts.get(effect)

    if text:

        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML"
        )


# ============================================================
# OYUNU BİTİR
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
        player_name(
            game,
            winner_uid
        )
    )

    db.add_win(
        winner_uid
    )

    db.add_coin(
        winner_uid,
        50
    )

    db.add_xp(
        winner_uid,
        30
    )

    for p in game["players"]:

        db.add_game(
            p["id"]
        )

    user = db.get_user(
        winner_uid
    )

    level = (
        user[6]
        if user
        else 1
    )

    xp = (
        user[7]
        if user
        else 0
    )

    await context.bot.send_message(
        chat_id,
        (
            f"🏆 {winner_mention} "
            f"<b>oyunu kazandı!</b> 🎉\n\n"
            f"🪙 +50 Coin\n"
            f"✨ +30 XP\n\n"
            f"⭐ Seviye: {level}\n"
            f"✨ XP: {xp}\n\n"
            f"🎮 Yeni oyun için "
            f"/oyun yazabilirsiniz."
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

🃏 Kartlarım butonuna basarak
elindeki kartları görebilirsin.

🎴 Kartlar gerçek UNO stickerları
olarak gösterilir.

İyi eğlenceler ❤️
"""

    await update.message.reply_html(
        text
    )


# ============================================================
# OYUN OLUŞTUR
# ============================================================

async def oyun(
    update,
    context
):

    chat = update.effective_chat
    user = update.effective_user

    if not create_game(
        chat.id,
        user.id
    ):

        await update.message.reply_text(
            "❌ Bu grupta zaten açık "
            "bir oyun var."
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
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="HTML"
    )

    lobby_messages[
        chat.id
    ] = msg.message_id


# ============================================================
# OYUN BAŞLAT
# ============================================================

async def _do_start_game(
    context,
    chat_id
):

    game = start_game(
        chat_id
    )

    if not game:

        await context.bot.send_message(
            chat_id,
            "❌ Oyun başlatılamadı."
        )

        return

    t_card = top_card(
        chat_id
    )

    color_tr = COLOR_NAME_TR.get(
        game["top_color"],
        game["top_color"]
    )

    sticker_id = get_card_sticker(
        t_card
    )

    # --------------------------------------------------------
    # BAŞLANGIÇ KARTI
    # --------------------------------------------------------

    if sticker_id:

        try:

            await context.bot.send_sticker(
                chat_id,
                sticker=sticker_id
            )

        except Exception as e:

            print(
                "❌ Başlangıç stickerı gönderilemedi:"
            )

            print(
                repr(e)
            )

    else:

        print(
            f"⚠️ Sticker bulunamadı: {t_card}"
        )

    # --------------------------------------------------------
    # OYUN MESAJI
    # --------------------------------------------------------

    await context.bot.send_message(
        chat_id,
        (
            "🚀 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: "
            f"<b>{color_tr}</b>\n\n"
            "🎴 Kartlarını görmek için "
            "butona dokun.\n\n"
            "⚡ Sadece sırası gelen "
            "oyuncu kart oynayabilir."
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
    update,
    context
):

    query = update.callback_query

    chat_id = query.message.chat.id
    user = query.from_user

    # ========================================================
    # KATIL
    # ========================================================

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
            "🎮 <b>Meyus UNO Lobisi</b>\n\n"
            f"👥 Oyuncular ({len(players)})\n\n"
        )

        for p in players:

            text += (
                f"• {p['name']}\n"
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

    # ========================================================
    # BAŞLAT
    # ========================================================

    if query.data == "start_game":

        if chat_id not in games:

            await query.answer(
                "Oyun bulunamadı.",
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

    # ========================================================
    # RENK
    # ========================================================

    if query.data.startswith(
        "renk:"
    ):

        _, color, target_uid = (
            query.data.split(":")
        )

        target_uid = int(
            target_uid
        )

        if user.id != target_uid:

            await query.answer(
                "Sadece kartı oynayan "
                "kişi rengi seçebilir.",
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

        await query.edit_message_reply_markup(
            reply_markup=None
        )

        game = games[
            chat_id
        ]

        await context.bot.send_message(
            chat_id,
            (
                f"🎨 "
                f"{mention_html(user.id, player_name(game, user.id))} "
                f"rengi "
                f"<b>{COLOR_NAME_TR.get(color, color)}</b> "
                f"seçti."
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

    await query.answer()


# ============================================================
# KATIL
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
            f"✅ "
            f"{update.effective_user.first_name} "
            f"oyuna katıldı!\n\n"
            f"👥 Toplam oyuncu: "
            f"{oyuncu}"
        )
    )


# ============================================================
# BAŞLAT
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

    if len(
        games[chat_id]["players"]
    ) < 2:

        await update.message.reply_text(
            "❌ En az 2 oyuncu gerekli."
        )

        return

    await _do_start_game(
        context,
        chat_id
    )


# ============================================================
# INLINE KARTLAR
# ============================================================

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
            switch_pm_parameter=(
                "no_game"
            ),
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

    playable_results = []
    unplayable_results = []

    # ========================================================
    # ELDEKİ KARTLAR
    # ========================================================

    for idx, card_code in enumerate(
        ha
