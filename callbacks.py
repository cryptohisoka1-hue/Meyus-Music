import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import THEME_PACKS, DEFAULT_THEME, CARD_FACES, COLOR_EMOJI, COLORS, MIN_PLAYERS, MAX_PLAYERS
from game import UnoGame, card_label
import database as db

logger = logging.getLogger(__name__)

GAMES = {}              # chat_id -> UnoGame
THEME_STICKERS = {}      # theme_key -> [file_id, ...]


async def load_all_themes(bot):
    for key, pack_name in THEME_PACKS.items():
        try:
            sticker_set = await bot.get_sticker_set(pack_name)
            THEME_STICKERS[key] = [s.file_id for s in sticker_set.stickers]
            logger.info(f"Tema yüklendi: {key} ({len(THEME_STICKERS[key])} sticker)")
        except TelegramError as e:
            logger.warning(f"Tema yüklenemedi ({key} -> {pack_name}): {e}")


def card_sticker(theme, card):
    file_ids = THEME_STICKERS.get(theme)
    if not file_ids:
        return None
    idx = CARD_FACES.index(card)
    return file_ids[idx % len(file_ids)]


# ================= KOMUTLAR =================

async def cmd_oyun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in GAMES and GAMES[chat_id].state != "finished":
        await update.message.reply_text("Bu grupta zaten aktif bir lobi/oyun var. Bitirmek için /bitir yaz.")
        return
    game = UnoGame(chat_id, update.effective_user.id)
    game.add_player(update.effective_user.id, update.effective_user.first_name)
    GAMES[chat_id] = game
    await send_lobby(update.effective_chat.id, context)


async def send_lobby(chat_id, context):
    game = GAMES[chat_id]
    text = (
        f"🎮 *UNO Lobisi Açıldı!*\n\n"
        f"Katılımcılar ({len(game.players)}/{MAX_PLAYERS}):\n"
        + "\n".join(f"• {p['name']}" for p in game.players.values())
        + f"\n\nTema: {game.theme}\n\nKatılmak için aşağıdaki butona bas."
    )
    kb = [
        [InlineKeyboardButton("➕ Katıl", callback_data="join")],
        [InlineKeyboardButton(f"🎨 Tema: {game.theme}", callback_data="theme_menu")],
        [InlineKeyboardButton("🚀 Başlat", callback_data="startgame")],
    ]
    await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


async def cmd_bitir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = GAMES.get(chat_id)
    if not game:
        await update.message.reply_text("Aktif bir oyun/lobi yok.")
        return
    if update.effective_user.id != game.host_id:
        await update.message.reply_text("Sadece lobiyi açan kişi oyunu bitirebilir.")
        return
    del GAMES[chat_id]
    await update.message.reply_text("🛑 Oyun sonlandırıldı.")


