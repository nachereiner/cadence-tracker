"""Correlation analysis: the six key questions of the project.

Spec: docs/specs/F05-correlations.md
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cadence_tracker.analysis import questions, stats
from cadence_tracker.analysis.questions import fr
from cadence_tracker.ui import charts, common

BADGES = {
    True: ("Progrès", "green", ":material/trending_up:"),
    False: ("À surveiller", "orange", ":material/trending_down:"),
    None: ("Stable", "gray", ":material/trending_flat:"),
}


def _question_chart(q: questions.QuestionResult, P: dict):
    d = q.data
    if d is None or d.empty:
        return None
    if q.key == "trend":
        data = d.dropna(subset=["cadence_mean"]).sort_values("start_local")
        return charts.runs_over_time(data, "cadence_mean", P, stats.rolling_mean(data, "cadence_mean"), q.effect)
    if q.key == "same_pace":
        return charts.scatter_by_period(
            d, "pace_s_km", "cadence_spm", P, "Allure du km (min/km)", "Cadence (pas/min)", pace_x=True, height=380
        )
    if q.key == "same_cadence":
        return charts.scatter_by_period(
            d, "cadence_spm", "pace_s_km", P, "Cadence (pas/min)", "Allure du km (min/km)", pace_y=True, height=380
        )
    if q.key == "hr_same_pace":
        return charts.scatter_by_period(
            d, "pace_s_km", "heart_rate", P, "Allure du km (min/km)", "FC (bpm)", pace_x=True, height=380
        )
    if q.key == "long_stability":
        return charts.value_over_time_with_zero(d, "cadence_drift_spm_h", P, "Dérive (pas/min par heure)")
    if q.key == "fatigue":
        return charts.value_over_time_with_zero(d, "cadence_fatigue_spm_h", P, "Effet fatigue (pas/min par heure)")
    return None


CHART_HINTS = {
    "same_pace": "Chaque point est un kilomètre, coloré par période (du plus clair au plus foncé = du plus ancien au plus récent). "
    "Si les droites récentes sont au-dessus des anciennes, la cadence a augmenté à allure égale.",
    "same_cadence": "Chaque point est un kilomètre. Droites plus hautes = allure plus rapide à cadence égale.",
    "hr_same_pace": "Chaque point est un kilomètre de séance continue. Droites récentes plus basses = FC plus basse à allure égale.",
    "long_stability": "Chaque point est une sortie longue ; sous zéro, la cadence baisse au fil de la sortie.",
    "fatigue": "Chaque point est une séance continue ; sous zéro, la cadence baisse à allure constante au fil de la sortie.",
}


def _questions_tab(df: pd.DataFrame, P: dict) -> None:
    sp = common.splits()
    sp = sp[sp["activity_id"].isin(df["id"])]
    results = questions.all_questions(df, sp)
    st.caption(
        "Réponses calculées sur les sorties sélectionnées par les filtres. Les effets « à allure équivalente » sont estimés par "
        "régression multiple : ils neutralisent l'allure, la pente et le type de séance, mais restent des associations "
        "(météo, fatigue, terrain non mesurés…)."
    )
    for q in results:
        with st.container(border=True):
            head, badge_col = st.columns([5, 1], vertical_alignment="center")
            head.markdown(f"#### {q.question}")
            if q.verdict == "insufficient":
                badge_col.badge("Données insuffisantes", color="gray", icon=":material/hourglass_empty:")
            elif q.verdict == "flat" and q.improving:
                badge_col.badge("Stable", color="green", icon=":material/check:")
            else:
                label, color, icon = BADGES[q.improving]
                badge_col.badge(label, color=color, icon=icon)
            st.markdown(f"**{q.headline}**")
            fig = _question_chart(q, P)
            if fig is not None:
                if q.key in CHART_HINTS:
                    st.caption(CHART_HINTS[q.key])
                common.show(fig, key=f"q_{q.key}")
            if q.method:
                with st.expander("Méthode et limites"):
                    st.write(q.method)
                    effect = q.effect
                    if isinstance(effect, stats.AdjustedEffect):
                        st.code(effect.formula, language=None)
                        st.write(f"R² = {fr(effect.r2, 2)} · p = {effect.p_value:.3g}")
                        coefs = pd.DataFrame({"Coefficient": effect.coefficients}).rename_axis("Variable")
                        st.dataframe(
                            coefs,
                            width="stretch",
                            column_config={"Coefficient": st.column_config.NumberColumn(format="%.3f")},
                        )
                    elif isinstance(effect, stats.Trend):
                        st.write(f"R² = {fr(effect.r2, 2)} · p = {effect.p_value:.3g} · n = {effect.n}")


def render() -> None:
    df = common.page_header("Corrélations")
    if common.activities().empty:
        common.empty_state()
        return
    if df.empty:
        common.no_match()
        return
    ranged = common.date_range(df, "Période analysée")
    _questions_tab(ranged, common.palette())
