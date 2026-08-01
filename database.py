'''import sqlite3
import json
from config import DATABASE_NAME


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                state TEXT
            )
        """)
        self.conn.commit()

    def save_state(self, game_id, state):
        cursor = self.conn.cursor()
        cursor.execute(
            "REPLACE INTO games (game_id, state) VALUES (?, ?)",
            (str(game_id), json.dumps(state))
        )
        self.conn.commit()

    def load_state(self, game_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT state FROM games WHERE game_id = ?", (str(game_id),))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def delete_state(self, game_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM games WHERE game_id = ?", (str(game_id),))
        self.conn.commit()
'''

with open('/mnt/agents/output/database.py', 'w', encoding='utf-8') as f:
    f.write(database_content)
print("✅ database.py")
