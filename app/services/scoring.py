"""
Scoring & Fusion Engine.

Improvements:
  1.  compute_final_score() now accepts anomaly_score (zero-day signal).
  2.  Isotonic regression calibration applied to fused score so that
      output probabilities are well-calibrated.
  3.  Richer reason codes with domain-specific explanations.
  4.  Entropy-based confidence measure (low when scores disagree).
"""
from __future__ import annotations

import math
from typing import Tuple, List, Optional

import structlog
import numpy as np

from app.config import settings
from app.models.schemas import RiskLevel

logger = structlog.get_logger(__name__)


def _calculate_extension_score(features: dict) -> float:
    """Calculate risk score from Chrome extension features."""
    if not features:
        return 0.0
    
    score = 0.0
    
    # Password fields - major phishing indicator
    if features.get('password_fields', 0) > 0:
        score += 0.25
    
    # Hidden inputs - often used in credential harvesting
    hidden_count = features.get('hidden_inputs', 0)
    if hidden_count > 0:
        score += min(hidden_count * 0.1, 0.2)
    
    # External links - suspicious if many
    external_links = features.get('external_links', 0)
    if external_links > 10:
        score += 0.15
    elif external_links > 5:
        score += 0.08
    
    # Iframes - can be used for hidden content
    if features.get('iframe_count', 0) > 0:
        score += 0.1
    
    # Suspicious URL keywords
    if features.get('suspicious_url_keywords'):
        score += 0.15
    
    # Long URL - common in phishing
    if features.get('long_url', False):
        score += 0.08
    
    # Excessive subdomains - common in phishing
    if features.get('excessive_subdomains', False):
        score += 0.1
    
    # Suspicious keywords on page
    page_keywords = features.get('suspicious_keywords_found', [])
    if page_keywords:
        score += min(len(page_keywords) * 0.1, 0.25)
    
    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Isotonic calibrator — fitted lazily from saved checkpoint
# ---------------------------------------------------------------------------
_calibrator        = None
_calibrator_loaded = False


def _get_calibrator():
    """
    Lazy-load (or fit a default) isotonic calibration model.

    We persist the calibrator alongside the ML model.  On first call we
    try to load `isotonic_calibrator.joblib`.  If absent we fit a trivial
    passthrough calibrator on three anchor points [0, 0.5, 1].
    """
    global _calibrator, _calibrator_loaded

    if _calibrator_loaded:
        return _calibrator

    try:
        import joblib, os, sys, pathlib

        project_root = pathlib.Path(__file__).resolve().parent.parent.parent
        cal_path     = project_root / "intelligence" / "nlp" / "isotonic_calibrator.joblib"

        if cal_path.exists():
            _calibrator = joblib.load(str(cal_path))
            logger.info("Isotonic calibrator loaded from disk.")
        else:
            # Fit a minimal anchor calibrator so the maths stays correct
            from sklearn.isotonic import IsotonicRegression
            cal = IsotonicRegression(out_of_bounds="clip")
            cal.fit([0.0, 0.5, 1.0], [0.0, 0.5, 1.0])  # identity baseline
            _calibrator = cal
            logger.info("Using identity isotonic calibrator (no checkpoint found).")

    except ImportError:
        logger.warning("scikit-learn not installed — isotonic calibration disabled.")
    except Exception as e:
        logger.warning("Failed to load calibrator", error=str(e))

    _calibrator_loaded = True
    return _calibrator


def calibrate_score(raw_score: float) -> float:
    """Apply isotonic calibration to map raw fusion score → calibrated probability."""
    cal = _get_calibrator()
    if cal is None:
        return raw_score
    try:
        calibrated = float(cal.predict([raw_score])[0])
        return round(float(np.clip(calibrated, 0.0, 1.0)), 4)
    except Exception:
        return raw_score


# ---------------------------------------------------------------------------
# Main fusion function
# ---------------------------------------------------------------------------

def compute_final_score(
    model_score: float,
    graph_score: float,
    anomaly_score: float = 0.0,
    thresholds: Optional[dict] = None,
) -> Tuple[RiskLevel, float, List[str]]:
    """
    Fuse ML, graph, and anomaly scores into a single calibrated risk decision.

    Formula
    -------
        w_model   = settings.MODEL_WEIGHT   (default 0.6)
        w_graph   = settings.GRAPH_WEIGHT   (default 0.4)
        w_anomaly = 0.25 (bonus weight when anomaly_score ≥ 0.6)

        raw = w_model * model_score + w_graph * graph_score
        if anomaly_score >= 0.6:
            raw = (raw + w_anomaly * anomaly_score) / (1 + w_anomaly)

        final = calibrate(raw)   ← isotonic regression

    Parameters
    ----------
    model_score   : ML prediction score [0, 1]
    graph_score   : Graph-based risk    [0, 1]
    anomaly_score : Zero-day anomaly    [0, 1] (default 0 = no anomaly)
    thresholds    : Override {"high": 0.7, "medium": 0.4} defaults

    Returns
    -------
    (RiskLevel, confidence, reasons)
    """
    if thresholds is None:
        thresholds = {"high": 0.7, "medium": 0.4}

    # ── Clamp inputs ─────────────────────────────────────────────────────
    model_score   = float(np.clip(model_score,   0.0, 1.0))
    graph_score   = float(np.clip(graph_score,   0.0, 1.0))
    anomaly_score = float(np.clip(anomaly_score, 0.0, 1.0))

    # ── Weighted fusion ───────────────────────────────────────────────────
    w_model = float(settings.MODEL_WEIGHT)   # 0.6
    w_graph = float(settings.GRAPH_WEIGHT)   # 0.4

    raw_score = w_model * model_score + w_graph * graph_score

    # Blend anomaly signal when it is significant
    ANOMALY_WEIGHT = 0.25
    if anomaly_score >= 0.6:
        raw_score = (raw_score + ANOMALY_WEIGHT * anomaly_score) / (1.0 + ANOMALY_WEIGHT)

    # ── Isotonic calibration ─────────────────────────────────────────────
    calibrated = calibrate_score(raw_score)

    # ── Risk classification ───────────────────────────────────────────────
    risk_level = apply_threshold(calibrated, thresholds)

    # ── Confidence via score entropy ──────────────────────────────────────
    scores        = [model_score, graph_score, anomaly_score if anomaly_score > 0 else None]
    active_scores = [s for s in scores if s is not None]
    confidence    = _entropy_confidence(active_scores, calibrated)

    # ── Explainability reasons ────────────────────────────────────────────
    reasons = _generate_reasons(model_score, graph_score, anomaly_score, risk_level, calibrated)

    logger.info(
        "Score computed",
        model_score=model_score,
        graph_score=graph_score,
        anomaly_score=anomaly_score,
        raw_score=round(raw_score, 4),
        calibrated=calibrated,
        risk_level=risk_level.value,
        confidence=confidence,
    )

    return risk_level, round(confidence, 3), reasons


