"""F05 — wording of the answers: practical vs statistical significance."""

from cadence_tracker.analysis.questions import monthly_verdict


def test_tiny_but_significant_effect_is_reported_as_stable():
    direction, improving, head = monthly_verdict(-0.03, -0.05, -0.01, "pas/min", good="up")
    assert direction == "flat" and improving is None
    assert head.startswith("Stable") and "par an" in head and "−0,03" in head


def test_meaningful_effects_and_no_effect():
    assert monthly_verdict(0.8, 0.5, 1.1, "pas/min", good="up")[:2] == ("up", True)
    assert monthly_verdict(-0.8, -1.1, -0.5, "bpm", good="down")[:2] == ("down", True)
    assert monthly_verdict(0.2, -0.3, 0.7, "pas/min", good="up")[0] == "flat"
