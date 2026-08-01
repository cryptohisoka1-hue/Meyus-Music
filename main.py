import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
import random

# Günlük kayıtlarını (log) etkinleştir
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Basit bir Uno destesi (Sadece renkler ve temel sayılar)
RENKLER = ['Kırmızı', 'Mavi', 'Yeşil', 'Sarı']
NUMARALAR = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

def yeni_deste():
    deste = [f"{renk} {no}" for renk in RENKLER for no in NUMARALAR]
    random.shuffle(deste)
    return deste

# Oyun durumunu tutacağımız sözlük
oyun_durumu = {}

async def baslat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    deste = yeni_deste()
    
    # Masaya bir kart aç
    yerdeki_kart = deste.pop()
    
    oyun_durumu[chat_id] = {
        'deste': deste,
        'yerdeki_kart': yerdeki_kart,
        'oyuncular': {},
        'sira': None
    }
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f" Uno Oyunu Başladı! 🎉\n\nYerdeki Kart: 🃏 **{yerdeki_kart}**\nOynamak için /katil yazın."
    )

async def katil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    kullanici = update.effective_user
    
    if chat_id not in oyun_durumu:
        await update.message.reply_text("Lütfen önce /baslat komutuyla bir oyun başlatın.")
        return

    if kullanici.id not in oyun_durumu[chat_id]['oyuncular']:
        # Oyuncuya 7 kart dağıt
        kartlar = [oyun_durumu[chat_id]['deste'].pop() for _ in range(7)]
        oyun_durumu[chat_id]['oyuncular'][kullanici.id] = {
            'isim': kullanici.first_name,
            'kartlar': kartlar
        }
        await update.message.reply_text(f"{kullanici.first_name} oyuna katıldı! Kartlarınız özelden gönderildi.")
        
        # Kartları oyuncuya özel mesaj (DM) olarak gönder
        kartlar_metin = "\n".join(kartlar)
        await context.bot.send_message(
            chat_id=kullanici.id,
            text=f"Kartlarınız:\n\n{kartlar_metin}"
        )
    else:
        await update.message.reply_text("Zaten oyundasınız!")

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in oyun_durumu:
        return

    yerdeki_kart = oyun_durumu[chat_id]['yerdeki_kart']
    await update.message.reply_text(f"Yerdeki Kart: 🃏 **{yerdeki_kart}**")

if __name__ == '__main__':
    # TOKEN kısmına BotFather'dan aldığınız anahtarı yapıştırın
    application = ApplicationBuilder().token("TOKEN_BURAYA").build()
    
    application.add_handler(CommandHandler("baslat", baslat))
    application.add_handler(CommandHandler("katil", katil))
    application.add_handler(CommandHandler("durum", durum))
    
    print("Bot çalışıyor...")
    application.run_polling()
    