# ---------------------------------------------------------------------------
# Supporting functions
# ---------------------------------------------------------------------------

def normalize_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Normalise score to [0, 1] range."""
    if max_val == min_val:
        return 0.5
    return float(np.clip((score - min_val) / (max_val - min_val), 0.0, 1.0))


def apply_threshold(score: float, thresholds: dict) -> RiskLevel:
    """Classify a continuous score into a RiskLevel using configurable thresholds."""
    if score >= thresholds.get("high", 0.7):
        return RiskLevel.HIGH
    if score >= thresholds.get("medium", 0.4):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def calculate_entropy(scores: List[float]) -> float:
    """Shannon entropy of a list of probabilities."""
    if not scores:
        return 0.0
    total = sum(scores)
    if total == 0:
        return 0.0
    probs   = [s / total for s in scores]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    return entropy


def _entropy_confidence(active_scores: List[float], calibrated: float) -> float:
    """
    Produce a confidence value based on:
      - How far `calibrated` is from the decision boundary (0.4 / 0.7)
      - How much the individual scores agree with each other
    """
    if not active_scores:
        return 0.5

    # Score spread: low variance → high agreement → higher confidence
    variance = float(np.var(active_scores)) if len(active_scores) > 1 else 0.0
    spread_penalty = min(variance * 2, 0.4)

    # Distance from nearest threshold
    thresholds  = [0.4, 0.7]
    min_dist    = min(abs(calibrated - t) for t in thresholds)
    boundary_conf = min(min_dist * 2, 0.5)   # 0 at boundary, up to 0.5 far from it

    confidence = max(0.1, min(1.0, 0.5 + boundary_conf - spread_penalty))
    return round(confidence, 3)


def _generate_reasons(
    model_score: float,
    graph_score: float,
    anomaly_score: float,
    risk_level: RiskLevel,
    calibrated: float,
) -> List[str]:
    """Generate structured, human-readable explanation reasons."""
    reasons: List[str] = []

    # ── ML model signal ───────────────────────────────────────────────────
    if model_score >= 0.75:
        reasons.append(
            f"ML model reports HIGH confidence of malicious content (score: {model_score:.2f})"
        )
    elif model_score >= 0.45:
        reasons.append(
            f"ML model reports MODERATE suspicion (score: {model_score:.2f})"
        )
    else:
        reasons.append(
            f"ML model finds content LOW risk (score: {model_score:.2f})"
        )

    # ── Graph signal ──────────────────────────────────────────────────────
    if graph_score >= 0.7:
        reasons.append(
            f"Domain appears in known-malicious graph clusters (graph score: {graph_score:.2f})"
        )
    elif graph_score >= 0.4:
        reasons.append(
            f"Domain has moderate graph-based threat indicators (graph score: {graph_score:.2f})"
        )
    else:
        reasons.append(
            f"No significant graph-based connections to known threats (graph score: {graph_score:.2f})"
        )

    # ── Anomaly / zero-day signal ────────────────────────────────────────
    if anomaly_score >= 0.8:
        reasons.append(
            f"⚠ Highly anomalous: pattern differs significantly from known samples "
            f"(anomaly score: {anomaly_score:.2f})"
        )
    elif anomaly_score >= 0.6:
        reasons.append(
            f"Moderate anomaly detected — may be novel attack variant "
            f"(anomaly score: {anomaly_score:.2f})"
        )

    # ── Calibrated final verdict ──────────────────────────────────────────
    if risk_level == RiskLevel.HIGH:
        reasons.append(
            f"HIGH RISK — calibrated probability {calibrated:.2f}: immediate investigation recommended"
        )
    elif risk_level == RiskLevel.MEDIUM:
        reasons.append(
            f"MEDIUM RISK — calibrated probability {calibrated:.2f}: caution advised"
        )
    else:
        reasons.append(
            f"LOW RISK — calibrated probability {calibrated:.2f}: content appears benign"
        )

    return reasons
