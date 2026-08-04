import logging

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN
import database as db

from callbacks import (
    cmd_oyun,
    cmd_bitir,
    cmd_siralama,
    cmd_profil,
    on_callback,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def post_init(application):
    logger.info("POST_INIT başladı.")

    # Telegram bağlantısını test et
    try:
        me = await application.bot.get_me()
        logger.info(
            f"TELEGRAM BAĞLANTISI OK: @{me.username} / ID={me.id}"
        )
    except Exception as e:
        logger.exception(
            f"TELEGRAM BAĞLANTI HATASI: {e}"
        )
        return

    # Eski webhook varsa kaldır
    try:
        await application.bot.delete_webhook(
            drop_pending_updates=True
        )
        logger.info("Webhook temizlendi.")
    except Exception as e:
        logger.exception(
            f"Webhook temizleme hatası: {e}"
        )

    logger.info("POST_INIT tamamlandı.")


def main():

    logger.info("main() başladı.")

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN bulunamadı! Railway Variables kısmını kontrol et."
        )

    logger.info("BOT_TOKEN mevcut.")

    # Database
    try:
        db.init_db()
        logger.info("Database hazır.")
    except Exception as e:
        logger.exception(
            f"Database başlatma hatası: {e}"
        )
        raise

    # Normal Telegram istekleri
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )

    # getUpdates için AYRI bağlantı
    polling_request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=30,
        pool_timeout=30,
    )

    logger.info("Application oluşturuluyor...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(polling_request)
        .post_init(post_init)
        .build()
    )

    logger.info("Application oluşturuldu.")

    # Komutlar
    app.add_handler(
        CommandHandler("oyun", cmd_oyun)
    )

    app.add_handler(
        CommandHandler("bitir", cmd_bitir)
    )

    app.add_handler(
        CommandHandler("siralama", cmd_siralama)
    )

    app.add_handler(
        CommandHandler("profil", cmd_profil)
    )

    # Inline butonlar
    app.add_handler(
        CallbackQueryHandler(on_callback)
    )

    logger.info("Handlerlar yüklendi.")
    logger.info("Bot polling başlatılıyor...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[
            "message",
            "callback_query",
        ],
    )


if __name__ == "__main__":
    main()
