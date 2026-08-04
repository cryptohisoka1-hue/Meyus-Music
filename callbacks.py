import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from telegram.error import TelegramError

from config import (
    THEME_PACKS,
    DEFAULT_THEME,
    CARD_FACES,
    COLOR_EMOJI,
    COLORS,
    MIN_PLAYERS,
    MAX_PLAYERS,
)

from game import UnoGame, card_label

import database as db


logger = logging.getLogger(__name__)


GAMES = {}

THEME_STICKERS = {}


# =========================================================
# TEMALAR
# =========================================================

async def load_all_themes(bot):

    for key, pack_name in THEME_PACKS.items():

        try:

            sticker_set = await bot.get_sticker_set(pack_name)

            THEME_STICKERS[key] = [
                sticker.file_id
                for sticker in sticker_set.stickers
            ]

            logger.info(
                f"Tema yüklendi: "
                f"{key} ({len(THEME_STICKERS[key])} sticker)"
            )

        except TelegramError as e:

            logger.warning(
                f"Tema yüklenemedi "
                f"({key} -> {pack_name}): {e}"
            )


def card_sticker(theme, card):

    file_ids = THEME_STICKERS.get(theme)

    if not file_ids:
        return None

    try:
        index = CARD_FACES.index(card)
    except ValueError:
        return None

    return file_ids[index % len(file_ids)]


# =========================================================
# /OYUN
# =========================================================

async def cmd_oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user = update.effective_user

    if (
        chat_id in GAMES
        and GAMES[chat_id].state != "finished"
    ):
        await update.message.reply_text(
            "Bu grupta zaten aktif bir lobi/oyun var.\n"
            "Bitirmek için /bitir yaz."
        )
        return

    db.upsert_user(
        user.id,
        user.username,
        user.first_name,
    )

    game = UnoGame(
        chat_id,
        user.id,
    )

    game.theme = DEFAULT_THEME

    game.add_player(
        user.id,
        user.first_name,
    )

    GAMES[chat_id] = game

    await send_lobby(
        chat_id,
        context,
    )


# =========================================================
# LOBİ
# =========================================================

