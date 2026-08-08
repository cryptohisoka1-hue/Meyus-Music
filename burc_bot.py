"""
Telegram Burc Yorumu Botu
--------------------------
Belirli aralıklarla gruba otomatik burç yorumu paylaşan bot.
- Bazen tüm 12 burcu tek mesajda paylaşır.
- Bazen tek bir burcun yorumunu paylaşır.
- Ayrıca /burc <isim> ve /burclar komutlarıyla manuel de kullanılabilir.

Kurulum:
    pip install -r requirements.txt

Çalıştırma:
    export BOT_TOKEN="123456:ABC-DEF..."
    export CHAT_ID="-1001234567890"
    python burc_bot.py
"""

import os
import random
import logging
from datetime import datetime, timedelta, time as dtime

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "BURAYA_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "BURAYA_GRUP_CHAT_ID")

# Günde kaç mesaj atılacağı (rastgele saatlerde, min-max arası)
MIN_POSTS_PER_DAY = 4
MAX_POSTS_PER_DAY = 7

# Mesajların atılabileceği saat aralığı (24 saat formatında)
ACTIVE_HOUR_START = 9
ACTIVE_HOUR_END = 23

# Tek burç mu, tüm burçlar mı paylaşılsın olasılığı (tek burç ihtimali)
SINGLE_SIGN_PROBABILITY = 0.7  # %70 tek burç, %30 hepsi birden

BURCLAR = [
    "Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak",
    "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık",
]

BURC_EMOJI = {
    "Koç": "♈", "Boğa": "♉", "İkizler": "♊", "Yengeç": "♋",
    "Aslan": "♌", "Başak": "♍", "Terazi": "♎", "Akrep": "♏",
    "Yay": "♐", "Oğlak": "♑", "Kova": "♒", "Balık": "♓",
}

# ---------------------------------------------------------------------------
# YORUM ÜRETİCİ (yerel, rastgele kombinasyon — dış API'ye bağımlı değil)
# ---------------------------------------------------------------------------
ACILIS = [
    "Bugün enerjin oldukça yüksek, fırsatları değerlendirmek için doğru zaman.",
    "Gökyüzü sana biraz sabır tavsiye ediyor, aceleci adımlardan kaçın.",
    "İçsel sezgilerin bugün seni doğru yöne yönlendirecek.",
    "Yıldızlar bugün senin için yeni kapılar açıyor.",
    "Bugün biraz içine dönme, kendine zaman ayırma günü.",
    "Enerjin dalgalı olabilir, kendine karşı nazik ol.",
    "Bugün cesur adımlar atman için uygun bir gün.",
    "Küçük bir sürpriz seni bekliyor olabilir.",
]

ASK = [
    "aşk hayatında sakinlik ve uyum ön planda.",
    "partnerinle iletişimi güçlendirmek için güzel bir gün.",
    "bekar burçlar için tanışma ihtimali yüksek.",
    "duygusal konularda biraz temkinli olmakta fayda var.",
    "geçmişten biriyle beklenmedik bir iletişim olabilir.",
    "ilişkinde küçük bir kıvılcım seni mutlu edecek.",
]

KARIYER = [
    "iş hayatında yeni bir teklif ya da fırsat kapını çalabilir.",
    "kariyerinde attığın adımların karşılığını almaya başlıyorsun.",
    "iş yerinde bir tartışmadan uzak durman senin yararına olur.",
    "yaratıcılığın bugün iş hayatında öne çıkıyor.",
    "ekip çalışmasında liderlik vasfın ortaya çıkabilir.",
    "finansal konularda dikkatli planlama yapman gerekiyor.",
]

SAGLIK = [
    "enerjini korumak için bugün biraz dinlenmeyi ihmal etme.",
    "spor ya da hareket senin için iyi gelecek.",
    "uyku düzenine dikkat etmen gerekiyor.",
    "stresten uzak durmak için nefes egzersizleri yapabilirsin.",
    "bedeninin sana verdiği sinyalleri dinle.",
]

KAPANIS = [
    "Unutma, yıldızlar yol gösterir ama kararı sen verirsin. ✨",
    "Bugün kendine güven, her şey yoluna girecek. 🌙",
    "Evren senin yanında, sadece adımını at. 🔮",
    "Pozitif kalmaya devam et, iyi şeyler geliyor. ⭐",
]


def burc_yorumu_uret(burc: str) -> str:
    emoji = BURC_EMOJI.get(burc, "✨")
    metin = (
        f"{emoji} *{burc}*\n\n"
        f"{random.choice(ACILIS)}\n\n"
        f"💕 Aşk: {random.choice(ASK)}\n"
        f"💼 Kariyer: {random.choice(KARIYER)}\n"
        f"🌿 Sağlık: {random.choice(SAGLIK)}\n\n"
        f"_{random.choice(KAPANIS)}_"
    )
    return metin


