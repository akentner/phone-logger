"""SQLite database management for phone-logger."""

import json
import logging
from datetime import UTC, datetime, timedelta
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
        await self._run_migrations()
        logger.info("Database schema initialized")

    async def _run_migrations(self) -> None:
        """Run any pending migrations."""
        # Check if number_type column exists
        cursor = await self.db.execute("PRAGMA table_info(contacts)")
        columns = [row[1] for row in await cursor.fetchall()]

        if "number_type" not in columns:
            logger.info("Running migration: add_number_type column")
            await self.db.execute(
                "ALTER TABLE contacts ADD COLUMN number_type TEXT DEFAULT 'private'"
            )
            await self.db.commit()

        # Ensure raw_events table and indexes exist (for existing DBs)
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS raw_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                raw_input TEXT,
                raw_event_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_raw_events_timestamp ON raw_events(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_raw_events_source ON raw_events(source);
        """)
        await self.db.commit()

        # Drop resolved_name from calls and call_log (now derived via JOIN on contacts)
        cursor = await self.db.execute("PRAGMA table_info(calls)")
        calls_columns = [row[1] for row in await cursor.fetchall()]
        if "resolved_name" in calls_columns:
            logger.info("Running migration: drop resolved_name from calls")
            await self.db.execute("ALTER TABLE calls DROP COLUMN resolved_name")
            await self.db.commit()

        cursor = await self.db.execute("PRAGMA table_info(call_log)")
        call_log_columns = [row[1] for row in await cursor.fetchall()]
        if "resolved_name" in call_log_columns:
            logger.info("Running migration: drop resolved_name from call_log")
            await self.db.execute("ALTER TABLE call_log DROP COLUMN resolved_name")
            await self.db.commit()

        # Add caller_device_id / called_device_id to calls (replace device/device_type)
        cursor = await self.db.execute("PRAGMA table_info(calls)")
        calls_columns = [row[1] for row in await cursor.fetchall()]
        if "caller_device_id" not in calls_columns:
            logger.info(
                "Running migration: add caller_device_id / called_device_id to calls"
            )
            await self.db.execute("ALTER TABLE calls ADD COLUMN caller_device_id TEXT")
            await self.db.execute("ALTER TABLE calls ADD COLUMN called_device_id TEXT")
            await self.db.commit()
        if "device" in calls_columns:
            logger.info("Running migration: drop device / device_type from calls")
            await self.db.execute("ALTER TABLE calls DROP COLUMN device")
            await self.db.execute("ALTER TABLE calls DROP COLUMN device_type")
            await self.db.commit()

    # --- Contact Operations ---

    async def get_contacts(self) -> list[dict]:
        """Get all contacts."""
        cursor = await self.db.execute("SELECT * FROM contacts ORDER BY name")
        rows = await cursor.fetchall()
        return [self._row_to_contact(row) for row in rows]

    async def get_contact(self, number: str) -> Optional[dict]:
        """Get a single contact by number."""
        cursor = await self.db.execute(
            "SELECT * FROM contacts WHERE number = ?", (number,)
        )
        row = await cursor.fetchone()
        return self._row_to_contact(row) if row else None

    async def create_contact(
        self,
        number: str,
        name: str,
        number_type: str = "private",
        tags: list[str] | None = None,
        notes: str | None = None,
        spam_score: int | None = None,
        source: str = "sqlite",
    ) -> dict:
        """Create a new contact."""
        now = datetime.now(UTC).isoformat()
        tags_json = json.dumps(tags or [])
        await self.db.execute(
            """INSERT INTO contacts (number, name, number_type, tags, notes, spam_score, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (number, name, number_type, tags_json, notes, spam_score, source, now, now),
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
            if value is not None and key in (
                "name",
                "number_type",
                "tags",
                "notes",
                "spam_score",
            ):
                if key == "tags":
                    value = json.dumps(value)
                updates.append(key + " = ?")
                params.append(value)

        if not updates:
            return contact

        updates.append("updated_at = ?")
        params.append(datetime.now(UTC).isoformat())
        params.append(number)

        await self.db.execute(
            "UPDATE contacts SET " + ", ".join(updates) + " WHERE number = ?",
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
            (datetime.now(UTC).isoformat(), number),
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

        cached_at = datetime.fromisoformat(dict(row)["cached_at"]).replace(tzinfo=UTC)
        ttl_days = dict(row)["ttl_days"]
        if datetime.now(UTC) > cached_at + timedelta(days=ttl_days):
            # Expired - remove from cache
            await self.delete_cache_entry(number, adapter)
            return None

        return json.loads(dict(row)["result_json"])

    async def set_cached(
        self, number: str, adapter: str, result: dict, ttl_days: int = 7
    ) -> None:
        """Store a resolve result in cache."""
        await self.db.execute(
            """INSERT OR REPLACE INTO cache (number, adapter, result_json, cached_at, ttl_days)
               VALUES (?, ?, ?, ?, ?)""",
            (
                number,
                adapter,
                json.dumps(result),
                datetime.now(UTC).isoformat(),
                ttl_days,
            ),
        )
        await self.db.commit()

    async def get_all_cache_entries(self) -> list[dict]:
        """Get all cache entries with expiration status."""
        cursor = await self.db.execute("SELECT * FROM cache ORDER BY cached_at DESC")
        rows = await cursor.fetchall()
        entries = []
        for row in rows:
            row_dict = dict(row)
            cached_at = datetime.fromisoformat(row_dict["cached_at"]).replace(
                tzinfo=UTC
            )
            expired = datetime.now(UTC) > cached_at + timedelta(
                days=row_dict["ttl_days"]
            )
            result = json.loads(row_dict["result_json"])
            entries.append(
                {
                    "number": row_dict["number"],
                    "adapter": row_dict["adapter"],
                    "result_name": result.get("name"),
                    "spam_score": result.get("spam_score"),
                    "cached_at": row_dict["cached_at"],
                    "ttl_days": row_dict["ttl_days"],
                    "expired": expired,
                }
            )
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

    # --- Raw Event Log Operations ---

    async def log_raw_event(
        self,
        source: str,
        raw_input: Optional[str],
        raw_event_json: str,
        timestamp: str,
    ) -> int:
        """Log a raw input event as received from an input adapter."""
        cursor = await self.db.execute(
            """INSERT INTO raw_events (source, raw_input, raw_event_json, timestamp)
               VALUES (?, ?, ?, ?)""",
            (source, raw_input, raw_event_json, timestamp),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_raw_events(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        source_filter: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Get paginated raw event log (cursor-based).

        Args:
            cursor: UUID of the last seen row (exclusive). None fetches from the start.
            limit: Maximum number of rows to return.
            source_filter: Optional source name filter.

        Returns:
            Tuple of (rows, next_cursor). next_cursor is None when no more rows exist.
        """
        where_clauses = []
        params: list = []
        if source_filter:
            where_clauses.append("source = ?")
            params.append(source_filter)
        if cursor:
            where_clauses.append("id < ?")
            params.append(cursor)

        where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(limit)
        db_cursor = await self.db.execute(
            "SELECT * FROM raw_events" + where + " ORDER BY id DESC LIMIT ?",
            params,
        )
        rows = await db_cursor.fetchall()
        result = [dict(row) for row in rows]
        next_cursor = result[-1]["id"] if len(result) == limit else None
        return result, next_cursor

    # --- Call Log Operations ---

    async def log_call(
        self,
        number: str,
        direction: str,
        event_type: str,
        source: str | None = None,
    ) -> int:
        """Log a call event."""
        cursor = await self.db.execute(
            """INSERT INTO call_log (number, direction, event_type, source, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (
                number,
                direction,
                event_type,
                source,
                datetime.now(UTC).isoformat(),
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_call_log(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        number_filter: str | None = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Get paginated call log (cursor-based).

        Args:
            cursor: UUID of the last seen row (exclusive). None fetches from the start.
            limit: Maximum number of rows to return.
            number_filter: Optional partial match on the number column.

        Returns:
            Tuple of (rows, next_cursor). next_cursor is None when no more rows exist.
        """
        where_clauses = []
        params: list = []
        if number_filter:
            where_clauses.append("number LIKE ?")
            params.append(f"%{number_filter}%")
        if cursor:
            where_clauses.append("id < ?")
            params.append(cursor)

        where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(limit)
        db_cursor = await self.db.execute(
            "SELECT * FROM call_log" + where + " ORDER BY id DESC LIMIT ?",
            params,
        )
        rows = await db_cursor.fetchall()
        result = [dict(row) for row in rows]
        next_cursor = result[-1]["id"] if len(result) == limit else None
        return result, next_cursor

    # --- Call Aggregation Operations ---

    async def upsert_call(
        self,
        call_id: str,
        connection_id: int,
        caller_number: str,
        called_number: str,
        direction: str,
        status: str,
        caller_device_id: Optional[str] = None,
        called_device_id: Optional[str] = None,
        msn: Optional[str] = None,
        trunk_id: Optional[str] = None,
        line_id: Optional[int] = None,
        is_internal: bool = False,
        started_at: Optional[str] = None,
        connected_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> dict:
        """Insert or update an aggregated call.

        Args:
            call_id: UUIDv7 call identifier
            connection_id: Fritz connection_id for call correlation
            caller_number: Caller's phone number
            called_number: Called party's phone number
            direction: 'inbound' or 'outbound'
            status: 'ringing', 'dialing', 'answered', 'missed', 'notReached'
            caller_device_id: Device ID of the calling party (AppConfig.pbx.devices[].id)
            called_device_id: Device ID of the called party (AppConfig.pbx.devices[].id)
            msn: MSN involved in the call (optional)
            trunk_id: Trunk identifier (optional)
            line_id: Line ID (optional)
            is_internal: Whether both parties are internal MSNs
            started_at: When the call started (RING/CALL event)
            connected_at: When the call connected (CONNECT event)
            finished_at: When the call finished (DISCONNECT event)
            duration_seconds: Call duration in seconds

        Returns:
            The call record as a dictionary
        """
        now = datetime.now(UTC).isoformat()
        cursor = await self.db.execute("SELECT id FROM calls WHERE id = ?", (call_id,))
        existing = await cursor.fetchone()

        if existing:
            # Update existing call
            await self.db.execute(
                """UPDATE calls SET
                   status = ?, caller_device_id = ?, called_device_id = ?, msn = ?,
                   trunk_id = ?, line_id = ?, is_internal = ?, connected_at = ?,
                   finished_at = ?, duration_seconds = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    status,
                    caller_device_id,
                    called_device_id,
                    msn,
                    trunk_id,
                    line_id,
                    1 if is_internal else 0,
                    connected_at,
                    finished_at,
                    duration_seconds,
                    now,
                    call_id,
                ),
            )
        else:
            # Create new call
            await self.db.execute(
                """INSERT INTO calls (
                   id, connection_id, caller_number, called_number, direction, status,
                   caller_device_id, called_device_id, msn, trunk_id, line_id, is_internal,
                   started_at, connected_at, finished_at, duration_seconds,
                   created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    call_id,
                    connection_id,
                    caller_number,
                    called_number,
                    direction,
                    status,
                    caller_device_id,
                    called_device_id,
                    msn,
                    trunk_id,
                    line_id,
                    1 if is_internal else 0,
                    started_at or now,
                    connected_at,
                    finished_at,
                    duration_seconds,
                    now,
                    now,
                ),
            )

        await self.db.commit()
        return await self.get_call(call_id)

    async def get_call(self, call_id: str) -> Optional[dict]:
        """Get a single call by ID, enriched with contact display names."""
        cursor = await self.db.execute(
            """SELECT c.*,
                      COALESCE(cc.name, c.caller_number) AS caller_display,
                      COALESCE(ca.name, c.called_number) AS called_display
               FROM calls c
               LEFT JOIN contacts cc ON cc.number = c.caller_number
               LEFT JOIN contacts ca ON ca.number = c.called_number
               WHERE c.id = ?""",
            (call_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_call(row) if row else None

    async def get_calls(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        line_id: Optional[int] = None,
        search: Optional[str] = None,
        msn: Optional[list[str]] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """Get paginated aggregated calls (cursor-based).

        Args:
            cursor: UUID of the last seen row (exclusive). None fetches from the start.
            limit: Maximum number of rows to return.
            direction: Filter by 'inbound' or 'outbound' (optional)
            status: Filter by status (optional)
            line_id: Filter by line ID (optional)
            search: Free-text search across caller_number, called_number, contact names (optional)
            msn: Filter by one or more MSNs — matches the stored msn column (optional)

        Returns:
            Tuple of (call records, next_cursor). next_cursor is None when no more rows exist.
        """
        where_clauses = []
        params: list = []

        if direction:
            where_clauses.append("c.direction = ?")
            params.append(direction)
        if status:
            where_clauses.append("c.status = ?")
            params.append(status)
        if line_id is not None:
            where_clauses.append("c.line_id = ?")
            params.append(line_id)
        if search:
            where_clauses.append(
                "(c.caller_number LIKE ? OR c.called_number LIKE ?"
                " OR cc.name LIKE ? OR ca.name LIKE ?)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term])
        if msn:
            placeholders = ",".join("?" * len(msn))
            where_clauses.append("c.msn IN (" + placeholders + ")")
            params.extend(msn)
        if cursor:
            where_clauses.append("c.id < ?")
            params.append(cursor)

        where = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        join = (
            " LEFT JOIN contacts cc ON cc.number = c.caller_number"
            " LEFT JOIN contacts ca ON ca.number = c.called_number"
        )

        params.append(limit)
        db_cursor = await self.db.execute(
            "SELECT c.*,"
            " COALESCE(cc.name, c.caller_number) AS caller_display,"
            " COALESCE(ca.name, c.called_number) AS called_display"
            " FROM calls c" + join + where + " ORDER BY c.id DESC LIMIT ?",
            params,
        )
        rows = await db_cursor.fetchall()
        result = [self._row_to_call(row) for row in rows]
        next_cursor = result[-1]["id"] if len(result) == limit else None
        return result, next_cursor

    async def get_call_by_connection_id(self, connection_id: int) -> Optional[dict]:
        """Get the most recent call for a Fritz connection_id."""
        cursor = await self.db.execute(
            "SELECT * FROM calls WHERE connection_id = ? ORDER BY started_at DESC LIMIT 1",
            (connection_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_call(row) if row else None

    async def get_display_name(self, number: str) -> str:
        """Get a human-readable display name for a phone number.

        Lookup order:
        1. contacts table (exact match on number)
        2. cache table (most recent non-expired entry across all adapters)
        3. raw number as fallback
        """
        # 1. contacts lookup
        contact = await self.get_contact(number)
        if contact and contact.get("name"):
            return contact["name"]

        # 2. cache fallback — pick the most recently cached non-expired entry with a name
        cursor = await self.db.execute(
            """SELECT result_json, cached_at, ttl_days FROM cache
               WHERE number = ?
               ORDER BY cached_at DESC""",
            (number,),
        )
        rows = await cursor.fetchall()
        for row in rows:
            row_dict = dict(row)
            cached_at = datetime.fromisoformat(row_dict["cached_at"]).replace(
                tzinfo=UTC
            )
            if datetime.now(UTC) > cached_at + timedelta(days=row_dict["ttl_days"]):
                continue  # expired
            result = json.loads(row_dict["result_json"])
            name = result.get("name")
            if name:
                return name

        # 3. Fallback: raw number
        return number

    # --- Helpers ---

    @staticmethod
    def _row_to_contact(row) -> dict:
        """Convert a database row to a contact dictionary."""
        data = dict(row)
        data["tags"] = json.loads(data.get("tags") or "[]")
        return data

    @staticmethod
    def _row_to_call(row) -> dict:
        """Convert a database row to a call dictionary."""
        data = dict(row)
        # Convert is_internal from integer to boolean
        data["is_internal"] = bool(data.get("is_internal", 0))
        return data
