"""Compare up to five runs (typically the same route at different dates) on a distance axis.

Spec: docs/specs/F10-comparaison.md
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from cadence_tracker import config
from cadence_tracker.analysis import metrics
from cadence_tracker.storage import repository as repo
from cadence_tracker.ui import charts, common, theme

MAX_RUNS = 5


@st.cache_data(show_spinner=False, max_entries=20)
def _prepared_samples(path: str, activity_id: int, version: tuple, settings_json: str):
    """1 Hz prepared samples of one run (cache key: db, run, data version, settings)."""
    samples = repo.load_samples(common.conn(), activity_id)
    if samples.empty:
        return samples
    return metrics.prepare(samples, config.Settings.from_dict(json.loads(settings_json)))


def load_prepared(activity_id: int) -> pd.DataFrame:
    settings_json = json.dumps(common.settings().to_dict())
    return _prepared_samples(str(config.db_path()), int(activity_id), common.data_version(), settings_json)


def similar_runs(df: pd.DataFrame, ref: pd.Series) -> pd.DataFrame:
    """Runs with a similar distance and the same session type first (no GPS involved)."""
    cand = df[df["id"] != ref["id"]].copy()
    if cand.empty or pd.isna(ref["distance_m"]):
        return cand.iloc[0:0]
    cand["dist_gap"] = (cand["distance_m"] - ref["distance_m"]).abs() / ref["distance_m"]
    cand = cand[cand["dist_gap"] <= 0.15]
    same_type = (cand["session_type"] == ref["session_type"]).astype(int)
    return cand.assign(same_type=same_type).sort_values(["same_type", "dist_gap"], ascending=[False, True])


def _summary(rows: pd.DataFrame) -> pd.DataFrame:
    def num(v, d):
        return theme.fmt(v, d) if pd.notna(v) else "–"

    return pd.DataFrame(
        {
            "Sortie": rows["label"],
            "Distance": rows["distance_km"].map(lambda v: f"{num(v, 2)} km"),
            "Durée": rows["elapsed_s"].map(common.duration),
            "Allure": rows["pace_s_km"].map(lambda v: f"{common.pace(v)} /km"),
            "Cadence": rows["cadence_mean"].map(lambda v: f"{num(v, 1)} pas/min"),
            "FC": rows["hr_mean"].map(lambda v: f"{num(v, 0)} bpm"),
            "Longueur de pas": rows["stride_m"].map(lambda v: f"{num(v, 2)} m"),
            "D+": rows["ascent_m"].map(lambda v: f"{num(v, 0)} m"),
        }
    )


def render() -> None:
    df = common.page_header("Comparer des sorties", with_types=False)
    if common.activities().empty:
        common.empty_state()
        return
    if len(df) < 2:
        common.no_match()
        return
    options = df.sort_values("start_local", ascending=False)
    labels = options.set_index("id")["label"]
    latest = options.iloc[0]
    similar = similar_runs(df, latest)
    default = [int(latest["id"])] + (
        [int(similar["id"].iloc[0])] if not similar.empty else [int(options.iloc[1]["id"])]
    )
    chosen = st.multiselect(
        "Sorties à comparer",
        options["id"].tolist(),
        default=default,
        max_selections=MAX_RUNS,
        format_func=labels.get,
        key=f"cmp_runs_{common.mode()}",
        help="La première sortie sert de référence. Ajoutez jusqu'à 5 sorties.",
    )
    if chosen:
        ref = df.set_index("id").loc[chosen[0]].copy()
        ref["id"] = chosen[0]
        sims = similar_runs(df, ref)
        sims = sims[~sims["id"].isin(chosen)]
        if not sims.empty:
            st.caption(
                f"{len(sims)} sortie(s) de distance proche de la première (±15 %), par exemple : "
                + ", ".join(sims["label"].head(3))
                + "."
            )
    if len(chosen) < 2:
        st.info("Choisissez au moins deux sorties.")
        return
    prepared = [(load_prepared(i), labels[i].split(",")[0]) for i in chosen]
    if any(g.empty for g, _ in prepared):
        st.warning("Séries temporelles manquantes pour l'une des sorties.")
        return
    smoothing = st.slider("Lissage (secondes)", 5, 120, 30, key="cmp_smooth")
    common.show(charts.compare_overlay(prepared, common.palette(), smoothing), key="cmp_chart")
    st.dataframe(_summary(df.set_index("id").loc[chosen].reset_index()), hide_index=True, width="stretch")