def tum_burclar_mesaji() -> str:
    tarih = datetime.now().strftime("%d.%m.%Y")
    baslik = f"🔮 *Günlük Burç Yorumları* — {tarih}\n\n"
    bolumler = []
    for burc in BURCLAR:
        emoji = BURC_EMOJI.get(burc, "✨")
        bolumler.append(
            f"{emoji} *{burc}*: {random.choice(ASK)} {random.choice(KARIYER)}"
        )
    return baslik + "\n\n".join(bolumler)


# ---------------------------------------------------------------------------
# TELEGRAM KOMUTLARI
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! Ben burç yorumu botuyum. 🔮\n\n"
        "Komutlar:\n"
        "/burc <isim> — tek bir burcun yorumunu al (ör: /burc Aslan)\n"
        "/burclar — tüm burçların yorumunu al"
    )


async def cmd_tek_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Bir burç ismi belirtmelisin. Örnek: /burc Koç\n"
            "Burçlar: " + ", ".join(BURCLAR)
        )
        return
    girilen = " ".join(context.args).strip().title()
    if girilen not in BURCLAR:
        await update.message.reply_text(
            f"'{girilen}' burcunu tanımıyorum. Şunlardan birini dene:\n"
            + ", ".join(BURCLAR)
        )
        return
    await update.message.reply_markdown(burc_yorumu_uret(girilen))


async def cmd_tum_burclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_markdown(tum_burclar_mesaji())


# ---------------------------------------------------------------------------
# OTOMATİK PAYLAŞIM
# ---------------------------------------------------------------------------
async def otomatik_paylas(context: ContextTypes.DEFAULT_TYPE):
    """Zamanlanan her tetiklemede tek burç ya da tüm burçları paylaşır."""
    if random.random() < SINGLE_SIGN_PROBABILITY:
        burc = random.choice(BURCLAR)
        mesaj = burc_yorumu_uret(burc)
    else:
        mesaj = tum_burclar_mesaji()

    await context.bot.send_message(chat_id=CHAT_ID, text=mesaj, parse_mode="Markdown")
    log.info("Otomatik burç mesajı gönderildi.")


def gunluk_rastgele_saatler_planla(scheduler: AsyncIOScheduler, app):
    """Her gün için rastgele sayıda ve rastgele saatte gönderim planlar,
    ve gece yarısı bir sonraki günün planını yeniden oluşturur."""

    # Bugün için önceki planları temizle (job id'leri ile)
    for job in scheduler.get_jobs():
        if job.id.startswith("burc_gonderim_"):
            job.remove()

    adet = random.randint(MIN_POSTS_PER_DAY, MAX_POSTS_PER_DAY)
    simdi = datetime.now()

    secilen_saatler = set()
    while len(secilen_saatler) < adet:
        saat = random.randint(ACTIVE_HOUR_START, ACTIVE_HOUR_END - 1)
        dakika = random.randint(0, 59)
        secilen_saatler.add((saat, dakika))

    for i, (saat, dakika) in enumerate(sorted(secilen_saatler)):
        calisma_zamani = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
        if calisma_zamani < simdi:
            continue  # geçmiş saatleri atla (bot gün ortasında başlatılmışsa)
        scheduler.add_job(
            otomatik_paylas,
            "date",
            run_date=calisma_zamani,
            args=[app],
            id=f"burc_gonderim_{i}",
            replace_existing=True,
        )
        log.info(f"Planlandı: {calisma_zamani}")

    # Bir sonraki günün planını gece yarısı yeniden oluştur
    yarin_gece_yarisi = (simdi + timedelta(days=1)).replace(
        hour=0, minute=1, second=0, microsecond=0
    )
    scheduler.add_job(
        gunluk_rastgele_saatler_planla,
        "date",
        run_date=yarin_gece_yarisi,
        args=[scheduler, app],
        id="gunluk_planlama",
        replace_existing=True,
    )


# ---------------------------------------------------------------------------
# ANA PROGRAM
# ---------------------------------------------------------------------------
def main():
    if BOT_TOKEN == "BURAYA_BOT_TOKEN" or CHAT_ID == "BURAYA_GRUP_CHAT_ID":
        log.warning(
            "BOT_TOKEN ve CHAT_ID ortam değişkenlerini ayarlamadın! "
            "export BOT_TOKEN=... ve export CHAT_ID=... yapman gerekiyor."
        )

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("burc", cmd_tek_burc))
    app.add_handler(CommandHandler("burclar", cmd_tum_burclar))

    scheduler = AsyncIOScheduler()
    scheduler.start()
    gunluk_rastgele_saatler_planla(scheduler, app)

    log.info("Bot başlatıldı, mesajlar bekleniyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
  
