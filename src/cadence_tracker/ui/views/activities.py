"""Sorties: sync new runs, then (collapsed) the editable list of runs.

Spec: docs/specs/F06-classification.md (manual corrections) and F01 (selection).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from cadence_tracker.analysis.classification import SESSION_TYPES
from cadence_tracker.ingest import garmin
from cadence_tracker.storage import repository as repo
from cadence_tracker.ui import common
from cadence_tracker.ui.views.data import run_sync

LABEL_TO_CODE = {v: k for k, v in SESSION_TYPES.items()}


def _table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": df["id"],
            "date": df["start_local"],
            "nom": df["title"],
            "type": df["type_label"],
            "auto": df["session_type_auto"].map(SESSION_TYPES).fillna("–"),
            "raison": df["classification_reason"].fillna(""),
            "inclure": ~df["excluded"],
            "km": df["distance_km"],
            "duree": df["elapsed_s"].map(common.duration),
            "allure": df["pace_s_km"].map(common.pace),
            "cadence": df["cadence_mean"],
            "fc": df["hr_mean"],
            "dplus": df["ascent_m"],
        }
    ).sort_values("date", ascending=False)


def _save(original: pd.DataFrame, edited: pd.DataFrame, df: pd.DataFrame) -> int:
    changes = 0
    auto = df.set_index("id")["session_type_auto"]
    orig = original.set_index("id")
    for row in edited.itertuples(index=False):
        before = orig.loc[row.id]
        fields = {}
        if row.nom != before["nom"]:
            fields["name"] = row.nom
        if row.type != before["type"]:
            code = LABEL_TO_CODE.get(row.type, "other")
            fields["session_type_manual"] = None if code == auto.get(row.id) else code
        if bool(row.inclure) != bool(before["inclure"]):
            fields["excluded"] = int(not row.inclure)
        if fields:
            repo.update_annotations(common.conn(), int(row.id), **fields)
            changes += 1
    return changes


def _last_sync() -> str:
    value = repo.get_sync_state(common.conn(), garmin.SOURCE).get("last_sync_at")
    if not value:
        return "Jamais synchronisé avec Garmin."
    ts = pd.Timestamp(value).tz_convert(datetime.now().astimezone().tzinfo)
    return f"Dernière synchronisation Garmin le {ts:%d/%m/%Y à %H:%M}."


def render() -> None:
    common.page_header("Sorties", with_types=False)
    c1, c2 = st.columns([1, 2], vertical_alignment="center")
    sync = c1.button("Synchroniser mes nouvelles sorties", type="primary", icon=":material/sync:", width="stretch")
    c2.caption(_last_sync())
    if sync:
        if garmin.get_api_key():
            run_sync()
        else:
            st.warning("Ajoutez d'abord votre clé Garmin dans Réglages, onglet Import et synchronisation.")
            if "settings" in common.PAGES:
                st.page_link(common.PAGES["settings"], label="Ouvrir les réglages", icon=":material/settings:")

    all_df = common.activities()
    if all_df.empty:
        common.empty_state()
        return
    # Excluded runs stay listed so they can be included again.
    df = all_df[all_df["is_trail"]] if common.mode() == "trail" else all_df[~all_df["is_trail"]]
    table = _table(df)
    with st.expander(f"Liste des sorties ({len(df)})", expanded=False):
        st.caption(
            "Corrigez le nom, le type de séance ou la case « Inclure », puis enregistrez. "
            "Vos corrections ne sont jamais écrasées par une nouvelle synchronisation."
        )
        with st.form("activities_form", border=False):
            edited = st.data_editor(
                table,
                hide_index=True,
                width="stretch",
                height=520,
                key="activities_editor",
                disabled=["date", "auto", "raison", "km", "duree", "allure", "cadence", "fc", "dplus"],
                column_config={
                    "id": None,
                    "date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY HH:mm", pinned=True),
                    "nom": st.column_config.TextColumn("Nom", width="medium"),
                    "type": st.column_config.SelectboxColumn(
                        "Type de séance", options=list(SESSION_TYPES.values()), required=True
                    ),
                    "auto": st.column_config.TextColumn("Type auto", help="Classification automatique (règles)."),
                    "raison": st.column_config.TextColumn("Pourquoi", width="medium"),
                    "inclure": st.column_config.CheckboxColumn(
                        "Inclure", help="Décochez pour exclure la sortie de toutes les analyses."
                    ),
                    "km": st.column_config.NumberColumn("Distance", format="%.1f km"),
                    "duree": "Durée",
                    "allure": "Allure",
                    "cadence": st.column_config.NumberColumn(
                        "Cadence", format="%.1f", help="Moyenne hors marche et arrêts"
                    ),
                    "fc": st.column_config.NumberColumn("FC", format="%.0f"),
                    "dplus": st.column_config.NumberColumn("D+", format="%.0f m"),
                },
            )
            submitted = st.form_submit_button("Enregistrer les modifications", type="primary")
        if submitted:
            n = _save(table, edited, df)
            common.invalidate()
            st.toast(f"{n} sortie(s) mise(s) à jour.", icon=":material/check:")
            st.rerun()
