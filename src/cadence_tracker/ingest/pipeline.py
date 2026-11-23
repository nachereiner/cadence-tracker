"""Ingestion pipeline: raw bytes -> parsed activity -> deduplicated storage -> metrics.

Deduplication (docs/specs/F02-stockage-dedoublonnage.md), in order:

1. same raw file content (SHA-256) already seen          -> `already_imported`
2. same (source, source_id), e.g. Garmin activityId      -> `duplicate`
3. another activity starting within ±2 min with a similar
   duration (same run from another source/export)        -> keep the richer one
   (cadence, heart rate, then more samples): `updated` or `duplicate`.

User annotations (type, cadence focus, exclusion, notes) are never overwritten.
Re-running an import or a sync is therefore always safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from cadence_tracker.analysis import classification, metrics
from cadence_tracker.ingest.files import RawFile, parse_raw
from cadence_tracker.models import RUNNING_SPORTS, ParsedActivity
from cadence_tracker.storage import repository as repo
from cadence_tracker.units import cadence_to_spm

log = logging.getLogger(__name__)
MIN_DURATION_S = 120


@dataclass
class ImportResult:
    origin: str
    status: str  # imported | updated | duplicate | already_imported | skipped | error
    activity_id: int | None = None
    message: str = ""


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _richness(has_cadence, has_hr, n_samples) -> tuple:
    return (int(has_cadence or 0), int(has_hr or 0), int(n_samples or 0))


def clean_samples(parsed: ParsedActivity) -> pd.DataFrame:
    df = parsed.samples.copy()
    df["cadence_spm"] = cadence_to_spm(df["cadence_raw"], parsed.cadence_unit)
    df.loc[df["heart_rate"] <= 0, "heart_rate"] = None
    df.loc[(df["cadence_spm"] <= 0) | (df["cadence_spm"] > 260), "cadence_spm"] = None
    df.loc[df["speed_mps"] > 12, "speed_mps"] = None  # > 43 km/h: sensor glitch
    return df.drop(columns=["cadence_raw"]).sort_values("t_s").reset_index(drop=True)


def remember_file(conn: sqlite3.Connection, raw: RawFile, source: str, source_id: str | None) -> str:
    """Record the file's hash (for deduplication). The file itself is never stored:
    original FIT/GPX/TCX files contain GPS positions (docs/adr/0004)."""
    sha = hashlib.sha256(raw.data).hexdigest()
    repo.record_seen_file(
        conn,
        sha256=sha,
        original_name=Path(raw.name).name,
        fmt=raw.fmt,
        size_bytes=len(raw.data),
        source=source,
        source_id=source_id,
    )
    return sha


def ingest_parsed(
    conn: sqlite3.Connection,
    parsed: ParsedActivity,
    *,
    origin: str,
    raw_sha256: str | None = None,
    settings=None,
) -> ImportResult:
    """Store one parsed activity (deduplicated) and compute its metrics."""
    settings = settings or repo.load_settings(conn)
    if parsed.sport not in RUNNING_SPORTS:
        return _skip(conn, origin, f"Sport ignoré : {parsed.sport}")
    samples = clean_samples(parsed)
    if samples.empty or samples["t_s"].max() < MIN_DURATION_S:
        return _skip(conn, origin, "Activité trop courte ou vide")

    activity_metrics, splits = metrics.compute_metrics(samples, settings, parsed.laps, parsed.summary)
    start = parsed.start_time_utc.astimezone(UTC).replace(microsecond=0)
    values = {
        "source": parsed.source,
        "source_id": parsed.source_id,
        "raw_sha256": raw_sha256,
        "name": parsed.name,
        "workout_name": parsed.workout_name,
        "device": parsed.device,
        "sport": parsed.sport,
        "sub_sport": parsed.sub_sport,
        "start_time_utc": iso_utc(start),
        "utc_offset_s": parsed.utc_offset_s,
        "elapsed_s": activity_metrics.get("elapsed_s"),
        "distance_m": activity_metrics.get("distance_m"),
        "device_summary": json.dumps({k: v for k, v in parsed.summary.items() if v is not None}, default=str),
    }

    existing = repo.find_by_source(conn, parsed.source, parsed.source_id)
    if existing is not None:
        return ImportResult(origin, "duplicate", existing["id"], "Déjà présente (même identifiant source)")

    new_rich = _richness(activity_metrics.get("has_cadence"), activity_metrics.get("has_hr"), len(samples))
    for other in repo.find_overlapping(conn, start, activity_metrics.get("elapsed_s") or 0):
        old_rich = _richness(other["has_cadence"], other["has_hr"], other["n_samples"])
        if new_rich > old_rich:
            # Same run, better data: replace data, keep the user's annotations and name.
            values_update = {k: v for k, v in values.items() if k != "name" or not other["name"]}
            with conn:
                repo.update_activity_data(conn, other["id"], values_update)
                _store_data(conn, other["id"], samples, parsed, activity_metrics, splits)
                repo.log_import(conn, origin, "updated", other["id"], f"Remplace la version {other['source']}")
            return ImportResult(
                origin, "updated", other["id"], f"Données plus complètes que la version {other['source']}"
            )
        with conn:
            repo.log_import(conn, origin, "duplicate", other["id"], f"Doublon de la version {other['source']}")
        return ImportResult(
            origin, "duplicate", other["id"], f"Doublon de l'activité #{other['id']} ({other['source']})"
        )

    with conn:
        activity_id = repo.insert_activity(conn, values)
        _store_data(conn, activity_id, samples, parsed, activity_metrics, splits)
        repo.log_import(conn, origin, "imported", activity_id)
    return ImportResult(origin, "imported", activity_id)


def _skip(conn, origin: str, message: str) -> ImportResult:
    with conn:
        repo.log_import(conn, origin, "skipped", message=message)
    return ImportResult(origin, "skipped", message=message)


def _store_data(conn, activity_id, samples, parsed, activity_metrics, splits) -> None:
    repo.replace_samples(conn, activity_id, samples)
    repo.replace_laps(conn, activity_id, parsed.laps)
    repo.replace_splits(conn, activity_id, splits)
    repo.upsert_metrics(conn, activity_id, activity_metrics)


def import_raw(
    conn: sqlite3.Connection,
    raw: RawFile,
    *,
    source: str | None = None,
    source_id: str | None = None,
    name: str | None = None,
    sport: str | None = None,
    sub_sport: str | None = None,
    settings=None,
) -> list[ImportResult]:
    """Import one decompressed file (from disk, upload or API download).

    `sport` / `sub_sport`: category chosen in the source app (Garmin typeKey). It
    wins over the file, whose own type can be stale (e.g. a GPX tagged "hiking").
    """
    sha = hashlib.sha256(raw.data).hexdigest()
    origin = Path(raw.name).name if source != "garmin_api" else f"garmin:{source_id}"
    if repo.raw_file_known(conn, sha):
        return [ImportResult(origin, "already_imported", message="Fichier déjà importé")]
    try:
        parsed_list = parse_raw(raw, source=source, source_id=source_id)
    except Exception as exc:  # corrupted / unsupported file: report, never crash a batch
        log.warning("Parse error for %s: %s", raw.name, exc)
        with conn:
            repo.log_import(conn, origin, "error", message=f"Lecture impossible : {exc}")
        return [ImportResult(origin, "error", message=f"Lecture impossible : {exc}")]
    if not parsed_list:
        with conn:
            repo.log_import(conn, origin, "skipped", message="Aucune donnée d'activité")
        return [ImportResult(origin, "skipped", message="Aucune donnée d'activité")]

    with conn:
        sha = remember_file(conn, raw, source or f"{raw.fmt}_file", source_id)
    results = []
    for parsed in parsed_list:
        if name and not parsed.name:
            parsed.name = name
        if sport:
            parsed.sport = sport
        if sub_sport and parsed.sub_sport == "road":
            parsed.sub_sport = sub_sport
        results.append(ingest_parsed(conn, parsed, origin=origin, raw_sha256=sha, settings=settings))
    return results


def import_many(conn: sqlite3.Connection, raws: Iterable[RawFile], progress=None) -> list[ImportResult]:
    settings = repo.load_settings(conn)
    results: list[ImportResult] = []
    for index, raw in enumerate(raws):
        results.extend(import_raw(conn, raw, settings=settings))
        if progress:
            progress(index + 1, raw.name)
    if any(r.status in {"imported", "updated"} for r in results):
        reclassify(conn, settings)
    return results


def reclassify(conn: sqlite3.Connection, settings=None) -> int:
    """Recompute the automatic session type of every activity."""
    settings = settings or repo.load_settings(conn)
    df = repo.load_activities(conn)
    result = classification.classify_all(df, settings)
    with conn:
        for row in result.itertuples(index=False):
            repo.set_classification(conn, int(row.id), row.session_type_auto, row.classification_reason)
    return len(result)


def recompute_all(conn: sqlite3.Connection, progress=None) -> int:
    """Recompute metrics and splits from stored samples (after a settings change)."""
    settings = repo.load_settings(conn)
    ids = repo.activity_ids(conn)
    for index, activity_id in enumerate(ids):
        samples = repo.load_samples(conn, activity_id)
        if samples.empty:
            continue
        laps = repo.load_laps(conn, activity_id)
        row = repo.get_activity_row(conn, activity_id)
        summary = json.loads(row["device_summary"] or "{}")
        activity_metrics, splits = metrics.compute_metrics(samples, settings, laps, summary)
        with conn:
            repo.replace_splits(conn, activity_id, splits)
            repo.upsert_metrics(conn, activity_id, activity_metrics)
        if progress:
            progress(index + 1, len(ids))
    reclassify(conn, settings)
    return len(ids)
