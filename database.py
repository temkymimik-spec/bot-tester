from datetime import datetime

import aiosqlite

import config

COLS = ["telegram_id", "username", "full_name", "po_id", "status", "created_at", "activated_at"]


class Database:
    def __init__(self, path):
        self.path = path
        self._conn = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id   INTEGER PRIMARY KEY,
                username      TEXT,
                full_name     TEXT,
                po_id         TEXT,
                status        TEXT DEFAULT 'new',
                created_at    TEXT,
                activated_at  TEXT
            );
            CREATE TABLE IF NOT EXISTS admins (
                telegram_id INTEGER PRIMARY KEY,
                added_by    INTEGER,
                created_at  TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        await self._commit()

        for k, v in {
            "referral_link_ru": "https://pocketoption.com/",
            "referral_link_int": "https://pocketoption.com/",
            "promo_code": "BONUS50",
            "admin_contact": "",
            "min_deposit": "10",
            "pair": "BTC/USD",
            "interval": "60",
            "autosignals": "0",
            "ai_provider": "strategy",
            "openai_base": "https://api.groq.com/openai/v1",
            "openai_key": "",
            "openai_model": "llama-3.3-70b-versatile",
            "neuro_key": "",
            "last_signal": "{}",
        }.items():
            cur = await self._conn.execute("SELECT 1 FROM settings WHERE key=?", (k,))
            if await cur.fetchone() is None:
                await self._conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?)", (k, v)
                )
        await self._commit()

        old = await self.get_setting("referral_link")
        if old and old != "https://pocketoption.com/":
            for new_key in ("referral_link_ru", "referral_link_int"):
                cur = await self._conn.execute(
                    "SELECT value FROM settings WHERE key=?", (new_key,)
                )
                row = await cur.fetchone()
                if row and row[0] == "https://pocketoption.com/":
                    await self._conn.execute(
                        "UPDATE settings SET value=? WHERE key=?",
                        (old, new_key),
                    )
            await self._commit()

        if config.OWNER_ID:
            await self.add_admin(config.OWNER_ID, 0)
        for aid in config.ADMIN_IDS:
            await self.add_admin(aid, config.OWNER_ID)

    async def _commit(self):
        await self._conn.commit()

    # ---------------- settings ----------------

    async def get_setting(self, key, default=None):
        cur = await self._conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default

    async def get_int(self, key, default=0):
        try:
            return int(await self.get_setting(key))
        except (TypeError, ValueError):
            return default

    async def set_setting(self, key, value):
        await self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        await self._commit()

    # ---------------- users ----------------

    async def upsert_user(self, tg_id, username, full_name):
        now = self.now()
        cur = await self._conn.execute("SELECT 1 FROM users WHERE telegram_id=?", (tg_id,))
        if await cur.fetchone() is None:
            await self._conn.execute(
                "INSERT INTO users(telegram_id, username, full_name, status, created_at) "
                "VALUES(?, ?, ?, 'new', ?)",
                (tg_id, username, full_name, now),
            )
        else:
            await self._conn.execute(
                "UPDATE users SET username=?, full_name=? WHERE telegram_id=?",
                (username, full_name, tg_id),
            )
        await self._commit()

    async def get_user(self, tg_id):
        cur = await self._conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,))
        row = await cur.fetchone()
        return dict(zip(COLS, row)) if row else None

    async def set_user(self, tg_id, **fields):
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        await self._conn.execute(
            f"UPDATE users SET {sets} WHERE telegram_id=?", (*fields.values(), tg_id)
        )
        await self._commit()

    async def users_by_status(self, status, limit=20):
        cur = await self._conn.execute(
            "SELECT * FROM users WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        )
        return [dict(zip(COLS, row)) for row in await cur.fetchall()]

    async def active_tg_ids(self):
        cur = await self._conn.execute("SELECT telegram_id FROM users WHERE status='active'")
        return [row[0] for row in await cur.fetchall()]

    async def counts(self):
        out = {}
        for st in ("new", "pending", "active", "banned"):
            cur = await self._conn.execute(
                "SELECT COUNT(*) FROM users WHERE status=?", (st,)
            )
            row = await cur.fetchone()
            out[st] = row[0]
        return out

    async def recent_users(self, limit=10):
        cur = await self._conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(zip(COLS, row)) for row in await cur.fetchall()]

    # ---------------- admins ----------------

    def is_owner(self, tg_id):
        return tg_id == config.OWNER_ID

    async def is_admin(self, tg_id):
        if self.is_owner(tg_id):
            return True
        cur = await self._conn.execute("SELECT 1 FROM admins WHERE telegram_id=?", (tg_id,))
        return await cur.fetchone() is not None

    async def add_admin(self, tg_id, added_by):
        cur = await self._conn.execute("SELECT 1 FROM admins WHERE telegram_id=?", (tg_id,))
        if await cur.fetchone() is None and tg_id:
            await self._conn.execute(
                "INSERT INTO admins(telegram_id, added_by, created_at) VALUES(?, ?, ?)",
                (tg_id, added_by, self.now()),
            )
            await self._commit()

    async def remove_admin(self, tg_id):
        await self._conn.execute("DELETE FROM admins WHERE telegram_id=?", (tg_id,))
        await self._commit()

    async def admin_ids(self):
        cur = await self._conn.execute("SELECT telegram_id FROM admins")
        return [row[0] for row in await cur.fetchall()]

    @staticmethod
    def now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


db = Database(config.DB_FILE)