"""Local database backups (docs/specs/F08-sauvegarde.md).

There is deliberately no export feature: data never leaves the machine through
the app, and the database contains no GPS position (docs/adr/0004).
`backup()` takes a consistent snapshot of the SQLite database (online backup
API, safe while the UI is running) and keeps the N most recent ones.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from cadence_tracker import config


def backup(db_file: Path | None = None, dest_dir: Path | None = None, keep: int = 10) -> Path:
    db_file = Path(db_file or config.db_path())
    dest_dir = Path(dest_dir or config.backups_dir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{db_file.stem}-{datetime.now():%Y%m%d-%H%M%S}.db"
    src = sqlite3.connect(db_file)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    snapshots = sorted(dest_dir.glob(f"{db_file.stem}-*.db"))
    for old in snapshots[:-keep]:
        old.unlink()
    return target