async def send_lobby(chat_id, context):

    game = GAMES[chat_id]

    players_text = "\n".join(
        f"• {p['name']}"
        for p in game.players.values()
    )

    text = (
        "🎮 *UNO Lobisi Açıldı!*\n\n"
        f"Katılımcılar "
        f"({len(game.players)}/{MAX_PLAYERS}):\n"
        f"{players_text}\n\n"
        f"🎨 Tema: {game.theme}\n\n"
        "Katılmak için aşağıdaki butona bas."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Katıl",
                callback_data="join",
            )
        ],
        [
            InlineKeyboardButton(
                f"🎨 Tema: {game.theme}",
                callback_data="theme_menu",
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Başlat",
                callback_data="startgame",
            )
        ],
    ]

    await context.bot.send_message(
        chat_id,
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# =========================================================
# /BİTİR
# =========================================================

async def cmd_bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    game = GAMES.get(chat_id)

    if not game:
        await update.message.reply_text(
            "Aktif bir oyun/lobi yok."
        )
        return

    if update.effective_user.id != game.host_id:

        await update.message.reply_text(
            "Sadece lobiyi açan kişi oyunu bitirebilir."
        )
        return

    del GAMES[chat_id]

    await update.message.reply_text(
        "🛑 Oyun sonlandırıldı."
    )


# =========================================================
# /SIRALAMA
# =========================================================

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):

    rows = db.get_weekly_ranking(10)

    if not rows:

        await update.message.reply_text(
            "Bu hafta henüz kazanan yok."
        )

        return

    lines = [
        "🏆 *Haftalık Sıralama*\n"
    ]

    medals = [
        "🥇",
        "🥈",
        "🥉",
    ]

    for index, row in enumerate(rows):

        medal = (
            medals[index]
            if index < 3
            else f"{index + 1}."
        )

        name = (
            row["first_name"]
            or row["username"]
            or "Oyuncu"
        )

        lines.append(
            f"{medal} {name} — "
            f"{row['weekly_wins']} galibiyet"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# =========================================================
# /PROFİL
# =========================================================

async def cmd_profil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    db.upsert_user(
        user.id,
        user.username,
        user.first_name,
    )

    profile = db.get_profile(user.id)

    if not profile:

        await update.message.reply_text(
            "Henüz hiç oyun oynamadın.\n"
            "/oyun ile başla!"
        )

        return

    if profile["games_played"] == 0:

        await update.message.reply_text(
            "Henüz hiç oyun oynamadın.\n"
            "/oyun ile başla!"
        )

        return

    win_rate = (
        profile["wins"]
        / profile["games_played"]
    ) * 100

    text = (
        f"👤 *{user.first_name} - Profil*\n\n"
        f"🎮 Oynanan oyun: "
        f"{profile['games_played']}\n"
        f"🏆 Galibiyet: "
        f"{profile['wins']}\n"
        f"📊 Kazanma oranı: "
        f"%{win_rate:.1f}\n"
        f"🃏 Oynanan toplam kart: "
        f"{profile['cards_played']}"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# =========================================================
# CALLBACK
# =========================================================

async def on_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    data = query.data

    chat_id = query.message.chat_id

    user = query.from_user

    game = GAMES.get(chat_id)

    # =====================================================
    # NOOP
    # =====================================================

    if data == "noop":

        await query.answer(
            "Bu kartı şu an oynayamazsın.",
            show_alert=False,
        )

        return

    # =====================================================
    # KATIL
    # =====================================================

    if data == "join":

        if not game or game.state != "lobby":

            await query.answer(
                "Lobi bulunamadı.",
                show_alert=True,
            )

            return

        if len(game.players) >= MAX_PLAYERS:

            await query.answer(
                "Lobi dolu.",
                show_alert=True,
            )

            return

        db.upsert_user(
            user.id,
            user.username,
            user.first_name,
        )

        added = game.add_player(
            user.id,
            user.first_name,
        )

        await query.answer(
            "Katıldın!"
            if added
            else "Zaten lobidesin."
        )

        await refresh_lobby_message(
            query,
            game,
        )

        return

    # =====================================================
    # TEMA MENÜ
    # =====================================================

    if data == "theme_menu":

        if not game:
            await query.answer(
                "Lobi bulunamadı.",
                show_alert=True,
            )
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    key,
                    callback_data=f"settheme|{key}",
                )
            ]
            for key in THEME_PACKS.keys()
        ]

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬅️ Geri",
                    callback_data="back_lobby",
                )
            ]
        )

        await query.edit_message_reply_markup(
            InlineKeyboardMarkup(keyboard)
        )

        await query.answer()

        return

    # =====================================================
    # TEMA SEÇ
    # =====================================================

    if data.startswith("settheme|"):

        theme = data.split("|", 1)[1]

        if game and theme in THEME_PACKS:
            game.theme = theme

        await query.answer(
            f"Tema: {theme}"
        )

        await refresh_lobby_message(
            query,
            game,
        )

        return

    # =====================================================
    # LOBİYE GERİ DÖN
    # =====================================================

    if data == "back_lobby":

        await refresh_lobby_message(
            query,
            game,
        )

        await query.answer()

        return

    # =====================================================
    # OYUNU BAŞLAT
    # =====================================================

    if data == "startgame":

        if not game or game.state != "lobby":

            await query.answer(
                "Lobi bulunamadı.",
                show_alert=True,
            )

            return

        if user.id != game.host_id:

            await query.answer(
                "Sadece lobiyi açan kişi başlatabilir.",
                show_alert=True,
            )

            return

        if len(game.players) < MIN_PLAYERS:

            await query.answer(
                f"En az {MIN_PLAYERS} oyuncu gerekli.",
                show_alert=True,
            )

            return

        if not game.start():

            await query.answer(
                "Oyun başlatılamadı.",
                show_alert=True,
            )

            return

        await query.answer(
            "Oyun başladı!"
        )

        await query.edit_message_text(
            "🎮 *Oyun başladı!*\n\n"
            "Kartlar dağıtıldı.",
            parse_mode="Markdown",
        )

        await send_turn(
            chat_id,
            context,
        )

        return

    # =====================================================
    # OYUN KONTROL
    # =====================================================

    if not game or game.state != "playing":

        await query.answer(
            "Aktif oyun yok.",
            show_alert=True,
        )

        return

    # =====================================================
    # KART ÇEK
    # =====================================================

    if data == "draw":

        if game.current_player != user.id:

            await query.answer(
                "Sıra sende değil.",
                show_alert=True,
            )

            return

        # ÖNEMLİ:
        # Artık doğrudan draw_cards(1) yok.
        #
        # +2 zincirinde:
        # 2 / 4 / 6 / ... kadar kart çeker.
        #
        # Normalde:
        # 1 kart çeker.

        drawn = game.draw_for_current()

        await query.answer(
            f"{len(drawn)} kart çektin."
        )

        await send_turn(
            chat_id,
            context,
        )

        return

    # =====================================================
    # KART OYNA
    # =====================================================

    if data.startswith("play|"):

        card = data.split("|", 1)[1]

        if game.current_player != user.id:

            await query.answer(
                "Sıra sende değil.",
                show_alert=True,
            )

            return

        # Wild / Wild4 renk seçimi
        if card in ("Wild", "Wild4"):

            keyboard = [
                [
                    InlineKeyboardButton(
                        COLOR_EMOJI[color],
                        callback_data=(
                            f"pickcolor|{card}|{color}"
                        ),
                    )
                ]
                for color in COLORS
            ]

            await query.edit_message_reply_markup(
                InlineKeyboardMarkup(keyboard)
            )

            await query.answer(
                "Renk seç"
            )

            return

        ok, result = game.play_card(
            user.id,
            card,
        )

        if not ok:

            await query.answer(
                result,
                show_alert=True,
            )

            return

        db.record_card_played(
            user.id
        )

        await query.answer()

        if result == "WIN":

            await finish_game(
                chat_id,
                context,
                user,
            )

            return

        await send_turn(
            chat_id,
            context,
        )

        return

    # =====================================================
    # WILD RENK SEÇ
    # =====================================================

    if data.startswith("pickcolor|"):

        parts = data.split("|")

        if len(parts) != 3:

            await query.answer(
                "Geçersiz seçim.",
                show_alert=True,
            )

            return

        _, card, color = parts

        if game.current_player != user.id:

            await query.answer(
                "Sıra sende değil.",
                show_alert=True,
            )

            return

        ok, result = game.play_card(
            user.id,
            card,
            chosen_color=color,
        )

        if not ok:

            await query.answer(
                result,
                show_alert=True,
            )

            return

        db.record_card_played(
            user.id
        )

        await query.answer()

        if result == "WIN":

            await finish_game(
                chat_id,
                context,
                user,
            )

            return

        await send_turn(
            chat_id,
            context,
        )

        return


