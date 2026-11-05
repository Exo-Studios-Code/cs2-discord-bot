"""
Database modul - SQLite přes aiosqlite
Ukládá uživatelské profily, match historii a statistiky.
"""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

log = logging.getLogger("CS2Bot.DB")

DB_PATH = "cs2bot.db"

class Database:
    def __init__(self):
        self.db: Optional[aiosqlite.Connection] = None

    async def init(self):
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row
        await self._create_tables()
        log.info("✅ Databáze inicializována")

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                discord_id TEXT PRIMARY KEY,
                steam_id TEXT NOT NULL,
                match_auth_token TEXT,
                last_sharecode TEXT,
                registered_at TEXT DEFAULT (datetime('now')),
                dm_notifications INTEGER DEFAULT 1,
                last_check TEXT
            );

            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                sharecode TEXT UNIQUE,
                match_id TEXT,
                map_name TEXT,
                result TEXT,
                score_ct INTEGER,
                score_t INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                hs_kills INTEGER,
                mvps INTEGER,
                score INTEGER,
                adr REAL,
                kd_ratio REAL,
                match_date TEXT DEFAULT (datetime('now')),
                raw_data TEXT,
                ai_analysis TEXT,
                FOREIGN KEY (discord_id) REFERENCES users(discord_id)
            );

            CREATE TABLE IF NOT EXISTS player_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                snapshot_date TEXT DEFAULT (datetime('now')),
                total_kills INTEGER,
                total_deaths INTEGER,
                total_matches INTEGER,
                total_wins INTEGER,
                total_mvps INTEGER,
                total_hs INTEGER,
                kd_ratio REAL,
                win_rate REAL,
                hs_rate REAL,
                raw_stats TEXT,
                FOREIGN KEY (discord_id) REFERENCES users(discord_id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                type TEXT,
                message TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (discord_id) REFERENCES users(discord_id)
            );
        """)
        await self.db.commit()

    # ─── USERS ───────────────────────────────────────────────────

    async def register_user(self, discord_id: str, steam_id: str,
                             match_auth_token: str, sharecode: str = None) -> bool:
        try:
            await self.db.execute("""
                INSERT INTO users (discord_id, steam_id, match_auth_token, last_sharecode)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    steam_id = excluded.steam_id,
                    match_auth_token = excluded.match_auth_token,
                    last_sharecode = COALESCE(excluded.last_sharecode, last_sharecode)
            """, (discord_id, steam_id, match_auth_token, sharecode))
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"Chyba při registraci uživatele: {e}")
            return False

    async def get_user(self, discord_id: str) -> Optional[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            return await cursor.fetchone()

    async def get_all_users(self) -> List[aiosqlite.Row]:
        async with self.db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()

    async def update_last_sharecode(self, discord_id: str, sharecode: str):
        await self.db.execute(
            "UPDATE users SET last_sharecode = ?, last_check = datetime('now') WHERE discord_id = ?",
            (sharecode, discord_id)
        )
        await self.db.commit()

    async def toggle_notifications(self, discord_id: str) -> bool:
        async with self.db.execute(
            "SELECT dm_notifications FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            new_val = 0 if row["dm_notifications"] else 1
        await self.db.execute(
            "UPDATE users SET dm_notifications = ? WHERE discord_id = ?",
            (new_val, discord_id)
        )
        await self.db.commit()
        return bool(new_val)

    # ─── MATCHES ─────────────────────────────────────────────────

    async def save_match(self, discord_id: str, data: Dict[str, Any]) -> bool:
        try:
            await self.db.execute("""
                INSERT OR IGNORE INTO match_history
                (discord_id, sharecode, match_id, map_name, result,
                 score_ct, score_t, kills, deaths, assists,
                 hs_kills, mvps, score, adr, kd_ratio, raw_data)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                discord_id,
                data.get("sharecode"),
                data.get("match_id"),
                data.get("map_name", "Neznámá"),
                data.get("result", "?"),
                data.get("score_ct", 0),
                data.get("score_t", 0),
                data.get("kills", 0),
                data.get("deaths", 0),
                data.get("assists", 0),
                data.get("hs_kills", 0),
                data.get("mvps", 0),
                data.get("score", 0),
                data.get("adr", 0.0),
                data.get("kd_ratio", 0.0),
                json.dumps(data.get("raw_data", {}))
            ))
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"Chyba při ukládání zápasu: {e}")
            return False

    async def update_match_analysis(self, sharecode: str, analysis: str):
        await self.db.execute(
            "UPDATE match_history SET ai_analysis = ? WHERE sharecode = ?",
            (analysis, sharecode)
        )
        await self.db.commit()

    async def get_match_history(self, discord_id: str, limit: int = 20) -> List[aiosqlite.Row]:
        async with self.db.execute("""
            SELECT * FROM match_history
            WHERE discord_id = ?
            ORDER BY match_date DESC
            LIMIT ?
        """, (discord_id, limit)) as cursor:
            return await cursor.fetchall()

    async def get_match_by_sharecode(self, sharecode: str) -> Optional[aiosqlite.Row]:
        async with self.db.execute(
            "SELECT * FROM match_history WHERE sharecode = ?", (sharecode,)
        ) as cursor:
            return await cursor.fetchone()

    # ─── SNAPSHOTS ───────────────────────────────────────────────

    async def save_snapshot(self, discord_id: str, stats: Dict[str, Any]):
        await self.db.execute("""
            INSERT INTO player_snapshots
            (discord_id, total_kills, total_deaths, total_matches, total_wins,
             total_mvps, total_hs, kd_ratio, win_rate, hs_rate, raw_stats)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            discord_id,
            stats.get("total_kills", 0),
            stats.get("total_deaths", 0),
            stats.get("total_matches", 0),
            stats.get("total_wins", 0),
            stats.get("total_mvps", 0),
            stats.get("total_hs", 0),
            stats.get("kd_ratio", 0.0),
            stats.get("win_rate", 0.0),
            stats.get("hs_rate", 0.0),
            json.dumps(stats)
        ))
        await self.db.commit()

    async def get_snapshots(self, discord_id: str, limit: int = 30) -> List[aiosqlite.Row]:
        async with self.db.execute("""
            SELECT * FROM player_snapshots
            WHERE discord_id = ?
            ORDER BY snapshot_date DESC
            LIMIT ?
        """, (discord_id, limit)) as cursor:
            return await cursor.fetchall()

    async def close(self):
        if self.db:
            await self.db.close()
