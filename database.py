import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "uno_bot.db")


def _week_start_str(dt=None):
    """
    Haftanın başlangıcını Pazartesi 00:00 olarak hesaplar.
    UTC kullanılır.
    """
    dt = dt or datetime.utcnow()
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


class Database:

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ---------------------------------------------------------
    # DATABASE OLUŞTUR
    # ---------------------------------------------------------

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
                    xp INTEGER DEFAULT 0,
                    theme TEXT DEFAULT 'meyus'
                )
            """)

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

            # Eski veritabanlarında theme sütunu yoksa ekle.
            columns = [
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(users)"
                ).fetchall()
            ]

            if "theme" not in columns:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'meyus'"
                )

            conn.commit()

    # ---------------------------------------------------------
    # KULLANICI
    # ---------------------------------------------------------

    def get_user(self, user_id):

        with sqlite3.connect(self.db_path) as conn:

            cur = conn.execute(
                """
                SELECT
                    user_id,
                    username,
                    first_name,
                    coins,
                    wins,
                    games,
                    level,
                    xp,
                    theme
                FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            )

            return cur.fetchone()

    def add_user(
        self,
        user_id,
        username=None,
        first_name=None
    ):

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    username,
                    first_name,
                    theme
                )
                VALUES (?, ?, ?, 'meyus')

                ON CONFLICT(user_id)
                DO UPDATE SET
                    username = COALESCE(
                        excluded.username,
                        users.username
                    ),
                    first_name = COALESCE(
                        excluded.first_name,
                        users.first_name
                    )
                """,
                (
                    user_id,
                    username,
                    first_name
                )
            )

            conn.commit()

    def get_or_create_user(
        self,
        user_id,
        username=None,
        first_name=None
    ):

        self.add_user(
            user_id,
            username,
            first_name
        )

        return self.get_user(user_id)

    # ---------------------------------------------------------
    # TEMA
    # ---------------------------------------------------------

    def get_theme(self, user_id):
        """
        Kullanıcının seçtiği temayı döndürür.

        Kullanıcı yoksa varsayılan:
        meyus
        """

        user = self.get_user(user_id)

        if not user:
            self.add_user(user_id)
            return "meyus"

        # users:
        # 0 user_id
        # 1 username
        # 2 first_name
        # 3 coins
        # 4 wins
        # 5 games
        # 6 level
        # 7 xp
        # 8 theme

        return user[8] or "meyus"

    def set_theme(self, user_id, theme):
        """
        Kullanıcının temasını kaydeder.
        """

        if not self.get_user(user_id):
            self.add_user(user_id)

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                UPDATE users
                SET theme = ?
                WHERE user_id = ?
                """,
                (
                    theme,
                    user_id
                )
            )

            conn.commit()

        return True

    # ---------------------------------------------------------
    # HAFTALIK KAYIT
    # ---------------------------------------------------------

    def _ensure_weekly_row(
        self,
        conn,
        user_id,
        first_name=None
    ):

        week = _week_start_str()

        conn.execute(
            """
            INSERT INTO weekly_stats (
                user_id,
                week_start,
                first_name,
                wins,
                games
            )
            VALUES (?, ?, ?, 0, 0)

            ON CONFLICT(user_id, week_start)
            DO UPDATE SET
                first_name =
                    COALESCE(
                        excluded.first_name,
                        weekly_stats.first_name
                    )
            """,
            (
                user_id,
                week,
                first_name
            )
        )

        return week

    # ---------------------------------------------------------
    # GALİBİYET
    # ---------------------------------------------------------

    def add_win(
        self,
        user_id,
        first_name=None
    ):

        if not self.get_user(user_id):

            self.add_user(
                user_id,
                None,
                first_name
            )

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                UPDATE users
                SET wins = wins + 1
                WHERE user_id = ?
                """,
                (user_id,)
            )

            week = self._ensure_weekly_row(
                conn,
                user_id,
                first_name
            )

            conn.execute(
                """
                UPDATE weekly_stats

                SET
                    wins = wins + 1,
                    first_name =
                        COALESCE(?, first_name)

                WHERE
                    user_id = ?
                    AND week_start = ?
                """,
                (
                    first_name,
                    user_id,
                    week
                )
            )

            conn.commit()

    # ---------------------------------------------------------
    # OYNANAN OYUN
    # ---------------------------------------------------------

    def add_game(
        self,
        user_id,
        first_name=None
    ):

        if not self.get_user(user_id):

            self.add_user(
                user_id,
                None,
                first_name
            )

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                UPDATE users
                SET games = games + 1
                WHERE user_id = ?
                """,
                (user_id,)
            )

            week = self._ensure_weekly_row(
                conn,
                user_id,
                first_name
            )

            conn.execute(
                """
                UPDATE weekly_stats

                SET
                    games = games + 1,
                    first_name =
                        COALESCE(?, first_name)

                WHERE
                    user_id = ?
                    AND week_start = ?
                """,
                (
                    first_name,
                    user_id,
                    week
                )
            )

            conn.commit()

    # ---------------------------------------------------------
    # COIN
    # ---------------------------------------------------------

    def add_coin(
        self,
        user_id,
        amount
    ):

        if not self.get_user(user_id):

            self.add_user(
                user_id,
                None,
                None
            )

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                UPDATE users
                SET coins = coins + ?
                WHERE user_id = ?
                """,
                (
                    amount,
                    user_id
                )
            )

            conn.commit()

    # ---------------------------------------------------------
    # XP / LEVEL
    # ---------------------------------------------------------

    def add_xp(
        self,
        user_id,
        amount
    ):

        if not self.get_user(user_id):

            self.add_user(
                user_id,
                None,
                None
            )

        with sqlite3.connect(self.db_path) as conn:

            conn.execute(
                """
                UPDATE users
                SET xp = xp + ?
                WHERE user_id = ?
                """,
                (
                    amount,
                    user_id
                )
            )

            conn.execute(
                """
                UPDATE users
                SET level = (xp / 100) + 1
                WHERE user_id = ?
                """,
                (user_id,)
            )

            conn.commit()

    # ---------------------------------------------------------
    # HAFTALIK SIRALAMA
    # ---------------------------------------------------------

    def get_weekly_leaderboard(
        self,
        limit=10
    ):

        week = _week_start_str()

        with sqlite3.connect(self.db_path) as conn:

            cur = conn.execute(
                """
                SELECT
                    user_id,
                    first_name,
                    wins,
                    games

                FROM weekly_stats

                WHERE week_start = ?

                ORDER BY
                    wins DESC,
                    games DESC

                LIMIT ?
                """,
                (
                    week,
                    limit
                )
            )

            return cur.fetchall()

    # ---------------------------------------------------------
    # KULLANICININ HAFTALIK SIRASI
    # ---------------------------------------------------------

    def get_weekly_user_rank(
        self,
        user_id
    ):

        week = _week_start_str()

        with sqlite3.connect(self.db_path) as conn:

            cur = conn.execute(
                """
                SELECT
                    user_id,
                    wins,
                    games

                FROM weekly_stats

                WHERE week_start = ?

                ORDER BY
                    wins DESC,
                    games DESC
                """,
                (week,)
            )

            rows = cur.fetchall()

        for index, row in enumerate(rows, start=1):

            if row[0] == user_id:

                return {
                    "rank": index,
                    "wins": row[1],
                    "games": row[2]
                }

        return None

    # ---------------------------------------------------------
    # HAFTANIN BAŞLANGIÇ TARİHİ
    # ---------------------------------------------------------

    def get_current_week_start(self):

        return _week_start_str()


# ---------------------------------------------------------
# GLOBAL DATABASE
# ---------------------------------------------------------

db = Database()
