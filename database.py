import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/uno.db"


def get_conn():
    import os
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            wins INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            cards_played INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            won INTEGER,
            ts TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_user(user_id, username, first_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (?,?,?)",
            (user_id, username, first_name),
        )
    else:
        cur.execute(
            "UPDATE users SET username=?, first_name=? WHERE user_id=?",
            (username, first_name, user_id),
        )
    conn.commit()
    conn.close()


def record_card_played(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET cards_played = cards_played + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def record_game_result(chat_id, player_ids, winner_id):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    for uid in player_ids:
        won = 1 if uid == winner_id else 0
        cur.execute(
            "INSERT INTO results (user_id, chat_id, won, ts) VALUES (?,?,?,?)",
            (uid, chat_id, won, now),
        )
        cur.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id=?", (uid,))
        if won:
            cur.execute("UPDATE users SET wins = wins + 1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()


def get_profile(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_weekly_ranking(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    cur.execute("""
        SELECT u.user_id, u.first_name, u.username, COUNT(*) as weekly_wins
        FROM results r
        JOIN users u ON u.user_id = r.user_id
        WHERE r.won = 1 AND r.ts >= ?
        GROUP BY r.user_id
        ORDER BY weekly_wins DESC
        LIMIT ?
    """, (week_ago, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
  
