from eem._pipeline import _compute_score


def test_empty_impacts_returns_neutral():
    score, risk, keywords = _compute_score([], [])
    assert score == 50
    assert risk == "medium"
    assert keywords == []


def test_severe_negative_impact():
    score, risk, _ = _compute_score([-8.4], [])
    assert score == 8
    assert risk == "high"


def test_mild_positive_impact():
    score, risk, _ = _compute_score([2.1], [])
    assert score == 60
    assert risk == "medium"


def test_neutral_impact():
    score, risk, _ = _compute_score([0.0], [])
    assert score == 50
    assert risk == "medium"


def test_strong_positive_impact():
    score, risk, _ = _compute_score([7.0], [])
    assert score == 85
    assert risk == "low"


def test_impact_clamped_above():
    score, _, _ = _compute_score([20.0], [])
    assert score == 100


def test_impact_clamped_below():
    score, _, _ = _compute_score([-20.0], [])
    assert score == 0


def test_average_of_multiple_events():
    score, risk, _ = _compute_score([-8.4, 2.1], [])
    assert score == round((8 + 61) / 2)
    assert risk == "high"


def test_keyword_frequency_order():
    kws = [["korupcja", "CBA"], ["korupcja", "zarząd"], ["CBA"]]
    _, _, top_kw = _compute_score([0.0, 0.0, 0.0], kws)
    assert top_kw[0] == "korupcja"
    assert "CBA" in top_kw


def test_keyword_capped_at_6():
    kws = [["a", "b", "c", "d", "e", "f", "g"]]
    _, _, top_kw = _compute_score([0.0], kws)
    assert len(top_kw) <= 6


def test_risk_boundary_high():
    score, risk, _ = _compute_score([-2.0], [])
    assert score == 40
    assert risk == "high"


def test_risk_boundary_medium():
    score, risk, _ = _compute_score([-1.8], [])
    assert score == 41
    assert risk == "medium"


def test_risk_boundary_low():
    score, risk, _ = _compute_score([3.2], [])
    assert score == 66
    assert risk == "low"
