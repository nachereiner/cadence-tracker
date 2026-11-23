"""Command-line interface: `ctrack --help`.

Everything the UI can do on data (import, sync, recompute, backup) is
also available here, so it can be scripted or scheduled (cron/launchd).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import typer

from cadence_tracker import config

app = typer.Typer(help="Running Cadence Tracker — suivi local de la cadence de course.", no_args_is_help=True)
garmin_app = typer.Typer(help="Synchronisation Garmin Connect (API personnelle officielle).", no_args_is_help=True)
app.add_typer(garmin_app, name="garmin")

STATUS_FR = {
    "imported": "importées",
    "updated": "mises à jour (données plus complètes)",
    "duplicate": "doublons ignorés",
    "already_imported": "fichiers déjà importés",
    "skipped": "ignorées (autre sport, trop courtes…)",
    "error": "erreurs",
}

DemoOption = Annotated[bool, typer.Option("--demo", help="Utiliser la base de démonstration (data/demo.db).")]


def _use_demo(demo: bool) -> None:
    if demo:
        os.environ["CTRACK_DB"] = str(config.demo_db_path())


def _conn():
    from cadence_tracker.storage import db

    return db.connect()


def _print_results(results) -> None:
    counts = Counter(r.status for r in results)
    for status, label in STATUS_FR.items():
        if counts.get(status):
            typer.echo(f"  {counts[status]:>4} {label}")
    for r in results:
        if r.status == "error":
            typer.secho(f"  ! {r.origin} : {r.message}", fg=typer.colors.RED)


@app.command("init")
def init(demo: DemoOption = False) -> None:
    """Crée le dossier de données et la base (sans effet si elle existe)."""
    _use_demo(demo)
    _conn()
    typer.echo(f"Base prête : {config.db_path()}")


@app.command("import")
def import_files(
    paths: Annotated[list[Path], typer.Argument(help="Fichiers FIT/TCX/GPX, dossiers ou archives ZIP.", exists=True)],
    demo: DemoOption = False,
) -> None:
    """Importe des fichiers d'activité (y compris les exports complets Garmin/Strava)."""
    from cadence_tracker.ingest.files import iter_raw_files
    from cadence_tracker.ingest.pipeline import import_many

    _use_demo(demo)
    conn = _conn()

    def progress(i, name):
        if i % 25 == 0:
            typer.echo(f"  … {i} fichiers traités")

    results = import_many(conn, iter_raw_files(paths), progress=progress)
    typer.echo(f"{len(results)} activités examinées :")
    _print_results(results)


@app.command("recompute")
def recompute(demo: DemoOption = False) -> None:
    """Recalcule métriques, splits et classification (après changement de paramètres)."""
    from cadence_tracker.ingest.pipeline import recompute_all

    _use_demo(demo)
    n = recompute_all(_conn())
    typer.echo(f"{n} activités recalculées.")


@app.command("backup")
def backup_cmd(demo: DemoOption = False) -> None:
    """Sauvegarde la base de données (data/backups, 10 dernières conservées)."""
    from cadence_tracker.backup import backup

    _use_demo(demo)
    _conn()
    typer.echo(f"Sauvegarde : {backup()}")


@app.command("purge-gps")
def purge_gps_cmd(
    yes: Annotated[bool, typer.Option("--yes", help="Ne pas demander de confirmation.")] = False,
) -> None:
    """Efface définitivement les données GPS héritées (optionnel, irréversible).

    L'application ne lit jamais ces données ; cette commande les supprime en plus
    du disque : colonnes GPS de la base et de ses sauvegardes (fichiers réécrits),
    fichiers originaux archivés (data/raw).
    """
    import shutil

    from cadence_tracker.privacy import purge_gps
    from cadence_tracker.storage import db

    targets = [config.db_path(), config.demo_db_path(), *sorted(config.backups_dir().glob("*.db"))]
    targets = [t for t in dict.fromkeys(targets) if t.exists()]
    raw = config.data_dir() / "raw"
    typer.echo("Bases concernées : " + ", ".join(t.name for t in targets))
    typer.echo(f"Fichiers originaux : {raw if raw.exists() else 'aucun'}")
    if not yes and not typer.confirm("Effacer définitivement ces données GPS ?"):
        raise typer.Exit(1)
    for target in targets:
        conn = db.connect(target)
        removed = purge_gps(conn)
        conn.close()
        typer.echo(f"  {target.name} : {sum(len(c) for c in removed.values())} colonne(s) GPS effacée(s)")
    if raw.exists():
        shutil.rmtree(raw)
        typer.echo(f"  {raw} supprimé")


