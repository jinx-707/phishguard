from joblib import load
from pathlib import Path
import json

BASE_PATH = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_PATH / "models"
ACTIVE_MODELS = MODEL_DIR / "active_models.json"

FEATURE_ORDER = [
    "ml_prob",
    "zero_day_score",
    "sms_risk",
    "brand_impersonation",
    "brand_confidence",
    "login_form",
    "suspicious_url_score",
    "is_trusted_domain"
]

_base_estimator = None  # cache


def load_base_estimator():
    """
    Loads and caches the underlying LogisticRegression
    from the calibrated pipeline.
    """
    global _base_estimator

    if _base_estimator is not None:
        return _base_estimator

    with open(ACTIVE_MODELS) as f:
        active = json.load(f)

    model_path = MODEL_DIR / active["phish_model"]
    pipeline = load(model_path)

    calibrated = pipeline.named_steps["clf"]

    # Extract underlying logistic regression
    _base_estimator = calibrated.calibrated_classifiers_[0].estimator

    return _base_estimator


def build_attributions(features: dict, score: float):
    """
    Builds proportional feature contribution explanations
    from logistic regression coefficients.
    """

    if score <= 0:
        return []

    model = load_base_estimator()
    weights = model.coef_[0]

    raw = []
    total = 0.0

    for f, w in zip(FEATURE_ORDER, weights):
        value = float(features.get(f, 0.0))
        contrib = abs(float(w) * value)  # force pure float

        if contrib > 0:
            raw.append((f, contrib))
            total += contrib

    if total == 0:
        return []

    explanations = []

    for f, c in sorted(raw, key=lambda x: x[1], reverse=True):
        proportion = float(c / total)  # pure float
        explanations.append({
            "signal": f,
            "contribution": round(proportion * score, 2)
        })

    return explanations