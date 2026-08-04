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
    load_all_themes,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# BAŞLANGIÇ
# =========================================================

async def post_init(application):
    """
    Bot başlatılırken Telegram bağlantısını kontrol eder.

    Tema yükleme işlemi arka planda yapılır.
    Böylece sticker API'sindeki timeout botun
    polling başlamasını engellemez.
    """

    logger.info("POST_INIT başladı.")

    # -----------------------------------------------------
    # Telegram bağlantı testi
    # -----------------------------------------------------

    try:
        me = await application.bot.get_me()

        logger.info(
            f"TELEGRAM BAĞLANTISI OK: "
            f"@{me.username} / ID={me.id}"
        )

    except Exception as e:
        logger.exception(
            f"TELEGRAM API BAĞLANTI HATASI: {e}"
        )

    # -----------------------------------------------------
    # Eski webhook'u temizle
    # -----------------------------------------------------

    try:
        await application.bot.delete_webhook(
            drop_pending_updates=True
        )

        logger.info("Eski webhook temizlendi.")

    except Exception as e:
        logger.warning(
            f"Webhook temizlenemedi: {e}"
        )

    # -----------------------------------------------------
    # TEMALARI ARKA PLANDA YÜKLE
    # -----------------------------------------------------
    #
    # Burada await kullanmıyoruz.
    #
    # Eğer sticker setlerinden biri timeout olursa
    # botun polling başlangıcı beklemeyecek.
    #

    try:
        application.create_task(
            load_themes_background(application)
        )

        logger.info(
            "Tema yükleme arka planda başlatıldı."
        )

    except Exception as e:
        logger.warning(
            f"Tema görevi başlatılamadı: {e}"
        )

    logger.info("POST_INIT tamamlandı.")


# =========================================================
# ARKA PLAN TEMA YÜKLEME
# =========================================================

async def load_themes_background(application):
    """
    Temaları bot başladıktan sonra arka planda yükler.

    Tema yüklenemese bile bot çalışmaya devam eder.
    """

    try:

        logger.info(
            "Sticker temaları yükleniyor..."
        )

        await load_all_themes(
            application.bot
        )

        logger.info(
            "Sticker temaları yükleme işlemi tamamlandı."
        )

    except Exception as e:

        logger.warning(
            f"Sticker temaları yüklenemedi: {e}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info("main() başladı.")

    # -----------------------------------------------------
    # BOT TOKEN
    # -----------------------------------------------------

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN bulunamadı! "
            "Railway > Variables kısmından BOT_TOKEN "
            "değerini kontrol et."
        )

    logger.info("BOT_TOKEN mevcut.")

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    try:

        db.init_db()

        logger.info(
            "Database hazır."
        )

    except Exception as e:

        logger.exception(
            f"Database başlatma hatası: {e}"
        )

        raise

    # -----------------------------------------------------
    # NORMAL TELEGRAM REQUEST
    # -----------------------------------------------------

    request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=60,
        http_version="1.1",
    )

    # -----------------------------------------------------
    # POLLING REQUEST
    # -----------------------------------------------------

    polling_request = HTTPXRequest(
        connect_timeout=60,
        read_timeout=90,
        write_timeout=60,
        pool_timeout=60,
        http_version="1.1",
    )

    # -----------------------------------------------------
    # APPLICATION
    # -----------------------------------------------------

    logger.info(
        "Application oluşturuluyor..."
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(polling_request)
        .post_init(post_init)
        .build()
    )

    logger.info(
        "Application oluşturuldu."
    )

    # =====================================================
    # KOMUTLAR
    # =====================================================

    app.add_handler(
        CommandHandler(
            "oyun",
            cmd_oyun
        )
    )

    app.add_handler(
        CommandHandler(
            "bitir",
            cmd_bitir
        )
    )

    app.add_handler(
        CommandHandler(
            "siralama",
            cmd_siralama
        )
    )

    app.add_handler(
        CommandHandler(
            "profil",
            cmd_profil
        )
    )

    # =====================================================
    # INLINE BUTONLAR
    # =====================================================

    app.add_handler(
        CallbackQueryHandler(
            on_callback
        )
    )

    logger.info(
        "Handlerlar yüklendi."
    )

    # =====================================================
    # POLLING
    # =====================================================

    logger.info(
        "Bot polling başlatılıyor..."
    )

    app.run_polling(
        drop_pending_updates=True,

        allowed_updates=[
            "message",
            "callback_query",
        ],

        # Telegram bağlantısında geçici problem
        # olursa birkaç kez tekrar dene.
        bootstrap_retries=5,
    )


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":
    main()
