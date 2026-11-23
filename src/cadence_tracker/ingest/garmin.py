"""Garmin Connect synchronisation through the official *Personal API* (Oct. 2026).

Flow (docs/specs/F01-import-synchronisation.md):

1. the Personal API key (created on connect.garmin.com > Settings > Personal API
   Key) is read from the OS keychain (`keyring`), or from the env variable /
   key file supported by Garmin's client;
2. it is exchanged for a 24 h bearer token (cached by Garmin's client, 0600);
3. activities are listed with `search_activities` (paginated, by date);
4. for each new running activity the *original FIT file* is downloaded (zip),
   archived and imported by the standard pipeline (dedup included).

Incremental: a normal sync starts 3 days before the last synced activity, so
re-running it is cheap and idempotent. `full=True` walks the whole history.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from cadence_tracker import config
from cadence_tracker.ingest.files import iter_raw_bytes
from cadence_tracker.ingest.pipeline import ImportResult, import_raw, reclassify
from cadence_tracker.models import normalize_sub_sport
from cadence_tracker.storage import repository as repo

log = logging.getLogger(__name__)

SOURCE = "garmin_api"
PAGE_SIZE = 50
RUNNING_TYPE_KEYS = {
    "running",
    "trail_running",
    "treadmill_running",
    "track_running",
    "street_running",
    "indoor_running",
    "virtual_run",
    "ultra_run",
    "obstacle_run",
}


class GarminKeyMissing(RuntimeError):
    pass


# ---------------------------------------------------------------- credentials
def get_api_key() -> str | None:
    """Key from the OS keychain, else from Garmin's own discovery (env / key file)."""
    try:
        import keyring

        key = keyring.get_password(config.KEYRING_SERVICE, config.KEYRING_GARMIN_KEY)
        if key:
            return key
    except Exception as exc:  # no keychain backend available
        log.debug("keyring unavailable: %s", exc)
    try:
        from garmin_personal_api import resolve_api_key

        return resolve_api_key()
    except Exception:
        return None


def set_api_key(key: str) -> None:
    import keyring

    keyring.set_password(config.KEYRING_SERVICE, config.KEYRING_GARMIN_KEY, key.strip())


def delete_api_key() -> None:
    import keyring

    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(config.KEYRING_SERVICE, config.KEYRING_GARMIN_KEY)
    config.garmin_token_cache().unlink(missing_ok=True)


def default_client_factory(force_refresh: bool = False):
    """Build an authenticated official client (imported lazily)."""
    from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

    key = get_api_key()
    if not key:
        raise GarminKeyMissing("Aucune clé Garmin Personal API configurée (ctrack garmin set-key).")
    cache = config.garmin_token_cache()
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with PersonalApiAuthenticator(bearer_token_cache_file=cache) as auth:
        token = auth.obtain_token(key, force_refresh=force_refresh)
    return GarminPersonalApiClient(token.access_token)


# ----------------------------------------------------------------------- sync
@dataclass
class SyncReport:
    listed: int = 0
    running: int = 0
    already_synced: int = 0
    downloaded: int = 0
    results: list[ImportResult] = field(default_factory=list)
    stopped_early: str | None = None

    @property
    def imported(self) -> int:
        return sum(r.status in {"imported", "updated"} for r in self.results)


def _status_code(exc: Exception) -> int | None:
    return getattr(exc, "status_code", None)


def _parse_start(item: dict) -> str | None:
    value = item.get("startTimeGMT") or item.get("startTimeLocal")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace(" ", "T")).date().isoformat()
    except ValueError:
        return None


def sync(
    conn: sqlite3.Connection,
    *,
    since: date | None = None,
    full: bool = False,
    client_factory: Callable[..., object] = default_client_factory,
    progress: Callable[[str], None] | None = None,
    pause_s: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> SyncReport:
    report = SyncReport()
    settings = repo.load_settings(conn)
    state = repo.get_sync_state(conn, SOURCE)
    if since is None and not full and state.get("last_activity_start"):
        since = date.fromisoformat(state["last_activity_start"][:10]) - timedelta(days=3)
    if since is None and settings.garmin_history_start:
        since = date.fromisoformat(settings.garmin_history_start)
    end = date.today() + timedelta(days=1)

    client = client_factory()
    say = progress or (lambda msg: log.info(msg))
    say(f"Recherche des activités depuis {since or 'le début'}…")
    newest: str | None = state.get("last_activity_start")

    def call(fn, *args, **kwargs):
        """Call the API with one token refresh on 401 and backoff on 429/5xx."""
        nonlocal client
        for attempt in range(4):
            try:
                return fn(client, *args, **kwargs)
            except Exception as exc:
                code = _status_code(exc)
                if code == 401 and attempt == 0:
                    client = client_factory(force_refresh=True)
                    continue
                if code in {429, 500, 502, 503, 504} and attempt < 3:
                    wait = 30 * (attempt + 1)
                    say(f"Garmin limite les requêtes (HTTP {code}), nouvel essai dans {wait} s…")
                    sleep(wait)
                    continue
                raise

    start = 0
    try:
        while True:
            page = (
                call(
                    lambda c, offset=start: c.search_activities(
                        start=offset, limit=PAGE_SIZE, start_date=since, end_date=end
                    )
                )
                or []
            )
            if not page:
                break
            report.listed += len(page)
            for item in page:
                type_key = (item.get("activityType") or {}).get("typeKey", "")
                if type_key not in RUNNING_TYPE_KEYS:
                    continue
                report.running += 1
                activity_id = str(item.get("activityId"))
                started = _parse_start(item)
                if repo.source_id_seen(conn, SOURCE, activity_id):
                    report.already_synced += 1
                    continue
                say(f"Téléchargement de « {item.get('activityName') or activity_id} » ({started})")
                content = call(lambda c, aid=activity_id: c.download_activity(aid))
                report.downloaded += 1
                for raw in iter_raw_bytes(f"garmin-{activity_id}.zip", content):
                    report.results.extend(
                        import_raw(
                            conn,
                            raw,
                            source=SOURCE,
                            source_id=activity_id,
                            name=item.get("activityName"),
                            sport="running",
                            sub_sport=normalize_sub_sport(type_key) if type_key != "running" else None,
                            settings=settings,
                        )
                    )
                if started and (newest is None or started > newest):
                    newest = started
                sleep(pause_s)
            if len(page) < PAGE_SIZE:
                break
            start += PAGE_SIZE
    except Exception as exc:
        report.stopped_early = str(exc)
        log.warning("Garmin sync stopped: %s", exc)
    finally:
        close = getattr(client, "close", None)
        if close:
            close()

    if report.imported:
        reclassify(conn, settings)
    # Interrupted sync: keep the previous cursor so the next run covers the gap.
    repo.set_sync_state(
        conn,
        SOURCE,
        None if report.stopped_early else newest,
        {
            "listed": report.listed,
            "running": report.running,
            "downloaded": report.downloaded,
            "imported": report.imported,
            "error": report.stopped_early,
        },
    )
    return report
