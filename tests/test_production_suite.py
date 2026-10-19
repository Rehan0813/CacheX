import sys
import os
import io
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure Backend is in sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(repo_root, "Backend")
sys.path.insert(0, backend_dir)


print("=" * 70)
print("RUNNING CACHEX PRODUCTION READINESS VERIFICATION SUITE")
print("=" * 70)

# Test 1: Database and Model Loading
print("\n[TEST 1] Testing Database & ML Model Initialization...")
from database import engine, SessionLocal, Base
from policy_engine import rf_model, analyze_and_predict
from main import app
from fastapi.testclient import TestClient

assert engine is not None, "Database engine failed to initialize!"
assert rf_model is not None, "ML Model failed to load!"
print(f"  -> Database dialect in use: {engine.dialect.name}")
print(f"  -> ML Model classes: {rf_model.classes_}")
print("  -> TEST 1 PASSED: Zero-config DB & Model loaded cleanly.")

# Test 2: Verify the 4 Policy Scenarios
print("\n[TEST 2] Verifying 4 Workload Telemetry Scenarios...")

scenarios = [
    {"name": "LRU Scenario", "inputs": [0.35, 0.25, 0.92, 0.60], "expected": "LRU"},
    {"name": "LFU Scenario", "inputs": [0.95, 0.30, 0.55, 0.45], "expected": "LFU"},
    {"name": "FIFO Scenario", "inputs": [0.30, 0.95, 0.25, 0.90], "expected": "FIFO"},
    {"name": "Hybrid Scenario", "inputs": [0.61, 0.30, 0.50, 0.50], "expected": "Hybrid"},
]

for s in scenarios:
    f, r, t, spat = s["inputs"]
    res = analyze_and_predict(f, r, t, spat)
    policy = res["predicted_policy"]
    matched = (policy == s["expected"]) or (s["expected"] == "Hybrid" and "Hybrid" in policy)
    print(f"  -> {s['name']} {s['inputs']}: Predicted '{policy}', Confidence: {res['confidence']*100:.1f}%, Status: {'PASS' if matched else 'FAIL'}")
    assert matched, f"Scenario {s['name']} failed! Got {policy}"

print("  -> TEST 2 PASSED: All 4 ML prediction scenarios verified.")

# Test 3: API Endpoint Tests via TestClient
print("\n[TEST 3] Testing FastAPI Endpoints...")
client = TestClient(app)

# Health
r = client.get("/health")
assert r.status_code == 200, f"Health check failed: {r.status_code}"
print("  -> /health: 200 OK")

# Upload Workload Valid
payload = {
    "access_frequency": 0.35,
    "reuse_distance": 0.25,
    "temporal_locality": 0.92,
    "spatial_locality": 0.60
}
r = client.post("/upload_workload", json=payload)
assert r.status_code == 200, f"Upload workload failed: {r.text}"
w_id = r.json()["workload_id"]
print(f"  -> /upload_workload (valid [0.35, 0.25, 0.92, 0.60]): 200 OK (id={w_id})")

# Upload Workload Invalid (Bounds enforcement test: > 1.0)
r_invalid = client.post("/upload_workload", json={"access_frequency": 1.5, "reuse_distance": 0.1, "temporal_locality": 0.5, "spatial_locality": 0.5})
assert r_invalid.status_code == 422, f"Bounds validation failed to reject 1.5! Got status {r_invalid.status_code}"
print("  -> /upload_workload validation: 422 Rejected out-of-bounds input (as expected)")

# Analyze Workload
r = client.post(f"/analyze_workload?workload_id={w_id}")
assert r.status_code == 200, f"Analyze workload failed: {r.text}"
res = r.json()
assert res["predicted_policy"] == "LRU"
print(f"  -> /analyze_workload: 200 OK -> Predicted: {res['predicted_policy']} (Confidence: {res['confidence']*100:.1f}%)")

# Cache Metrics
r = client.get("/cache_metrics")
assert r.status_code == 200
print(f"  -> /cache_metrics: 200 OK (Hit rate: {r.json()['cache_hit_rate']*100:.1f}%)")

# Policy History
r = client.get("/policy_history")
assert r.status_code == 200
assert len(r.json()) > 0
print(f"  -> /policy_history: 200 OK ({len(r.json())} items retrieved safely)")

# Prefetch
r = client.post(f"/simulate_prefetch?workload_id={w_id}&pattern=A->B->C")
assert r.status_code == 200
print(f"  -> /simulate_prefetch: 200 OK (Pattern: A->B->C => Next: {r.json()['predicted_next_block']})")

# Test 4: File Ingestion with Missing Values / NaNs
print("\n[TEST 4] Testing CSV Upload with dirty data & NaNs...")
csv_content = """access_frequency,reuse_distance,temporal_locality,spatial_locality
0.45,0.20,0.95,0.75
NaN,,0.80,0.60
0.50,0.30,invalid_num,0.70
"""
file_data = io.BytesIO(csv_content.encode("utf-8"))
r = client.post("/upload_file", files={"file": ("test_trace.csv", file_data, "text/csv")})
assert r.status_code == 200, f"CSV upload with dirty data crashed! {r.text}"
print(f"  -> /upload_file: 200 OK (Cleaned dirty trace averages without crashing, ID={r.json()['workload_id']})")

print("\n" + "=" * 70)
print("ALL PRODUCTION READINESS CHECKS PASSED SUCCESSFULLY (100%)")
print("=" * 70)
