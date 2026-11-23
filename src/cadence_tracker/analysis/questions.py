"""The six key questions of the project, answered from the data.

Each function returns a `QuestionResult` with a one-sentence answer, the method
used, and the statistical object behind it. The UI renders them in
"Corrélations > Questions clés". See docs/specs/F05-correlations.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from cadence_tracker.analysis import stats
from cadence_tracker.analysis.stats import AdjustedEffect, Trend


@dataclass
class QuestionResult:
    key: str
    question: str
    verdict: str  # 'up' | 'down' | 'flat' | 'insufficient'
    improving: bool | None  # does the observed direction mean progress?
    headline: str
    method: str
    effect: Trend | AdjustedEffect | tuple | None = None
    data: pd.DataFrame | None = None  # rows the answer is computed from (for charts)


def fr(value: float | None, decimals: int = 1, signed: bool = False) -> str:
    """French number formatting: 1.25 -> '1,3' (signed: '+1,3')."""
    if value is None or pd.isna(value):
        return "–"
    text = f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"
    return text.replace(".", ",").replace("-", "−")


def _ci(low: float, high: float, decimals: int = 1) -> str:
    return f"IC 95 % : {fr(low, decimals, True)} à {fr(high, decimals, True)}"


# Smallest change per month that matters in practice. A statistically detectable
# effect below it is reported as "stable" (long histories make tiny effects
# significant). Cadence: 0.1 steps/min per month = 1.2 per year.
NEGLIGIBLE_PER_MONTH = {"pas/min": 0.1, "s/km": 1.0, "bpm": 0.1}


def monthly_verdict(coef: float, lo: float, hi: float, unit: str, good: str) -> tuple[str, bool | None, str]:
    """(direction, improving, headline) for an effect expressed per month."""
    margin = NEGLIGIBLE_PER_MONTH.get(unit, 0.0)
    d = 2 if max(abs(coef), abs(hi - lo) / 2) < 0.15 else 1
    value = f"{fr(coef, d, True)} {unit} par mois, soit {fr(coef * 12, 1, True)} par an"
    ci = _ci(lo, hi, d)
    significant = lo > 0 or hi < 0
    if significant and max(abs(lo), abs(hi)) < margin:
        return "flat", None, f"Stable : {value} ({ci}). L'évolution est mesurable mais négligeable."
    if not significant:
        return "flat", None, f"Pas d'évolution nette : {value}, compatible avec zéro ({ci})."
    direction = "up" if lo > 0 else "down"
    verb = "Oui" if direction == good else "Non"
    return direction, direction == good, f"{verb} : {value} ({ci})."


def splits_context(splits: pd.DataFrame, activities: pd.DataFrame) -> pd.DataFrame:
    """Kilometre splits joined with their activity context (date, type, terrain)."""
    if splits.empty or activities.empty:
        return pd.DataFrame()
    ctx = activities[["id", "start_local", "session_type", "sub_sport"]].rename(columns={"id": "activity_id"})
    df = splits.merge(ctx, on="activity_id", how="inner")
    df["t_months"] = stats.months_since(df["start_local"], activities["start_local"].min())
    df["pace_s_km"] = 1000 / df["speed_mps"]
    df["elapsed_h"] = df["elapsed_end_s"] / 3600
    return df[(df["distance_m"] >= 500) & df["speed_mps"].between(1.5, 7)]


def _insufficient(key, question, n, needed) -> QuestionResult:
    return QuestionResult(
        key,
        question,
        "insufficient",
        None,
        f"Pas assez de données pour conclure ({n} disponibles, {needed} nécessaires).",
        "",
    )


def q_cadence_trend(acts: pd.DataFrame) -> QuestionResult:
    key, question = "trend", "Ma cadence augmente-t-elle au fil des semaines ?"
    trend = stats.linear_trend(acts["start_local"], acts["cadence_mean"]) if not acts.empty else None
    if trend is None:
        return _insufficient(key, question, len(acts), 6)
    direction, improving, head = monthly_verdict(
        trend.slope_per_month, trend.ci_low, trend.ci_high, "pas/min", good="up"
    )
    method = (
        f"Régression linéaire de la cadence moyenne de chaque sortie (hors marche et arrêts) sur la date ({trend.n} sorties). "
        "Tendance brute : elle mélange l'effet du temps et celui des allures et des séances choisies."
    )
    return QuestionResult(key, question, direction, improving, head, method, trend, acts)


def _adjusted_question(
    key, question, ctx, outcome, controls, unit, decimals, good_direction, method_intro
) -> QuestionResult:
    if ctx.empty:
        return _insufficient(key, question, 0, 15)
    effect = stats.adjusted_effect(
        ctx, outcome, "t_months", controls, categorical=["session_type"], cluster="activity_id"
    )
    if effect is None:
        return _insufficient(key, question, len(ctx), 15)
    direction, improving, head = monthly_verdict(effect.coef, effect.ci_low, effect.ci_high, unit, good_direction)
    method = (
        f"{method_intro} Unité d'analyse : le kilomètre ({effect.n} km issus de {effect.n_groups} sorties, "
        f"erreurs standard groupées par sortie). Variables de contrôle : {', '.join(effect.controls) or 'aucune'}. "
        "Il s'agit d'une association, pas d'une preuve de causalité."
    )
    return QuestionResult(key, question, direction, improving, head, method, effect, ctx)


def q_cadence_same_pace(ctx: pd.DataFrame) -> QuestionResult:
    outdoor = ctx[ctx["sub_sport"] != "treadmill"] if not ctx.empty else ctx
    return _adjusted_question(
        "same_pace",
        "À allure équivalente, ma cadence augmente-t-elle ?",
        outdoor,
        "cadence_spm",
        ["speed_mps", "grade_pct"],
        "pas/min",
        1,
        "up",
        "Cadence par km expliquée par le temps, à vitesse, pente et type de séance égaux (tapis exclu).",
    )


def q_pace_same_cadence(ctx: pd.DataFrame) -> QuestionResult:
    outdoor = ctx[ctx["sub_sport"] != "treadmill"] if not ctx.empty else ctx
    return _adjusted_question(
        "same_cadence",
        "À cadence équivalente, mon allure s'améliore-t-elle ?",
        outdoor,
        "pace_s_km",
        ["cadence_spm", "grade_pct"],
        "s/km",
        1,
        "down",
        "Allure par km (s/km, plus bas = plus rapide) expliquée par le temps, à cadence, pente et type de séance égaux. "
        "À lire avec la question précédente : si la cadence augmente à allure égale, il est attendu qu'à cadence égale "
        "l'allure soit plus lente (foulée plus courte) — ce n'est pas une baisse de forme.",
    )


def q_hr_same_pace(ctx: pd.DataFrame) -> QuestionResult:
    steady = (
        ctx[ctx["session_type"].isin(["ef", "long", "tempo"]) & (ctx["sub_sport"] != "treadmill")]
        if not ctx.empty
        else ctx
    )
    steady = steady.dropna(subset=["heart_rate"]) if not steady.empty else steady
    return _adjusted_question(
        "hr_same_pace",
        "À allure et conditions comparables, ma fréquence cardiaque diminue-t-elle ?",
        steady,
        "heart_rate",
        ["speed_mps", "grade_pct", "elapsed_h"],
        "bpm",
        1,
        "down",
        "FC par km expliquée par le temps, à vitesse, pente, durée écoulée (dérive cardiaque) et type de séance égaux "
        "(séances continues uniquement : EF, sortie longue, seuil).",
    )


def q_long_run_stability(acts: pd.DataFrame) -> QuestionResult:
    key, question = "long_stability", "Ma cadence reste-t-elle stable pendant une sortie longue ?"
    longs = acts[(acts["session_type"] == "long") | (acts["running_s"] >= 3600)] if not acts.empty else acts
    res = stats.mean_ci(longs["cadence_drift_spm_h"]) if not longs.empty else None
    if res is None:
        return _insufficient(key, question, len(longs), 3)
    mean, lo, hi, n = res
    stable = (lo <= 0 <= hi) or abs(mean) < 1.5
    if stable:
        head = f"Oui, globalement stable : {fr(mean, signed=True)} pas/min par heure en moyenne ({_ci(lo, hi)})."
        verdict = "flat"
    else:
        verdict = "down" if mean < 0 else "up"
        head = f"{'Non, elle baisse' if mean < 0 else 'Elle augmente'} : {fr(mean, signed=True)} pas/min par heure ({_ci(lo, hi)})."
    method = (
        f"Pente de la cadence (moyennes par minute, hors 5 premières minutes) au cours de {n} sorties "
        "d'au moins 1 h ou classées « sortie longue ». Effet brut : inclut les variations d'allure."
    )
    return QuestionResult(key, question, verdict, True if stable else mean > 0, head, method, res, longs)


def q_fatigue(acts: pd.DataFrame) -> QuestionResult:
    key, question = "fatigue", "Ma cadence diminue-t-elle avec la fatigue ?"
    steady = (
        acts[acts["session_type"].isin(["ef", "long", "tempo"]) & (acts["running_s"] >= 2400)]
        if not acts.empty
        else acts
    )
    res = stats.mean_ci(steady["cadence_fatigue_spm_h"]) if not steady.empty else None
    if res is None:
        return _insufficient(key, question, len(steady), 3)
    mean, lo, hi, n = res
    if hi < 0:
        verdict, head = (
            "down",
            f"Oui : à allure constante, elle baisse de {fr(-mean)} pas/min par heure de course ({_ci(lo, hi)}).",
        )
    elif lo > 0:
        verdict, head = (
            "up",
            f"Non, elle augmente même : {fr(mean, signed=True)} pas/min par heure à allure constante ({_ci(lo, hi)}).",
        )
    else:
        verdict, head = (
            "flat",
            f"Pas de baisse nette : {fr(mean, signed=True)} pas/min par heure à allure constante ({_ci(lo, hi)}).",
        )
    method = (
        f"Pour chacune des {n} séances continues de plus de 40 min, régression de la cadence (par minute) sur le temps "
        "écoulé en contrôlant la vitesse ; on rapporte la moyenne des pentes."
    )
    return QuestionResult(key, question, verdict, verdict != "down", head, method, res, steady)


def all_questions(acts: pd.DataFrame, splits: pd.DataFrame) -> list[QuestionResult]:
    ctx = splits_context(splits, acts)
    return [
        q_cadence_trend(acts),
        q_cadence_same_pace(ctx),
        q_pace_same_cadence(ctx),
        q_hr_same_pace(ctx),
        q_long_run_stability(acts),
        q_fatigue(acts),
    ]
