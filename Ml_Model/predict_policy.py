import joblib
import pandas as pd
import os
from pathlib import Path

base_dir = Path(__file__).resolve().parent
candidate_paths = [
    base_dir / "random_forest_model.pkl",
    base_dir.parent / "ml_model" / "random_forest_model.pkl",
    base_dir.parent / "Ml_Model" / "random_forest_model.pkl",
    Path("ml_model/random_forest_model.pkl"),
]

model = None
for p in candidate_paths:
    if p.is_file():
        try:
            model = joblib.load(str(p))
            print(f"Model loaded successfully from {p}\n")
            break
        except Exception as e:
            pass

if model is None:
    raise FileNotFoundError("Could not find random_forest_model.pkl in any candidate path.")

test_data = pd.DataFrame([
    [0.92, 0.15, 0.80, 0.75],   # frequent accesses
    [0.18, 0.91, 0.25, 0.30],   # very large reuse distance
    [0.45, 0.25, 0.93, 0.65],   # strong temporal locality
    [0.88, 0.35, 0.72, 0.55],   # high frequency accesses
    [0.30, 0.82, 0.40, 0.22],   # large reuse distance
], columns=[
    "access_frequency",
    "reuse_distance",
    "temporal_locality",
    "spatial_locality"
])

# Predict policies
predictions = model.predict(test_data)
probabilities = model.predict_proba(test_data)

print("Testing Cache Policy Predictions:\n")

for i in range(len(test_data)):
    workload = test_data.iloc[i].to_dict()
    confidence = max(probabilities[i]) * 100

    print(f"Workload {i+1}")
    print(workload)
    print("Recommended Policy:", predictions[i])
    print(f"Confidence: {confidence:.2f}%")
    print("-----------------------------------")