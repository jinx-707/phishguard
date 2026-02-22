"""
Scoring and fusion engine for combining model and graph scores.
"""
from typing import Tuple, List
import structlog

from app.config import settings
from app.models.schemas import RiskLevel

logger = structlog.get_logger(__name__)


def compute_final_score(
    model_score: float,
    graph_score: float,
) -> Tuple[RiskLevel, float, List[str]]:
    """
    Compute final risk score by fusing model and graph scores.
    
    Args:
        model_score: ML model score (0-1)
        graph_score: Graph-based score (0-1)
    
    Returns:
        Tuple of (risk_level, confidence, reasons)
    """
    # Normalize scores to [0, 1]
    model_score = max(0.0, min(1.0, model_score))
    graph_score = max(0.0, min(1.0, graph_score))
    
    # Weighted fusion
    final_score = (
        settings.MODEL_WEIGHT * model_score +
        settings.GRAPH_WEIGHT * graph_score
    )
    
    # Determine risk level based on thresholds
    if final_score >= 0.7:
        risk_level = RiskLevel.HIGH
    elif final_score >= 0.4:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW
    
    # Calculate confidence based on score distribution
    score_diff = abs(model_score - graph_score)
    confidence = 1.0 - (score_diff / 2.0)  # Higher confidence when scores agree
    
    # Generate explanation reasons
    reasons = _generate_reasons(model_score, graph_score, risk_level)
    
    logger.info(
        "Score computed",
        model_score=model_score,
        graph_score=graph_score,
        final_score=final_score,
        risk_level=risk_level.value,
    )
    
    return risk_level, round(confidence, 2), reasons


def _generate_reasons(
    model_score: float,
    graph_score: float,
    risk_level: RiskLevel,
) -> List[str]:
    """Generate explanation reasons based on scores."""
    reasons = []
    
    # Model-based reasons
    if model_score >= 0.7:
        reasons.append("High ML model confidence for malicious content")
    elif model_score >= 0.4:
        reasons.append("Moderate ML model confidence")
    else:
        reasons.append("Low ML model confidence")
    
    # Graph-based reasons
    if graph_score >= 0.7:
        reasons.append("Strong graph-based threat indicators")
    elif graph_score >= 0.4:
        reasons.append("Some graph-based threat indicators")
    else:
        reasons.append("No significant graph threat indicators")
    
    # Risk level specific
    if risk_level == RiskLevel.HIGH:
        reasons.append("HIGH risk level: immediate attention recommended")
    elif risk_level == RiskLevel.MEDIUM:
        reasons.append("MEDIUM risk level: review recommended")
    else:
        reasons.append("LOW risk level: content appears benign")
    
    return reasons


def normalize_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Normalize score to [0, 1] range."""
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (score - min_val) / (max_val - min_val)))


def apply_threshold(score: float, thresholds: dict) -> RiskLevel:
    """Apply thresholds to determine risk level."""
    if score >= thresholds.get("high", 0.7):
        return RiskLevel.HIGH
    elif score >= thresholds.get("medium", 0.4):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def calculate_entropy(scores: List[float]) -> float:
    """Calculate entropy of a probability distribution."""
    if not scores:
        return 0.0
    
    # Normalize scores to probabilities
    total = sum(scores)
    if total == 0:
        return 0.0
    
    probs = [s / total for s in scores]
    
    # Calculate entropy
    import math
    entropy = 0.0
    for p in probs:
        if p > 0:
            entropy -= p * math.log2(p)
    
    return entropy
