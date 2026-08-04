import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from config import BOT_TOKEN
import database as db
from callbacks import (
    cmd_oyun, cmd_bitir, cmd_siralama, cmd_profil, on_callback, load_all_themes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application):
    await load_all_themes(application.bot)
    logger.info("Bot hazır.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN ortam değişkeni tanımlı değil! Railway Variables kısmına ekle.")

    db.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("oyun", cmd_oyun))
    app.add_handler(CommandHandler("bitir", cmd_bitir))
    app.add_handler(CommandHandler("siralama", cmd_siralama))
    app.add_handler(CommandHandler("profil", cmd_profil))
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("Bot başlatılıyor (polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
  
