import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN
from telegram.ext import Application


async def main():
    from card_cache import prewarm_all_cards
    from cards_data import ALL_CARD_CODES

    print("🚀 Kart cache oluşturuluyor...")
    print("   (108 kart, her biri ~2.5 saniye = toplam ~4-5 dakika)")
    print("   Flood kontrolüne takılırsa otomatik bekleyecek.\n")

    app = Application.builder().token(BOT_TOKEN).build()
    await prewarm_all_cards(app.bot, None, ALL_CARD_CODES)

    print("\n✅ file_id_cache.json oluştu!")
    print("📁 Şimdi bu dosyayı GitHub'a ekle:")
    print("   git add file_id_cache.json")
    print("   git commit -m 'Add card file_id cache'")
    print("   git push origin main")


if __name__ == "__main__":
    asyncio.run(main())
  
