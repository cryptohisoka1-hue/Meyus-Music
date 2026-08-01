import sqlite3
import aiosqlite
from config import DATABASE_NAME

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                deck TEXT,
                discard_pile TEXT,
                current_turn INTEGER,
                direction INTEGER,
                players TEXT,
                active BOOLEAN DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                hand TEXT,
                game_id TEXT
            )
        """)
        await db.commit()

async def save_game(game_id, data):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("REPLACE INTO games (game_id, deck, discard_pile, current_turn, direction, players, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (game_id, data['deck'], data['discard'], data['turn'], data['direction'], str(data['players']), 1))
        await db.commit()

async def get_game(game_id):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT * FROM games WHERE game_id = ?", (game_id,))
        row = await cursor.fetchone()
        return row

async def add_player(user_id, game_id, hand):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO players (user_id, hand, game_id) VALUES (?, ?, ?)", (user_id, str(hand), game_id))
        await db.commit()

async def get_player_hand(user_id):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("SELECT hand FROM players WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return eval(row) if row else 
        
