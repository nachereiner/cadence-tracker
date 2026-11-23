-- 003 — Index of imported files, without file path (docs/adr/0004).
-- New imports no longer archive the original files (they contain the GPS
-- trace): only their hash is kept for deduplication. This migration is
-- NON-destructive: legacy GPS columns and the legacy `raw_files` table are left
-- untouched at rest, but the application never reads them (explicit column
-- lists in storage/repository.py). `ctrack purge-gps` erases them on request.

CREATE TABLE seen_files (
    sha256        TEXT PRIMARY KEY,         -- content hash: "already imported" check
    original_name TEXT,
    fmt           TEXT NOT NULL,
    size_bytes    INTEGER,
    source        TEXT,
    source_id     TEXT,
    first_seen_at TEXT NOT NULL
);
INSERT INTO seen_files (sha256, original_name, fmt, size_bytes, source, source_id, first_seen_at)
    SELECT sha256, original_name, fmt, size_bytes, source, source_id, first_seen_at FROM raw_files;
