import asyncio

from game import *

from cards_data import (
    card_display_label,
    DECK_BACK_CODE,
    COLOR_NAME_TR,
    COLOR_LABELS,
    ALL_CARD_CODES,
    PASS_ICON_CODE,
    INFO_ICON_CODE,
)

from card_cache import (
    get_card_file_id,
    get_local_icon_file_id,
    prewarm_all_cards,
)

from icon_assets import (
    pass_icon_bytes,
    info_icon_bytes,
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
    InlineQueryResultsButton,
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


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def player_name(game, uid):
    """Oyuncunun adını bulur."""
    for p in game.get("players", []):
        if p["id"] == uid:
            return p.get("name", "?")
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
    """Kullanıcı adını tıklanabilir Telegram etiketi yapar."""
    return (
        f'<a href="tg://user?id={uid}">'
        f'{html_escape(name)}'
        f'</a>'
    )


# ============================================================
# ORTAK BUTON
# ============================================================

HAND_BUTTON = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "🎴 Kartlarımı Gör / Oyna",
                switch_inline_query_current_chat=""
            )
        ]
    ]
)


# ============================================================
# SIRA BİLDİRİMİ
# ============================================================

async def announce_turn(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id,
):
    game = games.get(chat_id)

    if not game:
        return

    if not game.get("started"):
        return

    if game.get("winner"):
        return

    try:
        uid = current_player(chat_id)
    except Exception:
        return

    if uid is None:
        return

    name = player_name(game, uid)

    color_tr = COLOR_NAME_TR.get(
        game.get("top_color"),
        game.get("top_color", "?"),
    )

    try:
        top_label = card_display_label(
            top_card(chat_id)
        )
    except Exception:
        top_label = "Bilinmiyor"

    await context.bot.send_message(
        chat_id,
        (
            f"🎯 Sıra sende "
            f"{mention_html(uid, name)}!\n\n"
            f"🎴 Son atılan kart: "
            f"<b>{html_escape(top_label)}</b>\n"
            f"🎨 Geçerli renk: "
            f"<b>{html_escape(color_tr)}</b>\n\n"
            f"Aşağıdaki butona dokun, "
            f"kartların otomatik açılsın 🎴"
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )


# ============================================================
# KART ETKİSİ BİLDİRİMİ
# ============================================================

async def announce_effect(
    context,
    chat_id,
    actor_mention,
    effect,
    next_mention=None,
):
    texts = {
        "skip": (
            f"⛔ {actor_mention} "
            f"DUR kartı oynadı, sıra atlandı!"
        ),

        "reverse": (
            f"🔄 {actor_mention} "
            f"YÖN kartı oynadı, yön değişti!"
        ),

        "draw2": (
            f"➕2️⃣ {actor_mention} "
            f"+2 oynadı, {next_mention} "
            f"2 kart çekip sırasını kaçırdı!"
        ),

        "draw4": (
            f"➕4️⃣ {actor_mention} "
            f"+4 oynadı, {next_mention} "
            f"4 kart çekip sırasını kaçırdı!"
        ),
    }

    text = texts.get(effect)

    if text:
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
        )


# ============================================================
# OYUN BİTİRME
# ============================================================

