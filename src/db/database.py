"""SQLite database management for phone-logger."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        logger.info("Database connected: %s", self.db_path)

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database closed")

    @property
    def db(self) -> aiosqlite.Connection:
        """Get active database connection."""
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    async def _init_schema(self) -> None:
        """Initialize database schema from SQL file."""
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()
        await self.db.executescript(schema)
        await self.db.commit()
        logger.info("Database schema initialized")

    # --- Contact Operations ---

    async def get_contacts(self) -> list[dict]:
        """Get all contacts."""
        cursor = await self.db.execute(
            "SELECT * FROM contacts ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [self._row_to_contact(row) for row in rows]

    async def get_contact(self, number: str) -> Optional[dict]:
        """Get a single contact by number."""
        cursor = await self.db.execute(
            "SELECT * FROM contacts WHERE number = ?", (number,)
        )
        row = await cursor.fetchone()
        return self._row_to_contact(row) if row else None

    async def create_contact(self, number: str, name: str, tags: list[str] | None = None,
                             notes: str | None = None, spam_score: int | None = None,
                             source: str = "sqlite") -> dict:
        """Create a new contact."""
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])
        await self.db.execute(
            """INSERT INTO contacts (number, name, tags, notes, spam_score, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (number, name, tags_json, notes, spam_score, source, now, now),
        )
        await self.db.commit()
        return await self.get_contact(number)

    async def update_contact(self, number: str, **kwargs) -> Optional[dict]:
        """Update an existing contact."""
        contact = await self.get_contact(number)
        if not contact:
            return None

        updates = []
        params = []
        for key, value in kwargs.items():
            if value is not None and key in ("name", "tags", "notes", "spam_score"):
                if key == "tags":
                    value = json.dumps(value)
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return contact

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(number)

        await self.db.execute(
            f"UPDATE contacts SET {', '.join(updates)} WHERE number = ?",
            params,
        )
        await self.db.commit()
        return await self.get_contact(number)

    async def delete_contact(self, number: str) -> bool:
        """Delete a contact."""
        cursor = await self.db.execute(
            "DELETE FROM contacts WHERE number = ?", (number,)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def update_last_seen(self, number: str) -> None:
        """Update the last_seen timestamp for a contact."""
        await self.db.execute(
            "UPDATE contacts SET last_seen = ? WHERE number = ?",
            (datetime.now().isoformat(), number),
        )
        await self.db.commit()

    # --- Cache Operations ---

    async def get_cached(self, number: str, adapter: str) -> Optional[dict]:
        """Get a cached resolve result if not expired."""
        cursor = await self.db.execute(
            "SELECT * FROM cache WHERE number = ? AND adapter = ?",
            (number, adapter),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        cached_at = datetime.fromisoformat(dict(row)["cached_at"])
        ttl_days = dict(row)["ttl_days"]
        if datetime.now() > cached_at + timedelta(days=ttl_days):
            # Expired - remove from cache
            await self.delete_cache_entry(number, adapter)
            return None

        return json.loads(dict(row)["result_json"])

    async def set_cached(self, number: str, adapter: str, result: dict,
                         ttl_days: int = 7) -> None:
        """Store a resolve result in cache."""
        await self.db.execute(
            """INSERT OR REPLACE INTO cache (number, adapter, result_json, cached_at, ttl_days)
               VALUES (?, ?, ?, ?, ?)""",
            (number, adapter, json.dumps(result), datetime.now().isoformat(), ttl_days),
        )
        await self.db.commit()

    async def get_all_cache_entries(self) -> list[dict]:
        """Get all cache entries with expiration status."""
        cursor = await self.db.execute(
            "SELECT * FROM cache ORDER BY cached_at DESC"
        )
        rows = await cursor.fetchall()
        entries = []
        for row in rows:
            row_dict = dict(row)
            cached_at = datetime.fromisoformat(row_dict["cached_at"])
            expired = datetime.now() > cached_at + timedelta(days=row_dict["ttl_days"])
            result = json.loads(row_dict["result_json"])
            entries.append({
                "number": row_dict["number"],
                "adapter": row_dict["adapter"],
                "result_name": result.get("name"),
                "spam_score": result.get("spam_score"),
                "cached_at": row_dict["cached_at"],
                "ttl_days": row_dict["ttl_days"],
                "expired": expired,
            })
        return entries

    async def delete_cache_entry(self, number: str, adapter: str | None = None) -> bool:
        """Delete cache entry for a number, optionally filtered by adapter."""
        if adapter:
            cursor = await self.db.execute(
                "DELETE FROM cache WHERE number = ? AND adapter = ?",
                (number, adapter),
            )
        else:
            cursor = await self.db.execute(
                "DELETE FROM cache WHERE number = ?", (number,)
            )
        await self.db.commit()
        return cursor.rowcount > 0

    async def cleanup_expired_cache(self) -> int:
        """Remove all expired cache entries. Returns number of removed entries."""
        cursor = await self.db.execute(
            """DELETE FROM cache
               WHERE datetime(cached_at, '+' || ttl_days || ' days') < datetime('now')"""
        )
        await self.db.commit()
        return cursor.rowcount

    # --- Call Log Operations ---

    async def log_call(self, number: str, direction: str, event_type: str,
                       resolved_name: str | None = None, source: str | None = None) -> int:
        """Log a call event."""
        cursor = await self.db.execute(
            """INSERT INTO call_log (number, direction, event_type, resolved_name, source, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (number, direction, event_type, resolved_name, source, datetime.now().isoformat()),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_call_log(self, page: int = 1, page_size: int = 50,
                           number_filter: str | None = None) -> tuple[list[dict], int]:
        """Get paginated call log."""
        where = ""
        params: list = []
        if number_filter:
            where = "WHERE number LIKE ?"
            params.append(f"%{number_filter}%")

        # Get total count
        count_cursor = await self.db.execute(
            f"SELECT COUNT(*) FROM call_log {where}", params
        )
        total = (await count_cursor.fetchone())[0]

        # Get page
        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor = await self.db.execute(
            f"SELECT * FROM call_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total

    # --- Helpers ---

    @staticmethod
    def _row_to_contact(row) -> dict:
        """Convert a database row to a contact dictionary."""
        data = dict(row)
        data["tags"] = json.loads(data.get("tags") or "[]")
        return data
