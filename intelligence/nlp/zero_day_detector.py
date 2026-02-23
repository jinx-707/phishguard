"""
Zero-Day Anomaly Detector using IsolationForest.

Trains on historically observed scan data (text+URL features) and flags
inputs whose feature vectors deviate significantly from the baseline — a
surrogate for zero-day / never-seen-before threats.

Lifecycle
---------
    1.  train()         – fit IsolationForest on existing scan history.
    2.  is_anomalous()  – binary classification (True = likely zero-day).
    3.  get_anomaly_score() – continuous score in [0, 1] useful for fusion.

The model + vectoriser are saved to `intelligence/nlp/` via joblib.
If no saved model exists, a lightweight in-process model is returned
(fitted on a minimal bootstrap corpus) so the detector never blocks start-up.
"""
from __future__ import annotations

import os
import re
import math
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent
MODEL_PATH      = str(_BASE_DIR / "zero_day_model.joblib")
VECTORIZER_PATH = str(_BASE_DIR / "zero_day_vectorizer.joblib")

# ── Module-level cache (loaded once per worker process) ───────────────────────
_model      = None
_vectorizer = None
_loaded     = False


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _feature_text(text: str, url: Optional[str] = None) -> str:
    """
    Build a single string combining normalised text + URL tokens for TF-IDF.
    This keeps vectorisation simple and consistent.
    """
    parts = []
    if text:
        # lowercase, strip HTML tags, collapse whitespace
        clean = re.sub(r"<[^>]+>", " ", text.lower())
        clean = re.sub(r"\s+", " ", clean).strip()
        parts.append(clean)
    if url:
        # decompose URL into tokens (split on /.?=&-)
        url_tokens = re.sub(r"[/.\?=&#\-_]", " ", url.lower())
        parts.append(url_tokens)
    return " ".join(parts) or "unknown"


def _bootstrap_corpus() -> list[str]:
    """
    Minimal corpus used when no training data is available.
    Contains clearly benign and clearly phishing patterns so the
    IsolationForest has at least some baseline variance to work with.
    """
    return [
        "invoice attached please review quarterly report",
        "meeting agenda monday morning stand-up update",
        "your account has been suspended verify immediately",
        "urgent action required click here to confirm password",
        "click http paypal-verify-now xyz login",
        "reset password click link expires 24 hours",
        "congratulations you won prize claim now",
        "bank account locked verify identity now",
        "weekly newsletter product update release notes",
        "github pull request review automated test results",
    ] * 10  # repeat to give IsolationForest enough samples


# ══════════════════════════════════════════════════════════════════════════════
# Training
# ══════════════════════════════════════════════════════════════════════════════

def train(texts: Optional[list[str]] = None, save: bool = True) -> None:
    """
    Train (or retrain) the IsolationForest anomaly detector.

    Parameters
    ----------
    texts   : list of raw text strings to train on.  If None, the function
              tries to load data from the PostgreSQL `scans` table (async
              context is handled by running a sync query).  Falls back to
              the bootstrap corpus if the DB is also unavailable.
    save    : persist model + vectoriser to disk via joblib.
    """
    global _model, _vectorizer, _loaded

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.ensemble import IsolationForest
        import joblib
    except ImportError as e:
        logger.warning("scikit-learn / joblib not installed, zero-day detector disabled: %s", e)
        return

    # ── Collect training corpus ───────────────────────────────────────────────
    if texts is None:
        texts = _load_texts_from_db()

    if not texts or len(texts) < 10:
        logger.warning(
            "Insufficient training data (%d samples), using bootstrap corpus.",
            len(texts) if texts else 0,
        )
        texts = _bootstrap_corpus()

    feature_strings = [_feature_text(t) for t in texts]

    # ── Vectorise ─────────────────────────────────────────────────────────────
    vectorizer = TfidfVectorizer(
        max_features=5_000,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(feature_strings)

    # ── Fit IsolationForest ───────────────────────────────────────────────────
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,   # expect ~5 % anomalies
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    _model      = model
    _vectorizer = vectorizer
    _loaded     = True

    if save:
        joblib.dump(model,      MODEL_PATH)
        joblib.dump(vectorizer, VECTORIZER_PATH)
        logger.info("Zero-day model saved: %s, %s", MODEL_PATH, VECTORIZER_PATH)

    logger.info("Zero-day detector trained on %d samples.", len(texts))


def _load_texts_from_db() -> list[str]:
    """
    Attempt to pull scan text from PostgreSQL synchronously.
    Returns an empty list on any failure so callers can fall back gracefully.
    """
    try:
        from app.config import settings
        from sqlalchemy import create_engine, text as sql_text

        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine   = create_engine(sync_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})

        with engine.connect() as conn:
            rows = conn.execute(
                sql_text("SELECT text, url FROM scans WHERE text IS NOT NULL LIMIT 10000")
            ).fetchall()

        texts = []
        for row in rows:
            texts.append(_feature_text(row.text or "", row.url))
        logger.info("Loaded %d samples from DB for zero-day training.", len(texts))
        return texts
    except Exception as e:
        logger.warning("Could not load training data from DB: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Inference
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_loaded() -> bool:
    """
    Lazy-load the persisted model.  Returns True if a usable model is available.
    """
    global _model, _vectorizer, _loaded

    if _loaded:
        return True

    try:
        import joblib

        if os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH):
            _model      = joblib.load(MODEL_PATH)
            _vectorizer = joblib.load(VECTORIZER_PATH)
            _loaded     = True
            logger.info("Zero-day model loaded from disk.")
            return True
    except Exception as e:
        logger.warning("Failed to load zero-day model: %s", e)

    # Fall back: train on bootstrap corpus (fast, ~1 second)
    logger.info("Fitting bootstrap zero-day model (first-time startup).")
    train(texts=_bootstrap_corpus(), save=False)
    return _loaded