async def finish_game(
    context,
    chat_id,
    winner_uid,
):
    game = games.get(chat_id)

    if not game:
        return

    winner_name = player_name(
        game,
        winner_uid,
    )

    winner_mention = mention_html(
        winner_uid,
        winner_name,
    )

    # İstatistikleri kaydet
    try:
        db.add_win(
            winner_uid,
            winner_name,
        )
    except Exception as e:
        print(
            f"⚠️ Galibiyet kaydedilemedi: {e}"
        )

    for p in game.get("players", []):
        try:
            db.add_game(
                p["id"],
                p["name"],
            )
        except Exception as e:
            print(
                f"⚠️ Oyun istatistiği kaydedilemedi: {e}"
            )

    # Ödüller
    try:
        db.add_coin(
            winner_uid,
            50,
        )
    except Exception as e:
        print(
            f"⚠️ Coin eklenemedi: {e}"
        )

    try:
        db.add_xp(
            winner_uid,
            30,
        )
    except Exception as e:
        print(
            f"⚠️ XP eklenemedi: {e}"
        )

    # Önce kazanan mesajını gönder
    await context.bot.send_message(
        chat_id,
        (
            f"🏆 {winner_mention} "
            f"<b>oyunu kazandı!</b> 🎉\n\n"
            f"💰 +50 coin\n"
            f"⭐ +30 XP\n\n"
            f"Yeni oyun için <b>/oyun</b>"
        ),
        parse_mode="HTML",
    )

    # Oyunu temizle
    try:
        end_game(chat_id)
    except Exception as e:
        print(
            f"⚠️ Oyun temizlenirken hata: {e}"
        )

    try:
        lobby_messages.pop(chat_id, None)
    except Exception:
        pass


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if not user:
        return

    try:
        db.add_user(
            user.id,
            user.username,
            user.first_name,
        )
    except Exception as e:
        print(
            f"⚠️ Kullanıcı kaydedilemedi: {e}"
        )

    text = (
        "🎴 <b>Meyus UNO</b>'ya hoş geldin!\n\n"
        "🔥 Telegram üzerinde arkadaşlarınla "
        "UNO oyna.\n\n"
        "🎮 <b>Komutlar</b>\n"
        "• /oyun — Yeni oyun oluştur\n"
        "• /katil — Oyuna katıl\n"
        "• /baslat — Oyunu başlat\n"
        "• /bitir — Oyunu sonlandır\n"
        "• /profil — Profilini göster\n"
        "• /siralama — Haftalık sıralama\n"
        "• /yardim — Yardım\n\n"
        "🎴 Oyun başladıktan sonra "
        "<b>Kartlarımı Gör / Oyna</b> "
        "butonundan elini açabilirsin."
    )

    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
        )


# ============================================================
# /OYUN
# ============================================================

async def oyun(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    try:
        db.add_user(
            user.id,
            user.username,
            user.first_name,
        )
    except Exception as e:
        print(
            f"⚠️ Kullanıcı kaydedilemedi: {e}"
        )

    if chat.id in games:
        await update.message.reply_text(
            "❌ Bu grupta zaten açık bir oyun var."
        )
        return

    if not create_game(
        chat.id,
        user.id,
    ):
        await update.message.reply_text(
            "❌ Oyun oluşturulamadı."
        )
        return

    join_game(
        chat.id,
        user.id,
        user.first_name,
    )

    players = games[chat.id]["players"]

    text = (
        "🎮 <b>Meyus UNO Lobisi</b>\n\n"
        f"👥 Oyuncular ({len(players)})\n\n"
    )

    for p in players:
        text += (
            f"• {html_escape(p['name'])}\n"
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
                "▶️ Başlat",
                callback_data="start_game",
            )
        ],
    ]

    message = await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )

    try:
        lobby_messages[chat.id] = message.message_id
    except Exception:
        pass


# ============================================================
# OYUNU BAŞLAT
# ============================================================

async def _do_start_game(
    context,
    chat_id,
):
    if chat_id not in games:
        return False

    game_before = games[chat_id]

    if game_before.get("started"):
        return False

    if len(
        game_before.get("players", [])
    ) < 2:
        return False

    game = start_game(chat_id)

    if not game:
        return False

    t_card = top_card(chat_id)

    color_tr = COLOR_NAME_TR.get(
        game.get("top_color"),
        game.get("top_color", "?"),
    )

    # Kart cache
    cache_chat_id = (
        STORAGE_CHAT_ID or chat_id
    )

    try:
        asyncio.create_task(
            prewarm_all_cards(
                context.bot,
                cache_chat_id,
                ALL_CARD_CODES,
            )
        )
    except Exception as e:
        print(
            f"⚠️ Kart cache başlatılamadı: {e}"
        )

    try:
        asyncio.create_task(
            get_local_icon_file_id(
                context.bot,
                PASS_ICON_CODE,
                pass_icon_bytes(),
            )
        )
    except Exception as e:
        print(
            f"⚠️ Pas ikonu cache başlatılamadı: {e}"
        )

    try:
        asyncio.create_task(
            get_local_icon_file_id(
                context.bot,
                INFO_ICON_CODE,
                info_icon_bytes(),
            )
        )
    except Exception as e:
        print(
            f"⚠️ Bilgi ikonu cache başlatılamadı: {e}"
        )

    try:
        file_id = await get_card_file_id(
            context.bot,
            t_card,
            cache_chat_id,
        )
    except Exception as e:
        print(
            f"⚠️ Başlangıç kartı yüklenemedi: {e}"
        )

        await context.bot.send_message(
            chat_id,
            "❌ Başlangıç kartı yüklenemedi."
        )

        return False

    await context.bot.send_photo(
        chat_id,
        photo=file_id,
        caption=(
            "🎉 <b>Oyun başladı!</b>\n\n"
            f"🎨 Başlangıç rengi: "
            f"<b>{html_escape(color_tr)}</b>\n\n"
            "Herkes istediği an elini görebilir.\n"
            "Sadece sırası gelen oynayabilir."
        ),
        parse_mode="HTML",
        reply_markup=HAND_BUTTON,
    )

    await announce_turn(
        context,
        chat_id,
    )

    return True


