import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "uno_bot.db")


def _week_start_str(dt=None):
    """Haftanın (Pazartesi 00:00) tarihini 'YYYY-MM-DD' olarak döndürür."""
    dt = dt or datetime.utcnow()
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


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
            # ← YENİ: haftalık istatistik tablosu
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weekly_stats (
                    user_id INTEGER,
                    week_start TEXT,
                    first_name TEXT,
                    wins INTEGER DEFAULT 0,
                    games INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, week_start)
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

    def _ensure_weekly_row(self, conn, user_id, first_name):
        week = _week_start_str()
        conn.execute(
            "INSERT OR IGNORE INTO weekly_stats (user_id, week_start, first_name) VALUES (?, ?, ?)",
            (user_id, week, first_name)
        )
        return week

    def add_win(self, user_id, first_name=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET wins = wins + 1 WHERE user_id = ?",
                (user_id,)
            )
            week = self._ensure_weekly_row(conn, user_id, first_name or "?")
            conn.execute(
                "UPDATE weekly_stats SET wins = wins + 1, first_name = COALESCE(?, first_name) "
                "WHERE user_id = ? AND week_start = ?",
                (first_name, user_id, week)
            )
            conn.commit()

    def add_game(self, user_id, first_name=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET games = games + 1 WHERE user_id = ?",
                (user_id,)
            )
            week = self._ensure_weekly_row(conn, user_id, first_name or "?")
            conn.execute(
                "UPDATE weekly_stats SET games = games + 1, first_name = COALESCE(?, first_name) "
                "WHERE user_id = ? AND week_start = ?",
                (first_name, user_id, week)
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
            conn.execute(
                "UPDATE users SET xp = xp + ? WHERE user_id = ?",
                (amount, user_id)
            )
            conn.execute(
                "UPDATE users SET level = (xp / 100) + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    # ← YENİ: haftalık liderlik tablosu
    def get_weekly_leaderboard(self, limit=10):
        week = _week_start_str()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT user_id, first_name, wins, games FROM weekly_stats "
                "WHERE week_start = ? ORDER BY wins DESC, games DESC LIMIT ?",
                (week, limit)
            )
            return cur.fetchall()


# Global instance
db = Database()
