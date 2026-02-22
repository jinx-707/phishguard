from intelligence.nlp.explain_prediction import explain_email
from intelligence.web.url_checks import analyze_url
from intelligence.web.html_inspector import detect_login_form
from intelligence.web.brand_detector import detect_brand_impersonation
from intelligence.nlp.zero_day_detector import is_anomalous
from intelligence.engine.health import health_check 

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "security_policy.json"

with open(CONFIG_PATH, "r") as f:
    SECURITY_POLICY = json.load(f)


# ---------------- POLICY ---------------- #

def decide_action(risk_score):
    if risk_score >= SECURITY_POLICY["block_threshold"]:
        return "block"
    elif risk_score >= SECURITY_POLICY["warn_threshold"]:
        return "warn"
    else:
        return "allow"


# ---------------- HUMAN EXPLAINABILITY ---------------- #

def humanize_reasons(reasons):
    mapping = {
        "Phishing language detected": "This message uses urgent or threatening language commonly seen in phishing.",
        "Zero-day anomaly detected": "This message does not resemble typical legitimate communication patterns.",
        "Login form detected": "This page contains a password input field, which may be used to steal credentials.",
        "Brand impersonation detected": "This page pretends to be a trusted brand but is hosted on an unrelated domain.",
        "Suspicious TLD: .tk": "This website uses a high-risk domain often associated with scams.",
        "Contains keyword: verify": "The page urges account verification, a common phishing tactic.",
        "Contains keyword: login": "The page prompts users to log in, which may indicate credential harvesting.",
        "Contains keyword: secure": "The page uses security-related language to create false trust.",
        "Contains keyword: account": "The page references user accounts, a frequent phishing lure."
    }

    return [mapping.get(r, r) for r in reasons]


# ---------------- EMAIL ANALYSIS ---------------- #

def analyze_email(email_text):
    nlp_result = explain_email(email_text)
    anomaly = (
    is_anomalous(email_text)
    if SECURITY_POLICY.get("enable_zero_day", True)
    else False
)

    risk_score = 0
    reasons = []

    if nlp_result["prediction"] == 1:
        risk_score += 2
        reasons.append("Phishing language detected")

    if anomaly:
        risk_score += 1
        reasons.append("Zero-day anomaly detected")

    action = decide_action(risk_score)
    verdict = "phishing" if action == "block" else "safe"

    reasons = humanize_reasons(reasons)

    return {
        "type": "email",
        "verdict": verdict,
        "action": action,
        "risk_score": risk_score,
        "reasons": reasons,
        "explanation": nlp_result
    }


# ---------------- WEBSITE ANALYSIS ---------------- #

def analyze_website(url):
    risk_score = 0
    reasons = []

    url_result = analyze_url(url)
    form_result = detect_login_form(url)
    brand_result = detect_brand_impersonation(url)

    if url_result["verdict"] == "phishing":
        risk_score += 1
        reasons.extend(url_result["reasons"])

    if form_result.get("login_form_detected"):
        risk_score += 2
        reasons.append("Login form detected")
    
    if SECURITY_POLICY.get("enable_brand_detection", True):
        if brand_result["impersonation"]:
            risk_score += 2
            reasons.append("Brand impersonation detected")

    action = decide_action(risk_score)
    verdict = "phishing" if action == "block" else "safe"

    reasons = humanize_reasons(list(set(reasons)))

    return {
        "type": "website",
        "verdict": verdict,
        "action": action,
        "risk_score": risk_score,
        "reasons": reasons
    }


# ---------------- UNIFIED ENTRY POINT ---------------- #

def analyze(input_type, payload):
    """
    Unified PhishGuard entry point.
    input_type: 'email' or 'website'
    payload: email text or URL
    """
    if input_type == "email":
        return analyze_email(payload)

    elif input_type == "website":
        return analyze_website(payload)

    else:
        raise ValueError("Unsupported input type")


if __name__ == "__main__":
    email = "Urgent: verify your account immediately to avoid suspension"
    url = "http://secure-login-verify-account.tk"

    print(analyze("email", email))
    print(analyze("website", url))