@app.command("demo")
def demo_cmd(
    weeks: Annotated[int, typer.Option(help="Nombre de semaines d'historique.")] = 36,
    seed: int = 7,
) -> None:
    """(Re)crée la base de démonstration avec un historique synthétique."""
    from cadence_tracker import demo
    from cadence_tracker.ingest.pipeline import ingest_parsed, reclassify
    from cadence_tracker.storage import db, repository

    path = config.demo_db_path()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    conn = db.connect(path)
    repository.set_flag(conn, "is_demo", True)
    settings = repository.load_settings(conn)
    settings.cadence_target_spm = 172
    settings.cadence_goal_start = (date.today() - timedelta(weeks=weeks) + timedelta(days=70)).isoformat()
    repository.save_settings(conn, settings)
    activities = demo.generate(weeks=weeks, seed=seed)
    with typer.progressbar(activities, label="Génération") as bar:
        for activity in bar:
            ingest_parsed(conn, activity, origin=f"demo:{activity.source_id}", settings=settings)
    reclassify(conn)
    typer.echo(f"Base de démonstration : {path} ({len(activities)} activités)")
    typer.echo("Lancer l'interface : ctrack ui --demo")


@app.command("ui")
def ui(
    demo: DemoOption = False,
    port: int = 8501,
) -> None:
    """Lance l'interface web locale (Streamlit)."""
    _use_demo(demo)
    script = Path(__file__).parent / "ui" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script),
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    # Local only: the UI has no authentication and must never listen on the network.
    cmd += ["--server.address", "127.0.0.1"]
    # cwd = project root so that .streamlit/config.toml (theme, upload size) is picked up.
    raise typer.Exit(subprocess.call(cmd, env=os.environ.copy(), cwd=config.PROJECT_ROOT))


# ------------------------------------------------------------------ garmin
@garmin_app.command("set-key")
def garmin_set_key() -> None:
    """Enregistre la clé Garmin Personal API dans le trousseau du système."""
    from cadence_tracker.ingest.garmin import set_api_key

    typer.echo("Créez la clé sur https://connect.garmin.com/app/settings/personalApiToken")
    key = typer.prompt("Clé API personnelle", hide_input=True)
    set_api_key(key)
    typer.secho("Clé enregistrée dans le trousseau (Keychain).", fg=typer.colors.GREEN)


@garmin_app.command("forget-key")
def garmin_forget_key() -> None:
    """Supprime la clé du trousseau et le jeton en cache."""
    from cadence_tracker.ingest.garmin import delete_api_key

    delete_api_key()
    typer.echo("Clé et jeton supprimés. Pensez à révoquer la clé sur Garmin Connect si besoin.")


@garmin_app.command("status")
def garmin_status() -> None:
    """Affiche l'état de la configuration et de la dernière synchronisation."""
    from cadence_tracker.ingest.garmin import SOURCE, get_api_key
    from cadence_tracker.storage import repository

    typer.echo(f"Clé configurée : {'oui' if get_api_key() else 'non'}")
    state = repository.get_sync_state(_conn(), SOURCE)
    typer.echo(f"Dernière synchronisation : {state.get('last_sync_at') or 'jamais'}")
    typer.echo(f"Dernière activité synchronisée : {state.get('last_activity_start') or '–'}")


@garmin_app.command("sync")
def garmin_sync(
    since: Annotated[str | None, typer.Option(help="Date de début AAAA-MM-JJ.")] = None,
    full: Annotated[bool, typer.Option("--full", help="Parcourir tout l'historique.")] = False,
) -> None:
    """Synchronise les nouvelles activités (incrémental, sans doublons)."""
    from cadence_tracker.ingest.garmin import GarminKeyMissing, sync

    try:
        report = sync(_conn(), since=date.fromisoformat(since) if since else None, full=full, progress=typer.echo)
    except GarminKeyMissing as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(1) from exc
    typer.echo(
        f"{report.listed} activités listées, {report.running} courses, {report.already_synced} déjà synchronisées, "
        f"{report.downloaded} téléchargées."
    )
    _print_results(report.results)
    if report.stopped_early:
        typer.secho(f"Synchronisation interrompue : {report.stopped_early}", fg=typer.colors.YELLOW)
        typer.echo("Relancez plus tard : elle reprendra là où elle s'est arrêtée.")


if __name__ == "__main__":
    app()
