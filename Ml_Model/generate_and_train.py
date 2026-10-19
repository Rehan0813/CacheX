import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

def generate_and_train():
    np.random.seed(42)
    n_samples = 25000

    access_frequency = np.random.beta(2, 2, n_samples)
    reuse_distance = np.random.beta(2, 2, n_samples)
    temporal_locality = np.random.beta(2, 2, n_samples)
    spatial_locality = np.random.beta(2, 2, n_samples)

    dataset = pd.DataFrame({
        "access_frequency": access_frequency,
        "reuse_distance": reuse_distance,
        "temporal_locality": temporal_locality,
        "spatial_locality": spatial_locality
    })

    freq_rank = dataset["access_frequency"].rank(pct=True)
    reuse_rank = dataset["reuse_distance"].rank(pct=True)
    temp_rank = dataset["temporal_locality"].rank(pct=True)

    policy = []
    for f, r, t in zip(freq_rank, reuse_rank, temp_rank):
        if f > 0.66:
            p = "LFU"
        elif r > 0.66:
            p = "FIFO"
        else:
            p = "LRU"

        if np.random.rand() < 0.05:
            p = np.random.choice(["LRU", "LFU", "FIFO"])
        policy.append(p)

    dataset["best_policy"] = policy

    X = dataset.drop("best_policy", axis=1)
    y = dataset["best_policy"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print("Training Random Forest model...")
    model = RandomForestClassifier(
        n_estimators=400,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print("Model Accuracy:", accuracy_score(y_test, predictions))
    print("\nClassification Report:\n", classification_report(y_test, predictions))

    # Save to all possible expected locations
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)
    grandparent_dir = os.path.dirname(parent_dir)

    target_dirs = [
        os.path.join(base_dir),
        os.path.join(parent_dir, "ml_model"),
        os.path.join(grandparent_dir, "ml_model"),
    ]

    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        target_path = os.path.join(d, "random_forest_model.pkl")
        joblib.dump(model, target_path)
        print(f"Saved model to: {target_path}")

if __name__ == "__main__":
    generate_and_train()
