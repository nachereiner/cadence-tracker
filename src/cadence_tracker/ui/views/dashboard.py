"""Dashboard: the race-clock KPIs and the central evolution chart.

Spec: docs/specs/F04-tableau-de-bord.md
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cadence_tracker.analysis import economy, questions, stats
from cadence_tracker.analysis.questions import fr
from cadence_tracker.ui import charts, common, theme
from cadence_tracker.ui.views.goal import dashboard_goal

SHORT_LABELS = {
    "cadence_mean": "Cadence",
    "pace_s_km": "Allure",
    "hr_mean": "FC",
    "stride_m": "Longueur de pas",
    "hr_ref": "FC à allure égale",
    "efficiency": "Efficacité brute",
}
GRANULARITIES = {"day": "Jour", "week": "Semaine", "month": "Mois", "year": "Année"}


def _weekly_cadence(df: pd.DataFrame) -> pd.DataFrame:
    week = df["start_local"].dt.to_period("W-SUN").dt.start_time
    out = df.assign(week=week).groupby("week").apply(lambda g: stats.weighted_mean(g["cadence_mean"], g["running_s"]))
    full = pd.date_range(out.index.min(), out.index.max(), freq="7D")
    return out.reindex(full).rename_axis("week").reset_index(name="cadence")


def _scoreboard(df: pd.DataFrame) -> None:
    """Race-clock hero (cadence) and three quiet tiles (pace, heart rate, volume)."""
    cad_now, _, cad_delta = stats.window_compare(df, "cadence_mean", stat="wmean")
    spd_now, spd_prev, _ = stats.window_compare(df, "avg_speed_mps", stat="mean")
    hr_now, _, hr_delta = stats.window_compare(df, "hr_mean", stat="mean")
    last4 = df[df["start_local"] > df["start_local"].max() - pd.Timedelta(days=28)]
    pace_delta = (1000 / spd_now - 1000 / spd_prev) if spd_now and spd_prev else None
    weekly = _weekly_cadence(df).tail(12)
    n = len(last4)
    theme.scoreboard(
        cadence=cad_now,
        cadence_delta=cad_delta,
        weekly=weekly["cadence"].tolist(),
        weekly_labels=[f"Semaine du {w:%d/%m}" for w in weekly["week"]],
        goal=dashboard_goal(),
        tiles=[
            (
                "Allure moyenne",
                common.pace(1000 / spd_now if spd_now else None),
                "/km",
                theme.delta_html(pace_delta, "s/km", good_when="down", decimals=0),
            ),
            ("FC moyenne", theme.fmt(hr_now), "bpm", theme.delta_html(hr_delta, "bpm", good_when="down")),
            (
                "Volume",
                theme.fmt(last4["distance_km"].sum()),
                "km",
                f"{n} sortie{'s' if n > 1 else ''} en {common.duration(last4['elapsed_s'].sum())}",
            ),
        ],
    )


def _add_hr_at_reference(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Heart rate brought back to a reference pace on flat ground (see analysis/economy.py)."""
    everything = common.activities()
    everything = everything[~everything["excluded"]]
    ctx = questions.splits_context(common.splits(), everything)
    road_easy = everything[(everything["sub_sport"] == "road") & everything["session_type"].isin(["ef", "long"])]
    ref_speed = road_easy["avg_speed_mps"].median()
    if pd.isna(ref_speed) or ctx.empty:
        return df.assign(hr_ref=pd.NA), None
    ref_pace = round(1000 / ref_speed / 5) * 5  # round to 5 s/km
    model = economy.fit_hr_model(ctx, ref_speed=1000 / ref_pace)
    if model is None:
        return df.assign(hr_ref=pd.NA), None
    hr = economy.hr_at_reference(ctx, model)
    # Continuous efforts only: bringing interval or threshold reps back to an easy
    # pace would extrapolate the HR/speed relation far outside its linear range.
    steady = df["session_type"].isin(["ef", "long", "other", "trail"]) & (df["sub_sport"] != "treadmill")
    return df.assign(hr_ref=df["id"].map(hr).astype(float).where(steady)), common.pace(ref_pace)