# ============================================================
# CALLBACK BUTONLARI
# ============================================================

async def button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    chat_id = (
        query.message.chat.id
        if query.message
        else None
    )

    user = query.from_user

    if query.data == "noop":
        await query.answer(
            "Bu hamle geçersizdi, işlenmedi.",
            show_alert=True,
        )
        return

    # --------------------------------------------------------
    # KATIL
    # --------------------------------------------------------

    if query.data == "join":

        if chat_id is None:
            await query.answer(
                "Oyun grubu bulunamadı.",
                show_alert=True,
            )
            return

        try:
            db.add_user(
                user.id,
                user.username,
                user.first_name,
            )
        except Exception:
            pass

        result = join_game(
            chat_id,
            user.id,
            user.first_name,
        )

        if (
            result is False
            or result == "ALREADY_JOINED"
        ):
            await query.answer(
                "Zaten oyundasın.",
                show_alert=True,
            )
            return

        if result == "NO_GAME":
            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True,
            )
            return

        await query.answer(
            "✅ Oyuna katıldın!"
        )

        players = games[chat_id]["players"]

        text = (
            "🎮 <b>Meyus UNO Lobisi</b>\n\n"
            f"👥 Oyuncular ({len(players)})\n\n"
        )

        for p in players:
            text += (
                f"• {html_escape(p['name'])}\n"
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
                    "▶️ Başlat",
                    callback_data="start_game",
                )
            ],
        ]

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return

    # --------------------------------------------------------
    # BAŞLAT
    # --------------------------------------------------------

    if query.data == "start_game":

        if chat_id not in games:
            await query.answer(
                "Oyun bulunamadı.",
                show_alert=True,
            )
            return

        if games[chat_id].get("started"):
            await query.answer(
                "Oyun zaten başladı.",
                show_alert=True,
            )
            return

        if len(
            games[chat_id].get("players", [])
        ) < 2:
            await query.answer(
                "En az 2 oyuncu gerekli.",
                show_alert=True,
            )
            return

        await query.answer(
            "🎉 Oyun başlatılıyor..."
        )

        try:
            await query.edit_message_text(
                "🎉 Oyun başlatılıyor..."
            )
        except Exception:
            pass

        started = await _do_start_game(
            context,
            chat_id,
        )

        if not started:
            await context.bot.send_message(
                chat_id,
                (
                    "❌ Oyun başlatılamadı.\n"
                    "Lütfen /oyun ile yeni bir lobi oluşturun."
                ),
            )

        return

    # --------------------------------------------------------
    # RENK SEÇ
    # --------------------------------------------------------

    if query.data.startswith("renk:"):

        try:
            _, color, target_uid = (
                query.data.split(":")
            )

            target_uid = int(target_uid)

        except Exception:
            await query.answer(
                "Geçersiz renk seçimi.",
                show_alert=True,
            )
            return

        if user.id != target_uid:
            await query.answer(
                "Sadece kartı oynayan kişi rengi seçebilir.",
                show_alert=True,
            )
            return

        ok = choose_color(
            chat_id,
            user.id,
            color,
        )

        if not ok:
            await query.answer(
                "Bu işlem artık geçerli değil.",
                show_alert=True,
            )
            return

        await query.answer(
            f"Renk: {COLOR_NAME_TR.get(color, color)}"
        )

        game = games.get(chat_id)

        if not game:
            return

        await context.bot.send_message(
            chat_id,
            (
                f"🎨 "
                f"{mention_html(user.id, player_name(game, user.id))} "
                f"rengi <b>"
                f"{html_escape(COLOR_NAME_TR.get(color, color))}"
                f"</b> seçti."
            ),
            parse_mode="HTML",
        )

        if game.get("winner"):
            await finish_game(
                context,
                chat_id,
                game["winner"],
            )
        else:
            await announce_turn(
                context,
                chat_id,
            )

        return


