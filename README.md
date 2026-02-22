# 🛡️ PhishGuard

**Real-time, explainable phishing detection at the endpoint**

PhishGuard is a phishing detection and prevention platform designed to stop attacks **before users interact with them**. It detects phishing across **emails and websites**, including **fake login pages, brand impersonation, and zero-day scams**, while running efficiently **directly on the user’s device**.

---

## 🚨 Problem Statement

Phishing attacks are becoming more advanced:

- AI-generated phishing emails look legitimate  
- Fake login pages impersonate trusted brands  
- Zero-day scams bypass traditional filters  
- Users do not trust opaque “AI blocked this” warnings  

Most existing solutions are:
- Cloud-heavy and slow
- Signature-based and brittle
- Accurate but not explainable

---

## ✅ Solution

PhishGuard combines **machine learning**, **behavioral analysis**, and **web inspection** into a single intelligence engine that:

- Detects phishing emails before clicks
- Identifies fake login pages and brand impersonation
- Flags zero-day and unseen attack patterns
- Explains every decision in human-readable language
- Runs fast enough for real-time endpoint protection

---

## 🧠 Core Capabilities

### 📧 Email Phishing Detection
- NLP-based phishing language detection
- Trained on 80,000+ real emails
- ~99% accuracy
- Explainable detection reasons (urgency, threats, verification traps)

### 🌐 Web & Fake Login Detection
- Suspicious URL and domain analysis
- HTML inspection to detect credential-harvesting login forms
- Brand impersonation detection (Google, PayPal, Microsoft, etc.)

### 🧪 Zero-Day Detection
- Anomaly detection for previously unseen attacks
- Flags suspicious behavior even without known signatures

### ⚖️ Risk-Based Policy Engine

PhishGuard uses a tiered response model:

| Risk Score | Action | Description |
|-----------|--------|-------------|
| 0 | Allow | Safe content |
| 1 | Warn | Suspicious, user should be cautious |
| 2+ | Block | Confirmed phishing |

### 🔍 Explainability
Every alert includes clear explanations such as:
- “This page urges account verification, a common phishing tactic.”
- “This website uses a high-risk domain often associated with scams.”

---

