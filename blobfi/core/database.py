"""
core/database.py

SQLite persistence for BlobFi snapshots and IP rate limiting.
Snapshots survive server restarts and are shared across all visitors.
"""

import aiosqlite
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from core.logger import get_logger

logger = get_logger(__name__)
DB_PATH = "blobfi.db"


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id          TEXT PRIMARY KEY,
                blob_id     TEXT,
                timestamp   TEXT NOT NULL,
                top_protocol TEXT,
                top_apy     REAL,
                avg_apy     REAL,
                chain_tvl_usd REAL,
                protocols_tracked INTEGER,
                ai_report   TEXT,
                walrus_stored INTEGER DEFAULT 0,
                raw_json    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                ip          TEXT NOT NULL,
                triggered_at TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_rate_ip ON rate_limits(ip, triggered_at)")
        await db.commit()
    logger.info("Database initialized")


async def save_snapshot(summary: Dict[str, Any]):
    """Persist a snapshot summary to SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO snapshots
            (id, blob_id, timestamp, top_protocol, top_apy, avg_apy,
             chain_tvl_usd, protocols_tracked, ai_report, walrus_stored, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.get("snapshot_id"),
            summary.get("blob_id"),
            summary.get("timestamp"),
            summary.get("top_protocol"),
            summary.get("top_apy"),
            summary.get("avg_apy"),
            summary.get("chain_tvl_usd"),
            summary.get("protocols_tracked"),
            summary.get("ai_report"),
            1 if summary.get("walrus_stored") else 0,
            json.dumps(summary),
        ))
        await db.commit()


async def load_snapshots(limit: int = 50) -> List[Dict[str, Any]]:
    """Load snapshot history from SQLite, newest first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT raw_json FROM snapshots ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for row in rows:
        try:
            result.append(json.loads(row["raw_json"]))
        except Exception:
            pass
    return result


async def check_rate_limit(ip: str, max_per_hour: int = 1) -> Dict[str, Any]:
    """
    Check if an IP can trigger a manual snapshot.
    Returns {"allowed": bool, "wait_minutes": int}
    """
    window_start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT triggered_at FROM rate_limits WHERE ip = ? AND triggered_at > ? ORDER BY triggered_at DESC",
            (ip, window_start)
        ) as cursor:
            rows = await cursor.fetchall()

    count = len(rows)
    if count < max_per_hour:
        return {"allowed": True, "wait_minutes": 0, "used": count, "limit": max_per_hour}

    # Calculate wait time from oldest trigger in window
    oldest = rows[-1][0]
    oldest_dt = datetime.fromisoformat(oldest)
    if oldest_dt.tzinfo is None:
        oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
    available_at = oldest_dt + timedelta(hours=1)
    wait = max(0, int((available_at - datetime.now(timezone.utc)).total_seconds() / 60))
    return {"allowed": False, "wait_minutes": wait, "used": count, "limit": max_per_hour}


async def record_rate_limit(ip: str):
    """Record a manual snapshot trigger for an IP."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO rate_limits (ip, triggered_at) VALUES (?, ?)",
            (ip, datetime.now(timezone.utc).isoformat())
        )
        # Clean up old entries (older than 2 hours)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        await db.execute("DELETE FROM rate_limits WHERE triggered_at < ?", (cutoff,))
        await db.commit()