# ============================================================
# /KATIL
# ============================================================

async def katil(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    db.add_user(
        user.id,
        user.username,
        user.first_name,
    )

    result = join_game(
        chat.id,
        user.id,
        user.first_name,
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

    oyuncu = len(
        games[chat.id]["players"]
    )

    await update.message.reply_text(
        (
            f"✅ {html_escape(user.first_name)} "
            f"oyuna katıldı!\n\n"
            f"👥 Toplam oyuncu: {oyuncu}"
        ),
        parse_mode="HTML",
    )


# ============================================================
# /BASLAT
# ============================================================

async def baslat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        await update.message.reply_text(
            "❌ Önce /oyun oluştur."
        )
        return

    if games[chat_id].get("started"):
        await update.message.reply_text(
            "ℹ️ Oyun zaten başladı."
        )
        return

    if len(
        games[chat_id].get("players", [])
    ) < 2:
        await update.message.reply_text(
            "❌ En az 2 oyuncu gerekli."
        )
        return

    started = await _do_start_game(
        context,
        chat_id,
    )

    if not started:
        await update.message.reply_text(
            "❌ Oyun başlatılamadı. Lütfen tekrar deneyin."
        )


# ============================================================
# /STICKERLAR
# ============================================================

async def stickerlar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        sticker_set = await get_sticker_set(
            context.bot,
            STICKER_SET_NAME,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Sticker paketi alınamadı:\n{e}"
        )
        return

    lines = [
        (
            f"📦 Paket: {sticker_set.name} "
            f"({len(sticker_set.stickers)} sticker)\n"
        )
    ]

    for idx, sticker in enumerate(
        sticker_set.stickers
    ):
        lines.append(
            f"{idx}: {sticker.emoji or '—'}"
        )

    text = "\n".join(lines)

    # Telegram mesaj limiti
    for i in range(
        0,
        len(text),
        3500,
    ):
        await update.message.reply_text(
            text[i:i + 3500]
        )


# ============================================================
# /CEK
# ============================================================

async def cek(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
            "❌ Bu komutu oynadığın oyunun grubunda kullan."
        )
        return

    if current_player(chat_id) != user.id:
        await update.message.reply_text(
            "⏳ Sıra sende değil."
        )
        return

    res = draw_card(
        chat_id,
        user.id,
    )

    if not res["ok"]:
        await update.message.reply_text(
            "❌ Kart çekilemedi."
        )
        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id),
    )

    n = len(
        res.get("drawn", [])
    )

    if n:
        await update.message.reply_html(
            f"🃏 {actor_mention} "
            f"kart çekti ({n} kart)."
        )
    else:
        await update.message.reply_html(
            f"🃏 {actor_mention} "
            f"çekmek istedi ama deste boş."
        )

    if not game.get("winner"):
        await update.message.reply_html(
            (
                "Şimdi çektiğin kartı oynayabilir "
                "ya da /pas ile sırayı geçebilirsin.\n"
                "Elini görmek için 🎴 butonuna dokun."
            )
        )


# ============================================================
# /PAS
# ============================================================

async def pas(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
            "❌ Bu komutu oynadığın oyunun grubunda kullan."
        )
        return

    res = pass_turn(
        chat_id,
        user.id,
    )

    if not res["ok"]:
        reasons = {
            "SIRA_DEGIL": "⏳ Sıra sende değil.",
            "ONCE_CEK": (
                "❌ Pas geçmeden önce kart çekmelisin (/cek)."
            ),
            "OYUN_YOK": (
                "❌ Aktif bir oyun bulunamadı."
            ),
        }

        await update.message.reply_text(
            reasons.get(
                res.get("reason"),
                "❌ Pas geçilemedi.",
            )
        )
        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id),
    )

    await context.bot.send_message(
        chat_id,
        f"⏭ {actor_mention} pas geçti.",
        parse_mode="HTML",
    )

    await announce_turn(
        context,
        chat_id,
    )


# ============================================================
# INLINE KARTLAR
# ============================================================

