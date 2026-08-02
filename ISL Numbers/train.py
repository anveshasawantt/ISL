import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

CSV_PATH = r"C:\ISL PROJECT\data\isl_numbers_angles_2hands.csv"
MODEL_PATH = r"C:\ISL PROJECT\data\isl_numbers_model.pkl"

def train_model():
    if not os.path.exists(CSV_PATH):
        print(f"CSV file not found at {CSV_PATH}. Run extract.py first.")
        return

    print("Loading data...")
    df = pd.read_csv(CSV_PATH, dtype={"label": str})
    if df.empty:
        print("CSV file is empty. Check your dataset and extraction process.")
        return

    X = df.drop('label', axis=1).values
    y = df['label']
    print(f"Dataset shape: {df.shape}")
    print(f"Classes found: {sorted(y.unique())}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    print("Training Random Forest model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    print("Evaluating model...")
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()