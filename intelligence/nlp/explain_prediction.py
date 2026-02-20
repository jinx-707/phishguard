import joblib
import numpy as np

from pathlib import Path

BASE_PATH = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_PATH / "models" / "phish_model.joblib"
VECTORIZER_PATH = BASE_PATH / "models" / "tfidf_vectorizer.joblib"

model = None
vectorizer = None

def load_model():
    global model, vectorizer
    if model is None or vectorizer is None:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)


def explain_email(text, top_k=10):
    load_model()
    feature_names = vectorizer.get_feature_names_out()
    vec = vectorizer.transform([text])
    probs = model.predict_proba(vec)[0]
    prediction = model.predict(vec)[0]

    coefs = model.coef_[0]
    weighted_features = vec.toarray()[0] * coefs

    top_indices = np.argsort(weighted_features)[-top_k:][::-1]
    reasons = [(feature_names[i], weighted_features[i]) for i in top_indices]

    return {
        "prediction": int(prediction),
        "phishing_probability": float(probs[1]),
        "top_reasons": reasons
    }

if __name__ == "__main__":
    sample_email = """
    Urgent action required! Your account will be suspended.
    Click the link below to verify your information immediately.
    """

    result = explain_email(sample_email)
    print(result)