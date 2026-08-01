import sqlite3
from config import DB_PATH

class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_states (
                chat_id INTEGER PRIMARY KEY,
                state ტექಸ್ಟ್
            )
        """)
        self.conn.commit()

    def save_state(self, chat_id, state):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO game_states (chat_id, state)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET state=excluded.state
        """, (chat_id, state))
        self.conn.commit()

    def load_state(self, chat_id):
        cur = self.conn.cursor()
        cur.execute("SELECT state FROM game_states WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        return row["state"] if row else None

    def delete_state(self, chat_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM game_states WHERE chat_id = ?", (chat_id,))
        self.conn.commit()