def render() -> None:
    df = common.page_header("Tableau de bord")
    if common.activities().empty:
        common.empty_state()
        return
    if df.empty:
        common.no_match()
        return
    P = common.palette()
    _scoreboard(df)

    st.subheader("Évolution")
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    metric = (
        c1.segmented_control(
            "Indicateur",
            list(SHORT_LABELS),
            default="cadence_mean",
            key="dash_metric",
            persist_state="session",
            format_func=SHORT_LABELS.get,
            label_visibility="collapsed",
        )
        or "cadence_mean"
    )
    granularity = (
        c2.segmented_control(
            "Regrouper par",
            list(GRANULARITIES),
            default="month",
            key="dash_gran",
            persist_state="session",
            format_func=GRANULARITIES.get,
            label_visibility="collapsed",
            width="stretch",
        )
        or "month"
    )
    ref_pace = None
    if metric == "hr_ref":
        df, ref_pace = _add_hr_at_reference(df)

    chart = st.container()
    ranged = common.date_range(df, "Période affichée")
    data = ranged.dropna(subset=[metric]).sort_values("start_local")
    table = stats.aggregate_by_period(ranged, granularity)
    rolling = stats.rolling_mean(data, metric, days=28)
    trend = stats.linear_trend(data["start_local"], data[metric])
    target = common.settings().cadence_target_spm if metric == "cadence_mean" else None
    with chart:
        common.show(charts.evolution(data, table, metric, granularity, P, rolling, trend, target), key="dash_chart")

    left, right = st.columns([2, 1])
    with left:
        label, unit, is_pace = charts.METRICS[metric]
        if trend is None:
            st.caption("Tendance : pas assez de sorties sur la période (6 minimum).")
        else:
            unit_txt = "s/km" if is_pace else unit
            if unit_txt in questions.NEGLIGIBLE_PER_MONTH:
                # Same wording as the questions page: negligible effects are "stable".
                direction, _, sentence = questions.monthly_verdict(
                    trend.slope_per_month, trend.ci_low, trend.ci_high, unit_txt, good="up"
                )
                rest = sentence.partition(" : ")[2].rstrip(".")
                if sentence.startswith("Stable"):
                    head = "Stable"
                elif direction == "flat":
                    head = "Pas de tendance nette"
                elif is_pace:
                    head = "Plus lente" if direction == "up" else "Plus rapide"
                else:
                    head = "En hausse" if direction == "up" else "En baisse"
                st.markdown(f"**{head}** : {rest}, sur {trend.n} sorties {common.range_caption(data)}.")
            else:
                verdict = {"up": "En hausse", "down": "En baisse", "flat": "Pas de tendance nette"}[trend.direction]
                d = 2 if unit == "m" or abs(trend.slope_per_month) < 0.15 else 1
                st.markdown(
                    f"**{verdict}** : {fr(trend.slope_per_month, d, True)} {unit_txt} par mois sur {trend.n} sorties "
                    f"{common.range_caption(data)} (IC 95 % : {fr(trend.ci_low, d, True)} à {fr(trend.ci_high, d, True)})."
                )
        if metric == "hr_ref":
            st.caption(
                f"FC de chaque sortie continue ramenée à {ref_pace} /km sur le plat (hors premier km), d'après la relation "
                "FC/vitesse/pente mesurée dans vos sorties. Plus bas = meilleure économie de course."
            )
        elif metric == "efficiency":
            st.caption(
                "Efficacité brute = vitesse / FC. Elle baisse quand vous courez plus lentement ou en terrain vallonné, "
                "même à forme égale : pour suivre votre forme, préférez « FC à allure égale »."
            )
        st.caption(
            "Survolez une période pour son détail (sorties, volume, cadence, allure, FC). Tendance brute : pour isoler "
            "l'effet du temps à allure égale, voir la page Corrélations."
        )
    with right:
        mix = ranged.groupby("type_label").agg(Sorties=("id", "size"))
        mix["Cadence"] = ranged.groupby("type_label").apply(
            lambda g: stats.weighted_mean(g["cadence_mean"], g["running_s"])
        )
        st.dataframe(
            mix.sort_values("Sorties", ascending=False).rename_axis("Type de séance"),
            width="stretch",
            column_config={
                "Cadence": st.column_config.NumberColumn("Cadence", format="%.1f", help="Cadence moyenne (hors marche)")
            },
        )
