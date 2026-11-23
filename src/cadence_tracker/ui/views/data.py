"""Réglages > Import et synchronisation: Garmin sync, file import, backup, log.

Specs: docs/specs/F01-import-synchronisation.md, F08-sauvegarde.md
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime

import pandas as pd
import streamlit as st

from cadence_tracker.ingest import garmin
from cadence_tracker.ingest.files import iter_raw_bytes
from cadence_tracker.ingest.pipeline import import_many
from cadence_tracker.storage import repository as repo
from cadence_tracker.ui import common, theme

STATUS_FR = {
    "imported": "importée",
    "updated": "mise à jour",
    "duplicate": "doublon ignoré",
    "already_imported": "déjà importé",
    "skipped": "ignorée",
    "error": "erreur",
}


def _fr_ts(value: str) -> str:
    """ISO UTC timestamp -> local time '19/11/2026 20:08'."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(datetime.now().astimezone().tzinfo)
    return f"{ts:%d/%m/%Y %H:%M}"


def _fr_date(value: str) -> str:
    return f"{pd.Timestamp(value):%d/%m/%Y}"


def _results_summary(results) -> None:
    counts = Counter(r.status for r in results)
    if not results:
        st.info("Rien à importer.")
        return
    parts = [
        f"**{n}** {STATUS_FR.get(s, s)}{'s' if n > 1 and s in ('imported', 'updated', 'skipped') else ''}"
        for s, n in counts.items()
    ]
    st.success(", ".join(parts) + ".", icon=":material/task_alt:")
    errors = [r for r in results if r.status in {"error", "skipped"}]
    if errors:
        with st.expander("Détails des fichiers ignorés ou en erreur"):
            st.dataframe(
                pd.DataFrame(
                    [{"fichier": r.origin, "statut": STATUS_FR.get(r.status), "message": r.message} for r in errors]
                ),
                hide_index=True,
                width="stretch",
            )


def _garmin_section() -> None:
    st.subheader("Garmin Connect")
    st.caption(
        "Synchronisation via l'**API personnelle officielle** de Garmin : la clé se crée sur "
        "[connect.garmin.com › Paramètres › Personal API Key](https://connect.garmin.com/app/settings/personalApiToken) "
        "(durée de validité au choix, 1 an maximum). Elle est stockée dans le trousseau du système, jamais en clair dans le projet."
    )
    key_present = bool(garmin.get_api_key())
    state = repo.get_sync_state(common.conn(), garmin.SOURCE)
    last_sync = state.get("last_sync_at")
    last_run = state.get("last_activity_start")
    theme.stat_row(
        [
            (
                "Clé API",
                "Configurée" if key_present else "À ajouter",
                "",
                "rangée dans le trousseau" if key_present else "voir ci-dessous",
                key_present,
            ),
            ("Dernière synchronisation", _fr_ts(last_sync) if last_sync else "Jamais", ""),
            ("Dernière sortie synchronisée", _fr_date(last_run) if last_run else "–", ""),
        ]
    )

    with st.expander("Configurer la clé", expanded=not key_present), st.form("garmin_key", clear_on_submit=True):
        key = st.text_input("Clé Personal API", type="password")
        a, b = st.columns(2)
        if a.form_submit_button("Enregistrer la clé", type="primary") and key.strip():
            garmin.set_api_key(key)
            st.toast("Clé enregistrée dans le trousseau.", icon=":material/key:")
            st.rerun()
        if b.form_submit_button("Supprimer la clé"):
            garmin.delete_api_key()
            st.rerun()

    if not key_present:
        return
    mode = st.radio(
        "Synchroniser",
        ["new", "since", "full"],
        horizontal=True,
        format_func={"new": "Nouvelles activités", "since": "Depuis une date", "full": "Tout l'historique"}.get,
    )
    since = (
        st.date_input("Depuis le", value=date(date.today().year, 1, 1), format="DD/MM/YYYY")
        if mode == "since"
        else None
    )
    if st.button("Lancer la synchronisation", type="primary", icon=":material/sync:"):
        run_sync(since=since, full=mode == "full")


def run_sync(since: date | None = None, full: bool = False) -> None:
    """Garmin sync with live progress (also used by the Sorties page button)."""
    with st.status("Synchronisation Garmin…", expanded=True) as status:
        try:
            report = garmin.sync(common.conn(), since=since, full=full, progress=st.write)
        except garmin.GarminKeyMissing as exc:
            status.update(label=str(exc), state="error")
            return
        except Exception as exc:  # network, auth…
            status.update(label=f"Échec : {exc}", state="error")
            return
        new = report.imported
        plural = "s" if new > 1 else ""
        label = f"{new} nouvelle{plural} sortie{plural}" if new else "Aucune nouvelle sortie"
        status.update(label=label, state="error" if report.stopped_early else "complete", expanded=False)
    if report.stopped_early:
        st.warning(
            f"Synchronisation interrompue : {report.stopped_early}. Relancez plus tard, elle reprendra sans doublon."
        )
    if report.results:
        _results_summary(report.results)
    common.invalidate()


def _files_section() -> None:
    st.subheader("Importer des fichiers")
    st.caption(
        "FIT (recommandé : données complètes), TCX, GPX, ou archives ZIP — y compris l'export complet Garmin "
        "(« Exporter vos données ») et l'export Strava (dossier *activities*). Les doublons sont détectés automatiquement. "
        "Pour une très grosse archive, préférez la ligne de commande : `ctrack import chemin/vers/archive.zip`."
    )
    files = st.file_uploader(
        "Fichiers", type=["fit", "tcx", "gpx", "zip", "gz"], accept_multiple_files=True, label_visibility="collapsed"
    )
    if files and st.button(f"Importer {len(files)} fichier(s)", type="primary", icon=":material/upload:"):
        raws = [raw for f in files for raw in iter_raw_bytes(f.name, f.getvalue())]
        bar = st.progress(0.0, text="Import…")
        results = import_many(
            common.conn(), raws, progress=lambda i, name: bar.progress(i / max(len(raws), 1), text=name)
        )
        bar.empty()
        _results_summary(results)
        common.invalidate()


def _backup_section() -> None:
    st.subheader("Sauvegarde")
    counts = repo.counts(common.conn())
    st.caption(
        f"{counts['activities']} sorties et {common.fr_num(counts['samples'], 0)} points de mesure. "
        "L'application n'affiche ni ne permet d'exporter aucune donnée GPS, et ne conserve pas les fichiers importés."
    )
    if st.button("Créer une sauvegarde de la base", icon=":material/backup:"):
        from cadence_tracker.backup import backup

        path = backup()
        st.toast(f"Sauvegarde créée : {path.name}", icon=":material/check:")


def render_import() -> None:
    st.caption("Vos sorties restent sur cet ordinateur. Rien n'est envoyé ailleurs.")
    _garmin_section()
    st.divider()
    _files_section()
    st.divider()
    _backup_section()
    st.divider()
    st.subheader("Journal des imports")
    log = repo.recent_imports(common.conn(), 200)
    if log.empty:
        st.caption("Aucun import pour l'instant.")
    else:
        log["status"] = log["status"].map(STATUS_FR).fillna(log["status"])
        log["at"] = log["at"].map(_fr_ts)
        log["message"] = log["message"].fillna("")
        st.dataframe(
            log[["at", "origin", "status", "activity_id", "message"]],
            hide_index=True,
            width="stretch",
            column_config={
                "at": "Date",
                "origin": "Origine",
                "status": "Résultat",
                "activity_id": "Sortie #",
                "message": "Détail",
            },
        )
