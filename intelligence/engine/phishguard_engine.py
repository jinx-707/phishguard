from intelligence.nlp.explain_prediction import explain_email
from intelligence.web.url_checks import analyze_url
from intelligence.web.html_inspector import detect_login_form
from intelligence.web.brand_detector import detect_brand_impersonation
from intelligence.nlp.zero_day_detector import get_anomaly_score

import tldextract
from urllib.parse import urlparse
from pathlib import Path
import json
import csv
import re
from datetime import datetime

# ---------------- CONFIG ---------------- #

EMAIL_MAX_SCORE = 5.0
WEBSITE_MAX_SCORE = 6.0
META_LOG_PATH = "data/meta_training.csv"

BASE_PATH = Path(__file__).resolve().parents[2]

with open(BASE_PATH / "config" / "trusted_domains.json") as f:
    TRUSTED_DOMAINS = json.load(f)

with open(BASE_PATH / "config" / "security_policy.json") as f:
    SECURITY_POLICY = json.load(f)

# ---------------- META LOGGER ---------------- #

META_COLUMNS = [
    "ml_prob",
    "zero_day_score",
    "sms_risk",
    "brand_impersonation",
    "brand_confidence",
    "login_form",
    "suspicious_url_score",
    "is_trusted_domain",
    "label",
    "source",
    "timestamp"
]