async def inline_hand(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    inline_query = update.inline_query

    if not inline_query:
        return

    user = inline_query.from_user

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    # --------------------------------------------------------
    # AKTİF OYUN YOK
    # --------------------------------------------------------

    if not game:

        # switch_pm_text ve switch_pm_parameter
        # YERİNE yeni Telegram API sistemi:
        # InlineQueryResultsButton kullanılıyor.
        await inline_query.answer(
            [],
            button=InlineQueryResultsButton(
                text="Aktif bir oyunda değilsin",
                start_parameter="no_game",
            ),
            cache_time=1,
            is_personal=True,
        )

        return

    my_turn = (
        current_player(chat_id)
        == user.id
    )

    hand = game.get(
        "hands",
        {}
    ).get(
        user.id,
        [],
    )

    legal = (
        set(
            legal_cards_for(
                chat_id,
                user.id,
            )
        )
        if my_turn
        else set()
    )

    cache_chat_id = (
        STORAGE_CHAT_ID or chat_id
    )

    results = []

    # --------------------------------------------------------
    # KARTLAR
    # --------------------------------------------------------

    for idx, card_code in enumerate(hand):

        sticker_file_id = None

        is_illegal = (
            my_turn
            and card_code not in legal
        )

        result_id_prefix = (
            "illegal:"
            if is_illegal
            else ""
        )

        # Sticker
        if card_code in CARD_TO_STICKER_INDEX:

            try:
                sticker_file_id = (
                    await get_card_sticker_file_id(
                        context.bot,
                        STICKER_SET_NAME,
                        card_code,
                        CARD_TO_STICKER_INDEX[
                            card_code
                        ],
                    )
                )

            except Exception as e:
                print(
                    f"⚠️ Sticker alınamadı "
                    f"({card_code}): {e}"
                )

        if sticker_file_id:

            results.append(
                InlineQueryResultCachedSticker(
                    id=(
                        f"{result_id_prefix}"
                        f"{card_code}#{idx}"
                    ),
                    sticker_file_id=sticker_file_id,
                )
            )

            continue

        # Fotoğraf
        try:
            file_id = await get_card_file_id(
                context.bot,
                card_code,
                cache_chat_id,
            )

        except Exception as e:
            print(
                f"⚠️ Kart görseli yüklenemedi "
                f"({card_code}): {e}"
            )
            continue

        results.append(
            InlineQueryResultCachedPhoto(
                id=(
                    f"{result_id_prefix}"
                    f"{card_code}#{idx}"
                ),
                photo_file_id=file_id,
            )
        )

    # --------------------------------------------------------
    # BİLGİ İKONU
    # --------------------------------------------------------

    try:
        info_file_id = (
            await get_local_icon_file_id(
                context.bot,
                INFO_ICON_CODE,
                info_icon_bytes(),
            )
        )

        results.append(
            InlineQueryResultCachedPhoto(
                id="info",
                photo_file_id=info_file_id,
            )
        )

    except Exception as e:

        print(
            f"⚠️ Bilgi ikonu yüklenemedi: {e}"
        )

        results.append(
            InlineQueryResultArticle(
                id="info",
                title="❓ Kart Durumu",
                input_message_content=(
                    InputTextMessageContent(
                        "❓ Kart durumu"
                    )
                ),
            )
        )

    # --------------------------------------------------------
    # SADECE SIRA BENDeyse
    # --------------------------------------------------------

    if my_turn:

        has_drawn = (
            game.get(
                "has_drawn",
                {}
            ).get(
                user.id,
                False,
            )
        )

        # Deste
        try:

            deck_file_id = (
                await get_card_file_id(
                    context.bot,
                    DECK_BACK_CODE,
                    cache_chat_id,
                )
            )

            results.append(
                InlineQueryResultCachedPhoto(
                    id="draw",
                    photo_file_id=deck_file_id,
                )
            )

        except Exception as e:

            print(
                f"⚠️ Deste görseli yüklenemedi: {e}"
            )

        # Pas
        if has_drawn:

            try:

                pass_file_id = (
                    await get_local_icon_file_id(
                        context.bot,
                        PASS_ICON_CODE,
                        pass_icon_bytes(),
                    )
                )

                results.append(
                    InlineQueryResultCachedPhoto(
                        id="pass",
                        photo_file_id=pass_file_id,
                    )
                )

            except Exception as e:

                print(
                    f"⚠️ Pas ikonu yüklenemedi: {e}"
                )

                results.append(
                    InlineQueryResultArticle(
                        id="pass",
                        title="⏭ Pas",
                        input_message_content=(
                            InputTextMessageContent(
                                "⏭ Pas geç"
                            )
                        ),
                    )
                )

    # --------------------------------------------------------
    # TELEGRAM'A SONUÇLARI GÖNDER
    # --------------------------------------------------------

    await inline_query.answer(
        results,
        cache_time=1,
        is_personal=True,
    )


# ============================================================
# CHOSEN INLINE RESULT
# ============================================================

async def chosen_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chosen = update.chosen_inline_result

    if not chosen:
        return

    user = chosen.from_user
    result_id = chosen.result_id

    # --------------------------------------------------------
    # GEÇERSİZ KART
    # --------------------------------------------------------

    if result_id.startswith(
        "illegal:"
    ):
        return

    chat_id, game = (
        find_active_game_for_user(
            user.id
        )
    )

    if not game:
        return

    actor_mention = mention_html(
        user.id,
        player_name(game, user.id),
    )

    # --------------------------------------------------------
    # INFO
    # --------------------------------------------------------

    if result_id == "info":

        lines = [
            "📊 <b>Kart Durumu</b>\n"
        ]

        for p in game.get(
            "players",
            []
        ):

            count = len(
                game.get(
                    "hands",
                    {}
                ).get(
                    p["id"],
                    [],
                )
            )

            lines.append(
                f"• {html_escape(p['name'])}: "
                f"{count} kart"
            )

        await context.bot.send_message(
            chat_id,
            "\n".join(lines),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # KART ÇEK
    # --------------------------------------------------------

    if result_id == "draw":

        res = draw_card(
            chat_id,
            user.id,
        )

        if not res["ok"]:
            return

        n = len(
            res.get(
                "drawn",
                []
            )
        )

        await context.bot.send_message(
            chat_id,
            (
                f"🃏 {actor_mention} "
                f"kart çekti ({n} kart)."
                if n
                else
                f"🃏 {actor_mention} "
                f"çekmek istedi ama deste boş."
            ),
            parse_mode="HTML",
        )

        if not game.get("winner"):
            await announce_turn(
                context,
                chat_id,
            )

        return

    # --------------------------------------------------------
    # PAS
    # --------------------------------------------------------

    if result_id == "pass":

        res = pass_turn(
            chat_id,
            user.id,
        )

        if not res["ok"]:

            reasons = {
                "SIRA_DEGIL": (
                    "sıra artık sende değildi"
                ),
                "ONCE_CEK": (
                    "önce kart çekmen gerekiyordu"
                ),
                "OYUN_YOK": (
                    "aktif bir oyun bulunamadı"
                ),
            }

            reason = reasons.get(
                res.get("reason"),
                "işlenemedi",
            )

            await context.bot.send_message(
                chat_id,
                (
                    f"⚠️ {actor_mention} "
                    f"pas geçmeye çalıştı ama işlenmedi "
                    f"({reason})."
                ),
                parse_mode="HTML",
            )

            return

        await context.bot.send_message(
            chat_id,
            f"⏭ {actor_mention} pas geçti.",
            parse_mode="HTML",
        )

        await announce_turn(
            context,
            chat_id,
        )

        return

    # --------------------------------------------------------
    # KART OYNA
    # --------------------------------------------------------

    card_code = result_id.split(
        "#",
        1,
    )[0]

    res = play_card(
        chat_id,
        user.id,
        card_code,
    )

    # --------------------------------------------------------
    # GEÇERSİZ HAMLE
    # --------------------------------------------------------

    if not res["ok"]:

        if chosen.inline_message_id:

            try:

                await context.bot.edit_message_reply_markup(
                    inline_message_id=(
                        chosen.inline_message_id
                    ),
                    reply_markup=(
                        InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        "❌ Geçersiz hamle",
                                        callback_data="noop",
                                    )
                                ]
                            ]
                        )
                    ),
                )

            except Exception as e:

                print(
                    f"⚠️ Geçersiz kart "
                    f"işaretlenemedi: {e}"
                )

        return

    # --------------------------------------------------------
    # KAZANAN
    # --------------------------------------------------------

    if res.get("win"):

        await finish_game(
            context,
            chat_id,
            user.id,
        )

        return

    # --------------------------------------------------------
    # UNO
    # --------------------------------------------------------

    if res.get("remaining") == 1:

        await context.bot.send_message(
            chat_id,
            (
                f"🎉 {actor_mention} "
                f"<b>UNO!</b> "
                f"Elinde sadece 1 kart kaldı!"
            ),
            parse_mode="HTML",
        )

    # --------------------------------------------------------
    # JOKER RENK SEÇİMİ
    # --------------------------------------------------------

    if res.get("needs_color"):

        keyboard = [
            [
                InlineKeyboardButton(
                    (
                        f"{COLOR_LABELS[c]} "
                        f"{COLOR_NAME_TR[c]}"
                    ),
                    callback_data=(
                        f"renk:{c}:{user.id}"
                    ),
                )
                for c in [
                    "kirmizi",
                    "yesil",
                ]
            ],
            [
                InlineKeyboardButton(
                    (
                        f"{COLOR_LABELS[c]} "
                        f"{COLOR_NAME_TR[c]}"
                    ),
                    callback_data=(
                        f"renk:{c}:{user.id}"
                    ),
                )
                for c in [
                    "mavi",
                    "sari",
                ]
            ],
        ]

        await context.bot.send_message(
            chat_id,
            (
                f"🎨 {actor_mention}, "
                f"joker için bir renk seç:"
            ),
            reply_markup=(
                InlineKeyboardMarkup(
                    keyboard
                )
            ),
            parse_mode="HTML",
        )

        return

    # --------------------------------------------------------
    # KART ETKİSİ
    # --------------------------------------------------------

    effect = res.get(
        "effect"
    )

    if effect in (
        "skip",
        "reverse",
    ):

        await announce_effect(
            context,
            chat_id,
            actor_mention,
            effect,
        )

    elif effect in (
        "draw2",
        "draw4",
    ):

        try:
            next_uid = current_player(
                chat_id
            )

            next_mention = mention_html(
                next_uid,
                player_name(
                    game,
                    next_uid,
                ),
            )

            await announce_effect(
                context,
                chat_id,
                actor_mention,
                effect,
                next_mention,
            )

        except Exception:
            pass

    await announce_turn(
        context,
        chat_id,
    )


