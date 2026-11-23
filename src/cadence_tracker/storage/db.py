"""SQLite connection and schema migrations.

Migrations are plain SQL files in `storage/migrations/NNN_description.sql`,
applied in order; the applied level is stored in `PRAGMA user_version`. To evolve
the schema, add a new numbered file — never edit an applied one.
"""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

from cadence_tracker import config


def _migrations() -> list[tuple[int, str]]:
    folder = resources.files("cadence_tracker.storage") / "migrations"
    found = []
    for entry in folder.iterdir():
        match = re.match(r"^(\d+)_.*\.sql$", entry.name)
        if match:
            found.append((int(match.group(1)), entry.read_text(encoding="utf-8")))
    return sorted(found)


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open (and create/migrate if needed) the database."""
    path = Path(path) if path else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")  # deleted values are overwritten, not left in free pages
    conn.execute("PRAGMA journal_mode = WAL")  # UI can read while a sync writes
    conn.execute("PRAGMA synchronous = NORMAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in _migrations():
        if version > current:
            with conn:
                conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {version}")
            current = version
    return current
