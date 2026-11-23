-- 001 — Initial schema. See docs/architecture.md ("Modèle de données").
-- Rule: user annotations live in `activities` and are never overwritten by
-- re-imports or recomputation; everything in `activity_metrics` / `splits`
-- can be recomputed from `samples` (and `samples` from the raw files).

CREATE TABLE activities (
    id                  INTEGER PRIMARY KEY,
    source              TEXT NOT NULL,      -- fit_file | tcx_file | gpx_file | garmin_api | demo
    source_id           TEXT,               -- e.g. Garmin activityId
    raw_sha256          TEXT,               -- raw file the samples come from
    name                TEXT,
    workout_name        TEXT,
    device              TEXT,
    sport               TEXT NOT NULL,
    sub_sport           TEXT NOT NULL DEFAULT 'road',  -- road | trail | treadmill | track
    start_time_utc      TEXT NOT NULL,      -- ISO 8601, UTC
    utc_offset_s        INTEGER,
    elapsed_s           REAL,
    distance_m          REAL,
    device_summary      TEXT,               -- JSON totals computed by the watch
    -- User annotations
    session_type_manual TEXT,               -- overrides activity_metrics.session_type_auto
    cadence_focus       INTEGER,            -- NULL = undecided, 0/1 = user choice
    excluded            INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    imported_at         TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_activities_source ON activities(source, source_id) WHERE source_id IS NOT NULL;
CREATE INDEX ix_activities_start ON activities(start_time_utc);

CREATE TABLE samples (
    activity_id  INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    t_s          INTEGER NOT NULL,          -- seconds since start
    distance_m   REAL,
    speed_mps    REAL,
    cadence_spm  REAL,                      -- steps per minute (both feet)
    heart_rate   REAL,
    altitude_m   REAL,
    lat          REAL,
    lon          REAL,
    PRIMARY KEY (activity_id, t_s)
) WITHOUT ROWID;

CREATE TABLE laps (
    activity_id  INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    lap_index    INTEGER NOT NULL,
    start_s      REAL,
    duration_s   REAL,
    distance_m   REAL,
    speed_mps    REAL,
    heart_rate   REAL,
    cadence_spm  REAL,
    intensity    TEXT,
    PRIMARY KEY (activity_id, lap_index)
) WITHOUT ROWID;

CREATE TABLE splits (
    activity_id   INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    km            INTEGER NOT NULL,         -- 1-based kilometre index
    distance_m    REAL,
    duration_s    REAL,
    speed_mps     REAL,
    cadence_spm   REAL,
    heart_rate    REAL,
    elev_gain_m   REAL,
    grade_pct     REAL,
    elapsed_end_s REAL,
    PRIMARY KEY (activity_id, km)
) WITHOUT ROWID;

CREATE TABLE activity_metrics (
    activity_id           INTEGER PRIMARY KEY REFERENCES activities(id) ON DELETE CASCADE,
    metrics_version       INTEGER NOT NULL,
    computed_at           TEXT NOT NULL,
    elapsed_s             REAL,
    moving_s              REAL,
    running_s             REAL,
    distance_m            REAL,
    avg_speed_mps         REAL,
    cadence_mean          REAL,
    cadence_median        REAL,
    cadence_p10           REAL,
    cadence_p90           REAL,
    cadence_std           REAL,
    hr_mean               REAL,
    hr_peak               REAL,
    ascent_m              REAL,
    descent_m             REAL,
    ascent_per_km         REAL,
    stride_m              REAL,
    efficiency            REAL,
    decoupling_pct        REAL,
    cadence_first_half    REAL,
    cadence_second_half   REAL,
    cadence_drift_spm_h   REAL,
    cadence_fatigue_spm_h REAL,
    speed_cv              REAL,
    n_active_laps         INTEGER,
    n_rest_laps           INTEGER,
    active_lap_mean_s     REAL,
    has_hr                INTEGER,
    has_cadence           INTEGER,
    has_gps               INTEGER,
    has_altitude          INTEGER,
    start_lat             REAL,
    start_lon             REAL,
    session_type_auto     TEXT,
    classification_reason TEXT
);

CREATE TABLE raw_files (
    sha256        TEXT PRIMARY KEY,
    original_name TEXT,
    stored_path   TEXT NOT NULL,            -- relative to the data directory
    fmt           TEXT NOT NULL,
    size_bytes    INTEGER,
    source        TEXT,
    source_id     TEXT,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE import_log (
    id          INTEGER PRIMARY KEY,
    at          TEXT NOT NULL,
    origin      TEXT,
    status      TEXT NOT NULL,              -- imported | updated | duplicate | already_imported | skipped | error
    activity_id INTEGER,
    message     TEXT
);

CREATE TABLE sync_state (
    source              TEXT PRIMARY KEY,
    last_sync_at        TEXT,
    last_activity_start TEXT,
    details             TEXT
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL                     -- JSON
);