# ============================================================
# /BITIR
# ============================================================

async def bitir(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in games:

        await update.message.reply_text(
            "❌ Bu grupta açık bir oyun yok."
        )

        return

    game = games[chat_id]

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
                    user.id,
                )
            )

            is_admin = member.status in (
                "administrator",
                "creator",
            )

        except Exception:

            is_admin = False

    if not (
        is_owner
        or is_admin
    ):

        await update.message.reply_text(
            (
                "⛔ Sadece oyunu açan kişi "
                "veya grup yöneticileri "
                "/bitir kullanabilir."
            )
        )

        return

    was_started = game.get(
        "started",
        False,
    )

    try:
        end_game(chat_id)
    except Exception as e:
        print(
            f"⚠️ Oyun kapatılırken hata: {e}"
        )

    try:
        lobby_messages.pop(
            chat_id,
            None,
        )
    except Exception:
        pass

    if was_started:

        await update.message.reply_text(
            (
                f"🛑 Oyun "
                f"{html_escape(user.first_name)} "
                f"tarafından sonlandırıldı.\n\n"
                f"Yeni oyun için /oyun yazabilirsiniz."
            ),
            parse_mode="HTML",
        )

    else:

        await update.message.reply_text(
            (
                f"🛑 Lobi "
                f"{html_escape(user.first_name)} "
                f"tarafından kapatıldı.\n\n"
                f"Yeni oyun için /oyun yazabilirsiniz."
            ),
            parse_mode="HTML",
        )


