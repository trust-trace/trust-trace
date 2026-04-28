from eem._pipeline import _compute_score


def test_empty_impacts_returns_neutral():
    score, risk, trend, history, keywords = _compute_score([], [], [])
    assert score == 50
    assert risk == "medium"
    assert trend == 0
    assert history == [50]
    assert keywords == []


def test_severe_negative_impact():
    # impact=-8.4 → clamp(50 - 42, 0, 100) = 8
    score, risk, _, _, _ = _compute_score([-8.4], [], [])
    assert score == 8
    assert risk == "high"


def test_mild_positive_impact():
    # impact=2.1 → 50 + 10.5 = 60.5 → round() = 60 (banker's rounding, rounds to even)
    score, risk, _, _, _ = _compute_score([2.1], [], [])
    assert score == 60
    assert risk == "medium"


def test_neutral_impact():
    score, risk, _, _, _ = _compute_score([0.0], [], [])
    assert score == 50
    assert risk == "medium"


def test_strong_positive_impact():
    # impact=7.0 → clamp(50 + 35, 0, 100) = 85
    score, risk, _, _, _ = _compute_score([7.0], [], [])
    assert score == 85
    assert risk == "low"


def test_impact_clamped_above():
    # impact=20 → clamp(50 + 100, 0, 100) = 100
    score, _, _, _, _ = _compute_score([20.0], [], [])
    assert score == 100


def test_impact_clamped_below():
    # impact=-20 → clamp(50 - 100, 0, 100) = 0
    score, _, _, _, _ = _compute_score([-20.0], [], [])
    assert score == 0


def test_average_of_multiple_events():
    # (-8.4 → 8) and (2.1 → 61) → mean = 34 (rounded)
    score, risk, _, _, _ = _compute_score([-8.4, 2.1], [], [])
    assert score == round((8 + 61) / 2)
    assert risk == "high"


def test_trend_computed_correctly():
    prev = [60]
    score, _, trend, _, _ = _compute_score([0.0], prev, [])  # score = 50
    assert trend == 50 - 60  # -10


def test_trend_zero_when_no_history():
    _, _, trend, _, _ = _compute_score([0.0], [], [])
    assert trend == 0


def test_history_appended():
    prev = [70, 65]
    _, _, _, history, _ = _compute_score([0.0], prev, [])
    assert history == [70, 65, 50]


def test_history_capped_at_12():
    prev = list(range(12))  # already 12 values
    _, _, _, history, _ = _compute_score([0.0], prev, [])
    assert len(history) == 12
    assert history[-1] == 50
    assert history[0] == 1  # oldest dropped


def test_keyword_frequency_order():
    kws = [["korupcja", "CBA"], ["korupcja", "zarząd"], ["CBA"]]
    _, _, _, _, top_kw = _compute_score([0.0, 0.0, 0.0], [], kws)
    assert top_kw[0] == "korupcja"  # appears 2x
    assert "CBA" in top_kw


def test_keyword_capped_at_6():
    kws = [["a", "b", "c", "d", "e", "f", "g"]]
    _, _, _, _, top_kw = _compute_score([0.0], [], kws)
    assert len(top_kw) <= 6


def test_risk_boundary_high():
    # score=40 → high
    score, risk, _, _, _ = _compute_score([-2.0], [], [])  # 50-10=40
    assert score == 40
    assert risk == "high"


def test_risk_boundary_medium():
    # score=41 → medium
    score, risk, _, _, _ = _compute_score([-1.8], [], [])  # 50-9=41
    assert score == 41
    assert risk == "medium"


def test_risk_boundary_low():
    # score=66 → low
    score, risk, _, _, _ = _compute_score([3.2], [], [])  # 50+16=66
    assert score == 66
    assert risk == "low"
