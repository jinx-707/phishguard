import joblib

MODEL_PATH = "intelligence/nlp/phish_model.joblib"
VECTORIZER_PATH = "intelligence/nlp/tfidf_vectorizer.joblib"

model = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)

def predict_email(text):
    vec = vectorizer.transform([text])
    prob = model.predict_proba(vec)[0][1]
    pred = model.predict(vec)[0]

    return {
        "is_phishing": bool(pred),
        "confidence": float(prob)
    }

if __name__ == "__main__":
    emails = [
        "Your invoice is attached. Please review.",
        "Urgent! Verify your account immediately or it will be suspended."
    ]

    for email in emails:
        result = predict_email(email)
        print(email)
        print(result)
        print("-" * 50)