def is_anomalous(text: str, url: Optional[str] = None, threshold: float = 0.6) -> bool:
    """
    Return True if the sample appears anomalous (potential zero-day).

    Parameters
    ----------
    text      : text content (email body, page text, etc.)
    url       : optional URL string
    threshold : anomaly score cut-off (default 0.6 → top 40 % anomalous)
    """
    score = get_anomaly_score(text, url)
    return score >= threshold


def get_anomaly_score(text: str, url: Optional[str] = None) -> float:
    """
    Return a continuous anomaly score in [0, 1].

    IsolationForest's `decision_function` returns negative values for
    anomalies (more negative = more anomalous) and positive for normal
    samples.  We convert to [0, 1] where 1 = most anomalous.

    Formula
    -------
        raw ∈ [−0.5, 0.5]  (typical IsolationForest range)
        score = clip((0.5 − raw) / 1.0, 0, 1)
    """
    if not _ensure_loaded():
        return 0.0  # safeguard: report not anomalous if no model

    try:
        feature = _feature_text(text or "", url)
        vec     = _vectorizer.transform([feature])
        raw     = float(_model.decision_function(vec)[0])
        # Map: raw=-0.5 → score=1.0 (most anomalous)
        #       raw= 0.5 → score=0.0 (most normal)
        score = float(np.clip((0.5 - raw) / 1.0, 0.0, 1.0))
        return round(score, 4)
    except Exception as e:
        logger.warning("Zero-day score computation failed: %s", e)
        return 0.0


def get_z_score_anomaly(value: float, baseline_mean: float, baseline_std: float) -> float:
    """
    Simple z-score based anomaly measure for numeric features
    (e.g. unusual confidence score, unusual scan latency).

    Returns a [0,1] anomaly probability using the CDF of the standard normal.
    """
    if baseline_std == 0:
        return 0.0
    z = abs((value - baseline_mean) / baseline_std)
    # P(|Z| > z) — probability of being this extreme under a normal baseline
    p_anomaly = 2 * (1 - _standard_normal_cdf(z))
    return round(float(np.clip(1 - p_anomaly, 0, 1)), 4)


def _standard_normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ══════════════════════════════════════════════════════════════════════════════
# CLI entrypoint
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Training zero-day detector …")
    train()

    samples = [
        ("Your invoice is attached. Please review the quarterly report.", None),
        ("Urgent! Verify your account immediately or it will be suspended.", None),
        ("Click http://192.168.0.1/login.php to confirm bank account", "http://192.168.0.1/login.php"),
        ("Congratulations you won a prize, claim now!", "http://paypal-verify.xyz/claim"),
    ]

    for text, url in samples:
        score  = get_anomaly_score(text, url)
        is_zd  = is_anomalous(text, url)
        print(f"Text: {text[:60]!r}")
        print(f"  anomaly_score={score:.3f}  is_zero_day={is_zd}")
        print()