# =========================================================
# LOBİYİ GÜNCELLE
# =========================================================

async def refresh_lobby_message(
    query,
    game,
):

    if not game:
        return

    players_text = "\n".join(
        f"• {p['name']}"
        for p in game.players.values()
    )

    text = (
        "🎮 *UNO Lobisi Açıldı!*\n\n"
        f"Katılımcılar "
        f"({len(game.players)}/{MAX_PLAYERS}):\n"
        f"{players_text}\n\n"
        f"🎨 Tema: {game.theme}\n\n"
        "Katılmak için aşağıdaki butona bas."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Katıl",
                callback_data="join",
            )
        ],
        [
            InlineKeyboardButton(
                f"🎨 Tema: {game.theme}",
                callback_data="theme_menu",
            )
        ],
        [
            InlineKeyboardButton(
                "🚀 Başlat",
                callback_data="startgame",
            )
        ],
    ]

    try:

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
            parse_mode="Markdown",
        )

    except TelegramError:
        pass


# =========================================================
# SIRA MESAJI
# =========================================================

async def send_turn(
    chat_id,
    context,
):

    game = GAMES.get(chat_id)

    if not game:
        return

    if game.state != "playing":
        return

    uid = game.current_player

    if uid is None:
        return

    name = game.players[uid]["name"]

    # Önceki sıra mesajını sil
    if game.pending_message_id:

        try:

            await context.bot.delete_message(
                chat_id,
                game.pending_message_id,
            )

        except TelegramError:
            pass

    # Üst kart sticker
    sticker_id = card_sticker(
        game.theme,
        game.top_card,
    )

    if sticker_id:

        try:

            await context.bot.send_sticker(
                chat_id,
                sticker_id,
            )

        except TelegramError:
            pass

    # Zincir bilgisi
    chain_text = ""

    if game.pending_type == "draw2":

        chain_text = (
            f"\n⚠️ +2 zinciri: "
            f"{game.pending_draw} kart"
        )

        chain_text += (
            "\n➡️ +2 veya +4 oynayabilirsin."
        )

    header = (
        f"🔔 Sıra sende, "
        f"<a href='tg://user?id={uid}'>"
        f"{name}</a>!\n"
        f"Üstteki kart: "
        f"{card_label(game.top_card)}\n"
        f"Renk: "
        f"{COLOR_EMOJI.get(game.current_color, game.current_color)}\n"
        f"Yön: "
        f"{'⏩' if game.direction == 1 else '⏪'}"
        f"{chain_text}"
    )

    hand = game.players[uid]["hand"]

    keyboard = []

    for card in hand:

        playable = game.is_playable(card)

        if playable:

            label = card_label(card)

            callback = f"play|{card}"

        else:

            label = f"🔒{card_label(card)}"

            callback = "noop"

        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=callback,
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🃏 Kart Çek",
                callback_data="draw",
            )
        ]
    )

    message = await context.bot.send_message(
        chat_id,
        header,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
        parse_mode="HTML",
    )

    game.pending_message_id = message.message_id


# =========================================================
# OYUN BİTTİ
# =========================================================

async def finish_game(
    chat_id,
    context,
    winner,
):

    game = GAMES.get(chat_id)

    if not game:
        return

    db.record_game_result(
        chat_id,
        list(game.players.keys()),
        winner.id,
    )

    await context.bot.send_message(
        chat_id,
        (
            f"🎉 <b>{winner.first_name}</b> "
            f"oyunu kazandı!\n\n"
            "🏆 Tebrikler!\n\n"
            "Yeni oyun için /oyun yaz."
        ),
        parse_mode="HTML",
    )

    del GAMES[chat_id]
