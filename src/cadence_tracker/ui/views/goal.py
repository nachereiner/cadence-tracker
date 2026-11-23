"""Objectif: where you are, your rhythm, and when you will reach the target.

Spec: docs/specs/F07-objectif-cadence.md
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from cadence_tracker.analysis import cadence_goal, questions, stats
from cadence_tracker.analysis.questions import fr
from cadence_tracker.storage import repository as repo
from cadence_tracker.ui import charts, common, theme


def goal_runs(runs: pd.DataFrame):
    """(runs with cadence_adjusted, status) for the runs taken into account."""
    settings = common.settings()
    ctx = questions.splits_context(common.splits(), runs)
    annotated, b, ref = cadence_goal.annotate(runs, ctx)
    return annotated, cadence_goal.goal_status(annotated, b, ref, settings)


def dashboard_goal() -> tuple[float, float, float] | str | None:
    """Goal lane for the dashboard hero, with the same runs as the Objectif page.

    Returns (baseline, current, target), a short note when the goal exists but
    cannot be placed yet, or None when no goal is set.
    """
    settings = common.settings()
    if not settings.cadence_target_spm:
        return None
    note = f"Objectif {settings.cadence_target_spm:.0f} pas/min : pas assez de sorties récentes pour situer la progression."
    runs = common.in_mode(common.activities())
    if common.mode() == "road":
        types = st.session_state.get("g_types") or settings.natural_session_types
        runs = runs[runs["session_type"].isin(types)]
    if runs.empty:
        return note
    _, status = goal_runs(runs)
    if status.baseline is None or status.current is None:
        return note
    return status.baseline, status.current, status.target


def _goal_form(settings) -> None:
    with st.expander("Définir l'objectif", expanded=settings.cadence_target_spm is None), st.form("goal_form"):
        c1, c2 = st.columns(2)
        target = c1.number_input(
            "Cadence cible (pas/min)", 140.0, 220.0, float(settings.cadence_target_spm or 175.0), 1.0
        )
        start = c2.date_input(
            "Début du travail de cadence",
            value=date.fromisoformat(settings.cadence_goal_start) if settings.cadence_goal_start else date.today(),
            format="DD/MM/YYYY",
        )
        if st.form_submit_button("Enregistrer", type="primary"):
            settings.cadence_target_spm = float(target)
            settings.cadence_goal_start = start.isoformat()
            repo.save_settings(common.conn(), settings)
            common.invalidate()
            st.rerun()


def _month(d: date | None) -> str:
    return common.fr_month(pd.Timestamp(d)) if d else "–"


def render() -> None:
    settings = common.settings()
    df = common.page_header("Objectif cadence", types_key="g_types", types_default=settings.natural_session_types)
    if common.activities().empty:
        common.empty_state()
        return
    _goal_form(settings)
    runs = df.dropna(subset=["cadence_mean"])
    if runs.empty:
        common.no_match()
        return
    runs, status = goal_runs(runs)
    P = common.palette()

    gained = status.current - status.baseline if status.current is not None and status.baseline is not None else None
    if status.reached:
        eta_text = "objectif atteint"
    elif status.eta:
        eta_text = (
            f"entre {_month(status.eta_fast)} et {_month(status.eta_slow)}"
            if status.eta_slow
            else f"au plus tôt {_month(status.eta_fast)}"
        )
    else:
        eta_text = "pas d'échéance à ce rythme"
    theme.stat_row(
        [
            ("Où vous en êtes", theme.fmt(status.current, 1), "pas/min", "médiane des 4 dernières semaines", True),
            ("Point de départ", theme.fmt(status.baseline, 1), "pas/min", theme.delta_html(gained, "pas/min depuis")),
            (
                "Objectif",
                theme.fmt(status.target),
                "pas/min",
                f"{fr(status.progress_pct, 0)} % du chemin" if status.progress_pct is not None else "",
            ),
            (
                "Rythme",
                fr(status.trend.slope_per_month, 1, True) if status.trend else "–",
                "pas/min par mois",
                f"soit {fr(status.trend.slope_per_month * 12, 1, True)} par an" if status.trend else "",
            ),
            (
                "Date estimée",
                _month(status.eta) if status.eta else ("Atteint" if status.reached else "–"),
                "",
                eta_text,
                bool(status.eta),
            ),
        ]
    )
    if status.target and status.baseline is not None and status.current is not None:
        theme.lane_block(status.baseline, status.current, status.target)

    rolling = stats.rolling_mean(runs.sort_values("start_local"), "cadence_adjusted", days=28)
    common.show(charts.goal_projection(runs, rolling, status, P), key="goal_chart")

    trend = status.trend
    if not status.target:
        st.info("Définissez votre cadence cible ci-dessus pour obtenir la projection et la date estimée.")
    elif status.reached:
        st.success(
            "Objectif atteint sur les 4 dernières semaines. Bravo ! Fixez-vous un nouveau palier si vous le souhaitez."
        )
    elif trend is None:
        st.info("Pas encore assez de sorties depuis le début du travail de cadence pour estimer un rythme (6 minimum).")
    elif status.eta:
        st.markdown(
            f"À votre rythme actuel ({fr(trend.slope_per_month, 1, True)} pas/min par mois), vous atteindrez "
            f"**{status.target:.0f} pas/min vers {_month(status.eta)}**. "
            + (
                f"La fourchette va de {_month(status.eta_fast)} à {_month(status.eta_slow)}."
                if status.eta_slow
                else f"Au plus tôt vers {_month(status.eta_fast)} ; la tendance est encore trop incertaine pour une date au plus tard."
            )
        )
    else:
        st.markdown(
            f"À votre rythme actuel ({fr(trend.slope_per_month, 1, True)} pas/min par mois), l'objectif ne sera pas atteint "
            "dans les 3 prochaines années. Il faut accélérer la progression ou revoir la cible."
        )
    scope = (
        "toutes vos sorties trail"
        if common.mode() == "trail"
        else "types de séance choisis, par défaut endurance et sortie longue"
    )
    st.caption(
        f"Calculé sur {status.n_runs} sorties ({scope}). Le rythme est mesuré depuis le début du travail, "
        "et au minimum sur les 12 dernières semaines. Cadence ajustée à l'allure de référence "
        f"{common.pace(1000 / status.reference_speed) if status.reference_speed else '–'} /km "
        f"(+{fr(status.speed_slope)} pas/min par m/s, mesuré dans vos sorties) pour neutraliser l'effet de l'allure."
    )
