import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "uno_bot.db")

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    coins INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    games INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def get_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cur.fetchone()

    def add_user(self, user_id, username, first_name):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            conn.commit()

    def add_win(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET wins = wins + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    def add_game(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET games = games + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    def add_coin(self, user_id, amount):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET coins = coins + ? WHERE user_id = ?",
                (amount, user_id)
            )
            conn.commit()

    def add_xp(self, user_id, amount):
        with sqlite3.connect(self.db_path) as conn:
            # XP ekle ve seviye kontrolü
            conn.execute(
                "UPDATE users SET xp = xp + ? WHERE user_id = ?",
                (amount, user_id)
            )
            # Basit seviye sistemi: her 100 XP = 1 seviye
            conn.execute(
                "UPDATE users SET level = (xp / 100) + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

# Global instance
db = Database()