# ============================================================
# /PROFIL
# ============================================================

async def profil(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_obj = update.effective_user

    db.add_user(
        user_obj.id,
        user_obj.username,
        user_obj.first_name,
    )

    user = db.get_user(
        user_obj.id
    )

    if not user:

        await update.message.reply_text(
            "❌ Profil oluşturulamadı, tekrar dener misin?"
        )

        return

    await update.message.reply_text(
        (
            "👤 <b>Profil</b>\n\n"
            f"💰 Coin: {user[3]}\n"
            f"🏆 Galibiyet: {user[4]}\n"
            f"🎮 Oyun: {user[5]}\n"
            f"📈 Seviye: {user[6]}\n"
            f"✨ XP: {user[7]}"
        ),
        parse_mode="HTML",
    )


# ============================================================
# /SIRALAMA
# ============================================================

async def siralama(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    top = db.get_weekly_leaderboard(
        10
    )

    if not top:

        await update.message.reply_text(
            "🎮 Bu hafta henüz kimse oyun bitirmedi."
        )

        return

    madalya = [
        "🥇",
        "🥈",
        "🥉",
    ]

    lines = [
        "🏆 <b>Haftalık Sıralama</b> "
        "(İlk 10)\n"
    ]

    for i, (
        uid,
        name,
        wins,
        games_count,
    ) in enumerate(top):

        rank = (
            madalya[i]
            if i < 3
            else f"{i + 1}."
        )

        lines.append(
            (
                f"{rank} "
                f"{html_escape(name)} — "
                f"🏆 {wins} galibiyet "
                f"({games_count} oyun)"
            )
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
    )


# ============================================================
# /YARDIM
# ============================================================

async def yardim(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "📖 <b>Meyus UNO Yardım</b>\n\n"
        "/start — Botu başlatır\n"
        "/oyun — Yeni oyun oluşturur\n"
        "/katil — Oyuna katılır\n"
        "/baslat — Oyunu başlatır\n"
        "/bitir — Oyunu/lobiyi sonlandırır\n"
        "/profil — Profilini gösterir\n"
        "/siralama — Haftalık sıralamayı gösterir\n"
        "/cek — Sıra sendeyken kart çeker\n"
        "/pas — Kart çektikten sonra sırayı geçer\n\n"
        "🎴 Her an "
        "<b>Kartlarımı Gör / Oyna</b> "
        "butonuna dokunarak elini görebilirsin.\n\n"
        "🎯 Sıra sende olduğunda oynanabilir "
        "kartlar, deste ve pas seçeneği "
        "otomatik olarak görünür."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )


# ============================================================
# CHAT MIGRATION
# ============================================================

def _migrate_chat(
    old_chat_id,
    new_chat_id,
):
    """
    Grup süper gruba yükseltilince
    oyun/lobi verisini yeni chat_id'ye taşır.
    """

    if old_chat_id in games:

        game = games.pop(
            old_chat_id
        )

        games[new_chat_id] = game

        for uid in game.get(
            "hands",
            {}
        ).keys():

            if (
                user_active_chat.get(uid)
                == old_chat_id
            ):

                user_active_chat[uid] = (
                    new_chat_id
                )

    if old_chat_id in lobby_messages:

        lobby_messages[
            new_chat_id
        ] = lobby_messages.pop(
            old_chat_id
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):
    err = context.error

    if isinstance(
        err,
        ChatMigrated,
    ):

        old_chat_id = None

        if (
            update
            and getattr(
                update,
                "effective_chat",
                None,
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
                new_chat_id,
            )

        try:

            await context.bot.send_message(
                new_chat_id,
                (
                    "ℹ️ Bu grup süper gruba yükseltildi.\n\n"
                    "Oyun verisi yeni gruba taşındı.\n"
                    "Devam etmek için tekrar "
                    "🎴 <b>Kartlarımı Gör / Oyna</b> "
                    "butonuna dokunabilirsiniz."
                ),
                parse_mode="HTML",
            )

        except Exception:
            pass

        return

    print(
        f"⚠️ Beklenmeyen hata: {err}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN bulunamadı!"
        )

        return

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # KOMUTLAR
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "yardim",
            yardim,
        )
    )

    app.add_handler(
        CommandHandler(
            "oyun",
            oyun,
        )
    )

    app.add_handler(
        CommandHandler(
            "katil",
            katil,
        )
    )

    app.add_handler(
        CommandHandler(
            "baslat",
            baslat,
        )
    )

    app.add_handler(
        CommandHandler(
            "bitir",
            bitir,
        )
    )

    app.add_handler(
        CommandHandler(
            "profil",
            profil,
        )
    )

    app.add_handler(
        CommandHandler(
            "cek",
            cek,
        )
    )

    app.add_handler(
        CommandHandler(
            "pas",
            pas,
        )
    )

    app.add_handler(
        CommandHandler(
            "stickerlar",
            stickerlar,
        )
    )

    app.add_handler(
        CommandHandler(
            "siralama",
            siralama,
        )
    )

    # --------------------------------------------------------
    # CALLBACK
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            button
        )
    )

    # --------------------------------------------------------
    # INLINE MODE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    app.add_error_handler(
        error_handler
    )

    print(
        "✅ Meyus UNO başlatıldı!"
    )

    # --------------------------------------------------------
    # POLLING
    # --------------------------------------------------------

    app.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# BAŞLAT
# ============================================================

if __name__ == "__main__":
    main()
