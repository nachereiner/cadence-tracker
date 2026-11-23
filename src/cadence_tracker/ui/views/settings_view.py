"""Réglages > Paramètres généraux: analysis thresholds. Saving triggers a recomputation.

Spec: docs/specs/F09-parametres.md
"""

from __future__ import annotations

import streamlit as st

from cadence_tracker.analysis.classification import estimate_hr_max
from cadence_tracker.ingest.pipeline import recompute_all
from cadence_tracker.storage import repository as repo
from cadence_tracker.ui import common


def render_settings() -> None:
    st.caption("Seuils utilisés pour détecter la course, classer les séances et calculer les tendances.")
    s = common.settings()
    df = common.activities()
    estimated = estimate_hr_max(df) if not df.empty else None
    with st.form("settings"):
        st.subheader("Fréquence cardiaque")
        hr_auto = st.checkbox(
            "Estimer la FC max à partir des données",
            value=s.hr_max is None,
            help=f"Estimation actuelle : {estimated:.0f} bpm" if estimated else None,
        )
        hr_max = st.number_input("FC max (bpm)", 140, 230, int(s.hr_max or estimated or 190), disabled=False)

        st.subheader("Détection de la course")
        c1, c2 = st.columns(2)
        min_speed_kmh = c1.number_input(
            "Vitesse minimale de course (km/h)",
            3.0,
            12.0,
            round(s.min_run_speed_mps * 3.6, 1),
            0.1,
            help="En dessous : marche ou arrêt, exclu des statistiques de cadence.",
        )
        min_cad = c2.number_input("Cadence minimale de course (pas/min)", 90, 170, int(s.min_run_cadence_spm))

        st.subheader("Classification automatique")
        c1, c2, c3 = st.columns(3)
        ef_pct = c1.slider("EF : FC moyenne max (% FC max)", 60, 90, int(s.ef_max_hr_pct * 100))
        tempo_pct = c2.slider("Seuil : FC moyenne min (% FC max)", 75, 95, int(s.tempo_min_hr_pct * 100))
        cv = c3.number_input(
            "Fractionné : variabilité d'allure min (CV, hors arrêts)", 0.03, 0.5, float(s.interval_min_speed_cv), 0.01
        )
        blocks = c3.number_input("Fractionné : accélérations min", 1, 30, int(s.interval_min_fast_blocks))
        c1, c2, c3 = st.columns(3)
        long_min = c1.number_input("Sortie longue : durée min (min)", 40, 240, int(s.long_run_min_duration_min))
        long_km = c2.number_input(
            "Sortie longue : distance min (km)", 8.0, 50.0, float(s.long_run_min_distance_km), 0.5
        )
        trail = c3.number_input("Trail : dénivelé min (m/km)", 5.0, 100.0, float(s.trail_min_ascent_m_per_km), 1.0)

        st.subheader("Synchronisation Garmin")
        history = st.text_input(
            "Synchro Garmin complète : ne pas remonter avant (AAAA-MM-JJ, vide = tout)",
            value=s.garmin_history_start or "",
        )

        submitted = st.form_submit_button("Enregistrer et recalculer", type="primary")
    if submitted:
        analysis_changed = (
            round(min_speed_kmh / 3.6, 3) != round(s.min_run_speed_mps, 3) or float(min_cad) != s.min_run_cadence_spm
        )
        s.hr_max = None if hr_auto else int(hr_max)
        s.min_run_speed_mps = round(min_speed_kmh / 3.6, 3)
        s.min_run_cadence_spm = float(min_cad)
        s.ef_max_hr_pct, s.tempo_min_hr_pct = ef_pct / 100, tempo_pct / 100
        s.interval_min_speed_cv = float(cv)
        s.interval_min_fast_blocks = int(blocks)
        s.long_run_min_duration_min, s.long_run_min_distance_km = float(long_min), float(long_km)
        s.trail_min_ascent_m_per_km = float(trail)
        s.garmin_history_start = history.strip() or None
        repo.save_settings(common.conn(), s)
        with st.spinner("Recalcul des métriques…" if analysis_changed else "Reclassification…"):
            if analysis_changed:
                recompute_all(common.conn())
            else:
                from cadence_tracker.ingest.pipeline import reclassify

                reclassify(common.conn())
        common.invalidate()
        st.toast("Paramètres enregistrés.", icon=":material/check:")
        st.rerun()
