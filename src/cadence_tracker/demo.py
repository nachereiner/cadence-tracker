"""Synthetic training history, to explore the app before connecting real data.

Data are generated with a simple physiological model so that every screen has
something meaningful to show (and so that tests can check that the analyses
recover known effects):

* natural cadence at 2.85 m/s rises slowly (+0.3 steps/min/month), then faster
  once cadence-focus sessions start (+0.8 more per month);
* cadence increases with speed (+9 steps/min per m/s) and fades with fatigue;
* heart rate at a given speed decreases by ~0.8 bpm/month (fitness);
* the mix of sessions (EF, long, threshold, intervals, trail, treadmill) varies.

Demo data go to a separate database (`data/demo.db`), never to the real one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd

from cadence_tracker.models import LAP_COLUMNS, SAMPLE_COLUMNS, ParsedActivity

REF_SPEED = 2.85


def _natural_cadence(months: float, focus_start: float) -> float:
    return 163.0 + 0.3 * months + 0.8 * max(0.0, months - focus_start)


def _speed_profile(kind: str, rng: np.random.Generator, base: float) -> tuple[np.ndarray, list[tuple[int, int, str]]]:
    """Per-second target speed and laps (start_s, end_s, intensity)."""
    laps: list[tuple[int, int, str]] = []

    def seg(duration: int, speed: float, intensity: str = "active") -> np.ndarray:
        start = sum(len(p) for p in parts)
        laps.append((start, start + duration, intensity))
        return np.full(duration, speed)

    parts: list[np.ndarray] = []
    if kind in {"ef", "focus", "treadmill"}:
        parts.append(seg(int(rng.integers(38, 62)) * 60, base))
    elif kind == "long":
        parts.append(seg(int(rng.integers(85, 125)) * 60, base - 0.1))
    elif kind == "trail":
        parts.append(seg(int(rng.integers(60, 100)) * 60, base - 0.35))
    elif kind == "tempo":
        parts.append(seg(15 * 60, base, "warmup"))
        for i in range(3):
            parts.append(seg(10 * 60, base + 0.8))
            if i < 2:
                parts.append(seg(2 * 60, base - 0.3, "recovery"))
        parts.append(seg(10 * 60, base - 0.1, "cooldown"))
    elif kind == "intervals":
        parts.append(seg(15 * 60, base, "warmup"))
        reps = int(rng.integers(8, 11))
        for i in range(reps):
            parts.append(seg(90, base + 1.6))
            if i < reps - 1:
                parts.append(seg(90, base - 0.6, "rest"))
        parts.append(seg(10 * 60, base - 0.1, "cooldown"))
    return np.concatenate(parts), laps


def _activity(
    kind: str, start: datetime, months: float, focus_start: float, rng: np.random.Generator, index: int
) -> ParsedActivity:
    base = REF_SPEED + rng.normal(0, 0.08) + 0.012 * months
    target, laps = _speed_profile(kind, rng, base)
    n = len(target)
    t = np.arange(n)

    # Smooth speed with noise, a few short stops (traffic lights / walk breaks).
    noise = np.convolve(rng.normal(0, 0.12, n), np.ones(15) / 15, mode="same")
    speed = np.convolve(target, np.ones(12) / 12, mode="same") + noise
    if kind in {"long", "trail", "ef"}:
        for _ in range(int(rng.integers(0, 3))):
            s = int(rng.integers(300, max(301, n - 300)))
            speed[s : s + int(rng.integers(15, 60))] = rng.uniform(0.0, 0.3)

    # Terrain: altitude as a function of distance.
    dist = np.cumsum(np.clip(speed, 0, None))
    if kind == "trail":
        altitude = 420 + 110 * np.sin(2 * np.pi * dist / 5200) + 35 * np.sin(2 * np.pi * dist / 1300 + 1)
    elif kind == "treadmill":
        altitude = np.full(n, 170.0)
    else:
        altitude = 170 + 7 * np.sin(2 * np.pi * dist / 2600) + 4 * np.sin(2 * np.pi * dist / 850)
    grade = np.gradient(altitude) / np.maximum(np.clip(speed, 0.3, None), 0.3) * 100
    grade = np.convolve(grade, np.ones(20) / 20, mode="same")
    moving = speed > 0.5
    speed = np.where(moving, speed / (1 + 0.035 * np.clip(grade, -5, 25)), speed)
    dist = np.cumsum(np.clip(speed, 0, None))

    # Cadence: natural level + speed effect + grade + fatigue + noise.
    natural = _natural_cadence(months, focus_start)
    if kind == "focus":
        natural = max(natural + 3.0, 173.0 + 0.25 * (months - focus_start))
    fatigue = (2.6 - 0.15 * months) * t / 3600
    cadence = natural + 9.0 * (speed - REF_SPEED) + 0.25 * np.clip(grade, -10, 15) - fatigue
    cadence += np.convolve(rng.normal(0, 3.0, n), np.ones(5) / 5, mode="same")
    cadence = np.where(moving, cadence, 0.0)

    # Heart rate: steady-state from speed and grade, first-order lag, drift, fitness.
    hr_target = 70 + 26 * np.clip(speed, 0, None) + 1.1 * np.clip(grade, -5, 20) - 0.8 * months + 4.0 * t / 3600
    hr = np.empty(n)
    hr[0] = 95
    for i in range(1, n):
        hr[i] = hr[i - 1] + (hr_target[i] - hr[i - 1]) / 25
    hr += rng.normal(0, 1.0, n)

    samples = pd.DataFrame(
        {
            "t_s": t,
            "distance_m": dist,
            "speed_mps": np.clip(speed, 0, None),
            "cadence_raw": cadence / 2,  # FIT-like strides per minute
            "heart_rate": np.round(hr),
            "altitude_m": altitude + rng.normal(0, 0.3, n),
        }
    )
    if index % 5 == 0:  # mimic Garmin "smart recording" (irregular sampling)
        keep = np.cumsum(rng.integers(1, 5, n)) - 1
        samples = samples.iloc[keep[keep < n]].reset_index(drop=True)
    samples = samples.reindex(columns=SAMPLE_COLUMNS)

    lap_rows = []
    if kind in {"tempo", "intervals"}:
        for i, (a, b, intensity) in enumerate(laps):
            lap_rows.append(
                {
                    "lap_index": i,
                    "start_s": a,
                    "duration_s": b - a,
                    "distance_m": float(dist[min(b, n) - 1] - (dist[a - 1] if a else 0)),
                    "speed_mps": float(speed[a:b].mean()),
                    "heart_rate": float(hr[a:b].mean()),
                    "cadence_spm": float(cadence[a:b].mean()),
                    "intensity": intensity,
                }
            )
    names = {
        "ef": ["Footing", "EF", "Course à pied matinale", "Course à pied du soir"],
        "focus": ["EF cadence", "Course à pied matinale"],
        "long": ["Sortie longue", "Course à pied matinale"],
        "tempo": ["Seuil 3x10'", "Tempo", "Course à pied du soir"],
        "intervals": ["Fractionné 10x90''", "VMA courte", "Course à pied du soir"],
        "trail": ["Trail", "Course à pied - Monts"],
        "treadmill": ["Tapis", "Course à pied en salle"],
    }[kind]
    return ParsedActivity(
        source="demo",
        source_id=f"demo-{index}",
        start_time_utc=start,
        sport="running",
        sub_sport={"trail": "trail", "treadmill": "treadmill"}.get(kind, "road"),
        cadence_unit="strides",
        samples=samples,
        laps=pd.DataFrame(lap_rows, columns=LAP_COLUMNS) if lap_rows else None,
        utc_offset_s=3600,
        name=str(rng.choice(names)),
        device="Montre de démonstration",
    )


def generate(weeks: int = 36, seed: int = 7, end: date | None = None) -> list[ParsedActivity]:
    rng = np.random.default_rng(seed)
    end = end or date.today()
    first_monday = end - timedelta(days=end.weekday()) - timedelta(weeks=weeks - 1)
    focus_start = 2.3  # months after the beginning
    activities: list[ParsedActivity] = []
    last_focus: date | None = None
    for week in range(weeks):
        monday = first_monday + timedelta(weeks=week)
        plan = ["ef", "tempo" if week % 2 else "intervals", "ef", "long"]
        if week % 3 == 2:
            plan[2] = "trail"
        if week % 4 == 1:
            plan.append("ef")
        if week % 7 == 3:
            plan[0] = "treadmill"
        days = sorted(rng.choice([0, 1, 2, 3, 4], size=len(plan) - 1, replace=False).tolist()) + [
            int(rng.choice([5, 6]))
        ]
        for kind, offset in zip(plan, days, strict=False):
            day = monday + timedelta(days=int(offset))
            if day > end:
                continue
            months = (day - first_monday).days / 30.44
            if kind == "ef" and months >= focus_start and (last_focus is None or (day - last_focus).days >= 9):
                kind, last_focus = "focus", day
            hour = int(rng.choice([7, 12, 18]))
            start = datetime(day.year, day.month, day.day, hour - 1, int(rng.integers(0, 50)), tzinfo=UTC)
            activities.append(_activity(kind, start, months, focus_start, rng, len(activities)))
    return activities
