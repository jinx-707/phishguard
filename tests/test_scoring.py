"""
Test suite for the scoring & fusion engine.
Covers: calibration, risk thresholding, anomaly blending, reason generation.
"""
import pytest
from app.models.schemas import RiskLevel
from app.services.scoring import (
    compute_final_score,
    normalize_score,
    apply_threshold,
    calculate_entropy,
)


class TestNormalizeScore:
    def test_within_range(self):
        assert normalize_score(0.5, 0.0, 1.0) == 0.5

    def test_clips_below_zero(self):
        assert normalize_score(-1.0, 0.0, 1.0) == 0.0

    def test_clips_above_one(self):
        assert normalize_score(2.0, 0.0, 1.0) == 1.0

    def test_equal_min_max(self):
        assert normalize_score(0.5, 0.5, 0.5) == 0.5


class TestApplyThreshold:
    def test_high_risk(self):
        assert apply_threshold(0.85, {"high": 0.7, "medium": 0.4}) == RiskLevel.HIGH

    def test_medium_risk(self):
        assert apply_threshold(0.55, {"high": 0.7, "medium": 0.4}) == RiskLevel.MEDIUM

    def test_low_risk(self):
        assert apply_threshold(0.20, {"high": 0.7, "medium": 0.4}) == RiskLevel.LOW

    def test_boundary_high(self):
        assert apply_threshold(0.70, {"high": 0.7, "medium": 0.4}) == RiskLevel.HIGH

    def test_boundary_medium(self):
        assert apply_threshold(0.40, {"high": 0.7, "medium": 0.4}) == RiskLevel.MEDIUM


class TestCalculateEntropy:
    def test_single_score(self):
        entropy = calculate_entropy([1.0])
        assert entropy == 0.0

    def test_uniform_scores(self):
        entropy = calculate_entropy([0.5, 0.5])
        assert entropy == pytest.approx(1.0, abs=0.01)

    def test_empty_scores(self):
        assert calculate_entropy([]) == 0.0


class TestComputeFinalScore:
    def test_high_risk_scores(self):
        risk, confidence, reasons = compute_final_score(
            model_score=0.9, graph_score=0.85
        )
        assert risk == RiskLevel.HIGH
        assert confidence > 0.0
        assert len(reasons) > 0

    def test_low_risk_scores(self):
        risk, confidence, reasons = compute_final_score(
            model_score=0.05, graph_score=0.02
        )
        assert risk == RiskLevel.LOW

    def test_zero_day_boosts_score(self):
        risk_no_zd, conf_no_zd, _ = compute_final_score(
            model_score=0.55, graph_score=0.45, anomaly_score=0.0
        )
        risk_zd, conf_zd, reasons_zd = compute_final_score(
            model_score=0.55, graph_score=0.45, anomaly_score=0.85
        )
        # Zero-day should push confidence higher or keep same risk
        assert conf_zd >= conf_no_zd or risk_zd.value >= risk_no_zd.value

    def test_returns_tuple_of_three(self):
        result = compute_final_score(model_score=0.5, graph_score=0.5)
        assert len(result) == 3

    def test_scores_clamped(self):
        # Even with out-of-range inputs, calibrated score should be [0,1]
        risk, confidence, _ = compute_final_score(
            model_score=1.5, graph_score=-0.5
        )
        assert 0.0 <= confidence <= 1.0

    def test_reasons_are_non_empty_strings(self):
        _, _, reasons = compute_final_score(model_score=0.7, graph_score=0.6)
        assert all(isinstance(r, str) and len(r) > 0 for r in reasons)
