import sqlite3
from pathlib import Path

DB_FOLDER = Path("data")
DB_FOLDER.mkdir(exist_ok=True)

DB_PATH = DB_FOLDER / "uno.db"


class Database:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            coins INTEGER DEFAULT 100,
            wins INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0
        )
        """)

        self.conn.commit()

    # ---------------- USER ----------------

    def add_user(self, user_id, first_name, username):

        self.cursor.execute("""
        INSERT OR IGNORE INTO users
        (user_id, first_name, username)
        VALUES (?, ?, ?)
        """, (user_id, first_name, username))

        self.conn.commit()

    def get_user(self, user_id):

        self.cursor.execute("""
        SELECT * FROM users
        WHERE user_id=?
        """, (user_id,))

        return self.cursor.fetchone()

    # ---------------- COIN ----------------

    def add_coin(self, user_id, amount):

        self.cursor.execute("""
        UPDATE users
        SET coins = coins + ?
        WHERE user_id=?
        """, (amount, user_id))

        self.conn.commit()

    def remove_coin(self, user_id, amount):

        self.cursor.execute("""
        UPDATE users
        SET coins = coins - ?
        WHERE user_id=?
        """, (amount, user_id))

        self.conn.commit()

    # ---------------- XP ----------------

    def add_xp(self, user_id, amount):

        self.cursor.execute("""
        UPDATE users
        SET xp = xp + ?
        WHERE user_id=?
        """, (amount, user_id))

        self.conn.commit()

    # ---------------- GAME ----------------

    def add_game(self, user_id):

        self.cursor.execute("""
        UPDATE users
        SET games = games + 1
        WHERE user_id=?
        """, (user_id,))

        self.conn.commit()

    def add_win(self, user_id):

        self.cursor.execute("""
        UPDATE users
        SET wins = wins + 1
        WHERE user_id=?
        """, (user_id,))

        self.conn.commit()

    # ---------------- LEADERBOARD ----------------

    def leaderboard(self):

        self.cursor.execute("""
        SELECT first_name,wins
        FROM users
        ORDER BY wins DESC
        LIMIT 10
        """)

        return self.cursor.fetchall()


db = Database()
