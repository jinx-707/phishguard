import joblib
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
import os

MODEL_PATH = "intelligence/nlp/zero_day_model.pkl"
VECTORIZER_PATH = "intelligence/nlp/zero_day_vectorizer.pkl"

def train_zero_day_detector(data_path="data/raw/emails/phishing_email.csv"):
    df = pd.read_csv(data_path)

    texts = df["text_combined"].astype(str)

    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    X = vectorizer.fit_transform(texts)

    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(X)

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    print("Zero-day anomaly detector trained and saved.")

def is_anomalous(text):
    if not os.path.exists(MODEL_PATH):
        train_zero_day_detector()

    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)

    X = vectorizer.transform([text])
    prediction = model.predict(X)

    return prediction[0] == -1


if __name__ == "__main__":
    train_zero_day_detector()