async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_weekly_ranking(10)
    if not rows:
        await update.message.reply_text("Bu hafta henüz kazanan yok.")
        return
    lines = ["🏆 *Haftalık Sıralama*\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = r["first_name"] or r["username"] or "Oyuncu"
        lines.append(f"{medal} {name} — {r['weekly_wins']} galibiyet")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    p = db.get_profile(user.id)
    if not p or p["games_played"] == 0:
        await update.message.reply_text("Henüz hiç oyun oynamadın. /oyun ile başla!")
        return
    win_rate = (p["wins"] / p["games_played"]) * 100
    text = (
        f"👤 *{user.first_name} - Profil*\n\n"
        f"Oynanan oyun: {p['games_played']}\n"
        f"Galibiyet: {p['wins']}\n"
        f"Kazanma oranı: %{win_rate:.1f}\n"
        f"Oynanan toplam kart: {p['cards_played']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ================= CALLBACK QUERY =================

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id
    user = query.from_user
    game = GAMES.get(chat_id)

    if data == "noop":
        await query.answer("Bu kartı şu an oynayamazsın.", show_alert=False)
        return

    if data == "join":
        if not game or game.state != "lobby":
            await query.answer("Lobi bulunamadı.", show_alert=True)
            return
        if len(game.players) >= MAX_PLAYERS:
            await query.answer("Lobi dolu.", show_alert=True)
            return
        added = game.add_player(user.id, user.first_name)
        db.upsert_user(user.id, user.username, user.first_name)
        await query.answer("Katıldın!" if added else "Zaten lobidesin.")
        await refresh_lobby_message(query, game)
        return

    if data == "theme_menu":
        kb = [[InlineKeyboardButton(k, callback_data=f"settheme|{k}")] for k in THEME_PACKS.keys()]
        kb.append([InlineKeyboardButton("⬅️ Geri", callback_data="back_lobby")])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(kb))
        await query.answer()
        return

    if data.startswith("settheme|"):
        theme = data.split("|", 1)[1]
        if game:
            game.theme = theme
        await query.answer(f"Tema: {theme}")
        await refresh_lobby_message(query, game)
        return

    if data == "back_lobby":
        await refresh_lobby_message(query, game)
        await query.answer()
        return

    if data == "startgame":
        if not game or game.state != "lobby":
            await query.answer("Lobi bulunamadı.", show_alert=True)
            return
        if user.id != game.host_id:
            await query.answer("Sadece lobiyi açan kişi başlatabilir.", show_alert=True)
            return
        if len(game.players) < MIN_PLAYERS:
            await query.answer(f"En az {MIN_PLAYERS} oyuncu gerekli.", show_alert=True)
            return
        game.start()
        await query.answer("Oyun başladı!")
        await query.edit_message_text("🎮 Oyun başladı! Kartlar dağıtıldı.")
        await send_turn(chat_id, context)
        return

    # ---- oyun içi ----
    if not game or game.state != "playing":
        await query.answer("Aktif oyun yok.", show_alert=True)
        return

    if data == "draw":
        if game.current_player != user.id:
            await query.answer("Sıra sende değil.", show_alert=True)
            return
        game.draw_cards(user.id, 1)
        game.advance_turn(1)
        await query.answer("Kart çektin.")
        await send_turn(chat_id, context)
        return

    if data.startswith("play|"):
        card = data.split("|", 1)[1]
        if card in ("Wild", "Wild4"):
            if game.current_player != user.id:
                await query.answer("Sıra sende değil.", show_alert=True)
                return
            kb = [[InlineKeyboardButton(f"{COLOR_EMOJI[c]}", callback_data=f"pickcolor|{card}|{c}")] for c in COLORS]
            await query.edit_message_reply_markup(InlineKeyboardMarkup(kb))
            await query.answer("Renk seç")
            return
        ok, result = game.play_card(user.id, card)
        if not ok:
            await query.answer(result, show_alert=True)
            return
        db.record_card_played(user.id)
        await query.answer()
        if result == "WIN":
            await finish_game(chat_id, context, user)
            return
        await send_turn(chat_id, context)
        return

    if data.startswith("pickcolor|"):
        _, card, color = data.split("|")
        if game.current_player != user.id:
            await query.answer("Sıra sende değil.", show_alert=True)
            return
        ok, result = game.play_card(user.id, card, chosen_color=color)
        if not ok:
            await query.answer(result, show_alert=True)
            return
        db.record_card_played(user.id)
        await query.answer()
        if result == "WIN":
            await finish_game(chat_id, context, user)
            return
        await send_turn(chat_id, context)
        return


async def refresh_lobby_message(query, game):
    if not game:
        return
    text = (
        f"🎮 *UNO Lobisi Açıldı!*\n\n"
        f"Katılımcılar ({len(game.players)}/{MAX_PLAYERS}):\n"
        + "\n".join(f"• {p['name']}" for p in game.players.values())
        + f"\n\nTema: {game.theme}\n\nKatılmak için aşağıdaki butona bas."
    )
    kb = [
        [InlineKeyboardButton("➕ Katıl", callback_data="join")],
        [InlineKeyboardButton(f"🎨 Tema: {game.theme}", callback_data="theme_menu")],
        [InlineKeyboardButton("🚀 Başlat", callback_data="startgame")],
    ]
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    except TelegramError:
        pass


# ================= OYUN AKIŞI =================

async def send_turn(chat_id, context: ContextTypes.DEFAULT_TYPE):
    game = GAMES[chat_id]
    uid = game.current_player
    name = game.players[uid]["name"]

    # önceki sıra mesajını sil
    if game.pending_message_id:
        try:
            await context.bot.delete_message(chat_id, game.pending_message_id)
        except TelegramError:
            pass

    sticker_id = card_sticker(game.theme, game.top_card)
    if sticker_id:
        try:
            await context.bot.send_sticker(chat_id, sticker_id)
        except TelegramError:
            pass

    header = (
        f"🔔 Sıra sende, <a href='tg://user?id={uid}'>{name}</a>!\n"
        f"Üstteki kart: {card_label(game.top_card)}  |  Renk: {COLOR_EMOJI[game.current_color]}\n"
        f"Yön: {'⏩' if game.direction == 1 else '⏪'}"
    )

    hand = game.players[uid]["hand"]
    kb = []
    for card in hand:
        playable = game.is_playable(card)
        label = card_label(card) if playable else f"🔒{card_label(card)}"
        cb = f"play|{card}" if playable else "noop"
        kb.append([InlineKeyboardButton(label, callback_data=cb)])
    kb.append([InlineKeyboardButton("🃏 Kart Çek", callback_data="draw")])

    msg = await context.bot.send_message(
        chat_id, header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )
    game.pending_message_id = msg.message_id


async def finish_game(chat_id, context: ContextTypes.DEFAULT_TYPE, winner):
    game = GAMES[chat_id]
    db.record_game_result(chat_id, list(game.players.keys()), winner.id)
    await context.bot.send_message(
        chat_id,
        f"🎉 <b>{winner.first_name}</b> oyunu kazandı! Tebrikler!\n\nYeni oyun için /oyun yaz.",
        parse_mode="HTML",
    )
    del GAMES[chat_id]
    