def log_meta_sample(features: dict, label: int, source: str):
    row = {k: float(features.get(k, 0.0)) for k in META_COLUMNS if k not in ["label", "source", "timestamp"]}
    row["label"] = int(label)
    row["source"] = source
    row["timestamp"] = datetime.utcnow().isoformat()

    file_exists = Path(META_LOG_PATH).exists()

    with open(META_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=META_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

# ---------------- DECISION HELPERS ---------------- #

def decide_action(score):
    if score >= 0.75:
        return "block"
    if score >= 0.55:
        return "warn"
    if score >= 0.30:
        return "review"
    return "allow"

def confidence_from_score(score):
    if score >= 0.85:
        return 0.95
    if score >= 0.70:
        return 0.85
    if score >= 0.50:
        return 0.70
    if score >= 0.30:
        return 0.55
    return 0.90

def action_message(action):
    return {
        "allow": "No threat detected.",
        "review": "Looks suspicious. Please verify before interacting.",
        "warn": "High risk detected. Proceed with caution.",
        "block": "Confirmed phishing attempt. Access blocked."
    }.get(action, "")

def humanize_reasons(reasons):
    mapping = {
        "Login form detected": "Page contains a password field.",
        "Brand impersonation detected": "Trusted brand referenced but domain is unrelated.",
        "Trusted domain": "Domain is known and trusted.",
        "Phishing language detected": "Urgent or manipulative language detected.",
        "Zero-day anomaly detected": "Behavior deviates from known safe patterns.",
        "Contains clickable link": "Contains a clickable link."
    }
    return [mapping.get(r, r) for r in reasons]

# ---------------- SMS HEURISTICS ---------------- #

SMS_URGENCY = ["urgent", "verify", "immediately", "suspended", "click"]

def analyze_sms(text):
    text = text.lower()
    return min(sum(1 for w in SMS_URGENCY if w in text), 2)

# ---------------- EMAIL ANALYSIS ---------------- #

def analyze_email(text):
    nlp_result = explain_email(text)

    ml_prob = nlp_result.get("phishing_probability", 0.0)
    sms_risk = analyze_sms(text)

    risk_score = sms_risk + (ml_prob * 2.0)
    reasons = []

    if ml_prob >= 0.5:
        reasons.append("Phishing language detected")

    text_l = text.lower()

    # --- BRAND + URGENCY HARD BLOCK ---
    BRANDS = ["google", "paypal", "apple", "amazon", "netflix"]
    ACTIONS = ["login", "verify", "secure", "confirm"]
    URGENCY = ["urgent", "immediately", "suspended", "locked", "alert"]

    brand_hit = any(b in text_l for b in BRANDS)
    action_hit = any(a in text_l for a in ACTIONS)
    urgency_hit = any(u in text_l for u in URGENCY)

    if brand_hit and action_hit and urgency_hit:
        score = 1.0
        features = {
            "ml_prob": ml_prob,
            "zero_day_score": 0,
            "sms_risk": sms_risk,
            "brand_impersonation": 1,
            "brand_confidence": 1.0,
            "login_form": 0,
            "suspicious_url_score": 0,
            "is_trusted_domain": 0
        }
        log_meta_sample(features, 1, "email")
        return {
            "type": "email_or_sms",
            "verdict": "phishing",
            "action": "block",
            "message": action_message("block"),
            "risk_score": score,
            "confidence": confidence_from_score(score),
            "reasons": ["Brand impersonation with urgent action request"],
            "features": features,
            "explanation": nlp_result
        }

    # --- LEGIT BRAND SOFTENING ---
    LEGIT_WORDS = ["successfully", "completed", "receipt", "confirmation"]
    if brand_hit and any(w in text_l for w in LEGIT_WORDS):
        risk_score *= 0.6

    # --- URL IN EMAIL BOOST ---
    if re.search(r"https?://", text):
        risk_score += 0.5
        reasons.append("Contains clickable link")

    # --- ZERO DAY ---
    zero_day_score = 0.0
    if SECURITY_POLICY.get("enable_zero_day", True):
        try:
            zero_day_score = min(get_anomaly_score(text), 1.0)
            risk_score += zero_day_score
            if zero_day_score >= 0.3:
                reasons.append("Zero-day anomaly detected")
        except RuntimeError:
            pass

    score = round(min(risk_score / EMAIL_MAX_SCORE, 1.0), 2)
    action = decide_action(score)
    verdict = "phishing" if action == "block" else "safe"

    features = {
        "ml_prob": ml_prob,
        "zero_day_score": zero_day_score,
        "sms_risk": sms_risk,
        "brand_impersonation": 0,
        "brand_confidence": 0,
        "login_form": 0,
        "suspicious_url_score": 0,
        "is_trusted_domain": 0
    }

    log_meta_sample(features, 1 if verdict == "phishing" else 0, "email")

    return {
        "type": "email_or_sms",
        "verdict": verdict,
        "action": action,
        "message": action_message(action),
        "risk_score": score,
        "confidence": confidence_from_score(score),
        "reasons": humanize_reasons(reasons),
        "features": features,
        "explanation": nlp_result
    }

# ---------------- WEBSITE ANALYSIS ---------------- #

def analyze_website(url):
    extracted = tldextract.extract(url)
    registered_domain = extracted.registered_domain.lower()
    is_trusted = registered_domain in TRUSTED_DOMAINS

    url_result = analyze_url(url)
    form_result = detect_login_form(url)
    brand_result = detect_brand_impersonation(url)

    features = {
        "ml_prob": 0,
        "zero_day_score": 0,
        "sms_risk": 0,
        "brand_impersonation": int(brand_result.get("impersonation", False)),
        "brand_confidence": brand_result.get("confidence", 0.0),
        "login_form": int(form_result.get("login_form_detected", False)),
        "suspicious_url_score": url_result.get("score", 0.0),
        "is_trusted_domain": int(is_trusted)
    }

    if brand_result.get("impersonation"):
        verdict = "phishing"
        action = "block"
        score = 1.0
        reasons = ["Brand impersonation detected"]

    elif is_trusted:
        verdict = "safe"
        action = "allow"
        score = 0.0
        reasons = ["Trusted domain"]

    else:
        risk_score = 0
        reasons = []

        if url_result.get("verdict") == "phishing":
            risk_score += 1

        if form_result.get("login_form_detected"):
            risk_score += 2
            reasons.append("Login form detected")

        score = round(min(risk_score / WEBSITE_MAX_SCORE, 1.0), 2)
        action = decide_action(score)
        verdict = "phishing" if action == "block" else "safe"

    log_meta_sample(features, 1 if verdict == "phishing" else 0, "website")

    return {
        "type": "website",
        "verdict": verdict,
        "action": action,
        "message": action_message(action),
        "risk_score": score,
        "confidence": confidence_from_score(score),
        "reasons": humanize_reasons(reasons),
        "features": features
    }

# ---------------- ENTRY POINT ---------------- #

def analyze(input_type, payload):
    input_type = input_type.lower().strip()

    if input_type in ["email", "sms", "email_or_sms"]:
        return analyze_email(payload)

    if input_type == "website":
        return analyze_website(payload)

    raise ValueError(f"Unsupported input type: {input_type}")