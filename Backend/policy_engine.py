import joblib
import pandas as pd
import os
from pathlib import Path

# Configurable Model Path via Environment or Candidate Paths
env_model_path = os.getenv("MODEL_PATH")

base_dir = Path(__file__).resolve().parent

candidate_paths = [
    Path(env_model_path) if env_model_path else None,
    base_dir / "random_forest_model.pkl",
    base_dir / "ml_model" / "random_forest_model.pkl",
    base_dir.parent / "ml_model" / "random_forest_model.pkl",
    base_dir.parent / "Ml_Model" / "random_forest_model.pkl",
    base_dir.parent.parent / "ml_model" / "random_forest_model.pkl",
    base_dir.parent.parent / "Ml_Model" / "random_forest_model.pkl",
]

rf_model = None
for p in candidate_paths:
    if p and p.is_file():
        try:
            rf_model = joblib.load(str(p))
            print(f"ML Model loaded successfully from {p}.")
            break
        except Exception as e:
            print(f"Error loading ML model from {p}: {e}")

if rf_model is None:
    print("Warning: ML model file not found in any candidate path.")

def analyze_and_predict(access_frequency: float, reuse_distance: float, temporal_locality: float, spatial_locality: float):
    # Sanitize and clamp values to [0.0, 1.0]
    access_frequency = max(0.0, min(1.0, float(access_frequency)))
    reuse_distance = max(0.0, min(1.0, float(reuse_distance)))
    temporal_locality = max(0.0, min(1.0, float(temporal_locality)))
    spatial_locality = max(0.0, min(1.0, float(spatial_locality)))

    # Format input for the model
    input_data = pd.DataFrame([[
        access_frequency,
        reuse_distance,
        temporal_locality,
        spatial_locality
    ]], columns=["access_frequency", "reuse_distance", "temporal_locality", "spatial_locality"])
    
    # If model failed to load, return a fallback
    if not rf_model:
        return {
            "workload_type": "Unknown",
            "predicted_policy": "Hybrid",
            "hybrid_ratio": "LRU 50% LFU 50%",
            "confidence": 0.0,
            "reason": ["ML Model failed to load. Fallback to Hybrid."]
        }
        
    # Predict using the Random Forest Model
    prediction = rf_model.predict(input_data)[0]
    probabilities = rf_model.predict_proba(input_data)[0]
    confidence = float(max(probabilities))
    
    # Hybrid Cache Policy Generator:
    # If the top two probabilities are close (diff < 0.40), generate a hybrid policy
    sorted_probs = sorted(probabilities, reverse=True)
    top_indices = probabilities.argsort()[-2:][::-1]
    classes = rf_model.classes_
    
    hybrid_ratio = None
    if (sorted_probs[0] - sorted_probs[1]) < 0.40:
        hybrid_ratio = f"{classes[top_indices[0]]} {int(sorted_probs[0]*100)}% {classes[top_indices[1]]} {int(sorted_probs[1]*100)}%"
        main_policy = "Hybrid"
    else:
        main_policy = prediction

    # Determine workload type based on prediction
    workload_type = "AI" if prediction == "LFU" else "Database" if prediction == "LRU" else "Streaming" if prediction == "FIFO" else "Scientific"
    
    reasons = [f"ML Model predicted {prediction} with {confidence*100:.1f}% confidence"]
    if access_frequency > 0.7: reasons.append("High access frequency detected")
    if temporal_locality > 0.7: reasons.append("Strong temporal locality detected")
    if reuse_distance > 0.7: reasons.append("Large reuse distance detected")
    if hybrid_ratio: reasons.append("Hybrid pattern detected: Two policies show similar performance potential")
    
    # Calculate realistic performance gains based on features
    latency_gain = round(-(access_frequency * 15 + temporal_locality * 10), 1)
    throughput_gain = round((spatial_locality * 8 + confidence * 5), 1)

    return {
        "workload_type": workload_type,
        "predicted_policy": main_policy,
        "hybrid_ratio": hybrid_ratio,
        "confidence": confidence,
        "reason": reasons,
        "latency_gain": latency_gain,
        "throughput_gain": throughput_gain
    }
