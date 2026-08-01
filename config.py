config_content = '''# Telegram Bot Token'ınızı buraya yazın
# @BotFather'dan alabilirsiniz
BOT_TOKEN = "8832238568:AAH2f7d9UF2rxbRWjcXgnQcChzSvD8C1eKE"

# Veritabanı dosya adı
DATABASE_NAME = "uno_games.db"
'''

with open('/mnt/agents/output/config.py', 'w', encoding='utf-8') as f:
    f.write(config_content)
print("✅ config.py")
