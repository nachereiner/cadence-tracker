"""F06 — session classification rules."""

import pandas as pd

from cadence_tracker.analysis.classification import classify, classify_all, keyword_type
from cadence_tracker.config import Settings

S = Settings()
BASE = {
    "name": "Course à pied",
    "sub_sport": "road",
    "elapsed_s": 3000,
    "running_s": 2900,
    "distance_m": 9000,
    "hr_mean": 140,
    "avg_speed_mps": 3.0,
}


def test_keywords_win_and_are_accent_insensitive():
    assert keyword_type("Fractionné 10x400") == "intervals"
    assert keyword_type("Seuil 3x10'") == "tempo"
    assert keyword_type("FRACTIONNE") == "intervals"
    assert keyword_type("Sortie longue du dimanche") == "long"
    assert keyword_type("EF cadence") == "ef"
    assert keyword_type("Course à pied matinale") is None
    # Training-plan names: intensity words win over the plan name "TRAIL".
    assert keyword_type("Bordeaux - TRAIL-S2-1-Endurance Fondamentale") == "ef"
    assert keyword_type("Bordeaux - TRAIL-S5-2-Seuil 60") == "tempo"
    assert keyword_type("Bordeaux - 21KM-S9-3-Allure 21") == "tempo"
    assert keyword_type("Bordeaux - 21KM-S4-3-Force + Allure 21km") == "tempo"
    assert keyword_type("Bordeaux - Base") == "ef"
    assert keyword_type("Bordeaux Trail") == "trail"


def test_rules_from_data():
    assert classify({**BASE}, S, hr_max=190)[0] == "ef"
    assert classify({**BASE, "sub_sport": "trail"}, S, 190)[0] == "trail"
    assert classify({**BASE, "ascent_per_km": 40}, S, 190)[0] == "trail"
    assert classify({**BASE, "n_active_laps": 8, "n_rest_laps": 7, "active_lap_mean_s": 90}, S, 190)[0] == "intervals"
    assert classify({**BASE, "n_active_laps": 3, "n_rest_laps": 2, "active_lap_mean_s": 600}, S, 190)[0] == "tempo"
    assert classify({**BASE, "hr_mean": 168}, S, 190)[0] == "tempo"
    assert classify({**BASE, "elapsed_s": 6000, "distance_m": 18000}, S, 190)[0] == "long"
    # Variability alone (stops in town) is not enough: repeated fast blocks are required.
    assert classify({**BASE, "speed_cv": 0.25, "fast_blocks": 1}, S, 190)[0] == "ef"
    assert classify({**BASE, "speed_cv": 0.13, "fast_blocks": 8}, S, 190)[0] == "intervals"
    # Strides (15 s accelerations) in an easy run are not intervals.
    assert classify({**BASE, "n_active_laps": 6, "n_rest_laps": 6, "active_lap_mean_s": 15}, S, 190)[0] == "ef"


def test_hr_max_is_estimated_when_not_set():
    df = pd.DataFrame([{**BASE, "id": 1, "hr_peak": 185}, {**BASE, "id": 2, "hr_peak": 175, "hr_mean": 160}])
    result = classify_all(df, S).set_index("id")["session_type_auto"]
    assert result[1] == "ef" and result[2] == "tempo"  # 160/185 = 86 %


def test_missing_names_are_handled():
    assert keyword_type(float("nan"), None) is None
    assert classify({**BASE, "name": float("nan"), "workout_name": None}, S, 190)[0] == "ef"
