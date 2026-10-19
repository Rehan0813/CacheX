from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
import os

from database import engine, get_db
import models
import schemas
from policy_engine import analyze_and_predict
from cache_engine import simulate_metrics
from prefetch_engine import analyze_pattern

from fastapi.middleware.cors import CORSMiddleware

# Initialize database schemas safely
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Database schema initialization error: {e}")

app = FastAPI(
    title="CacheX - Adaptive Cache Engine",
    description="Production-grade AI-driven adaptive cache policy classification and prefetch engine",
    version="1.0.0"
)

# CORS configuration
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

@app.get("/")
def root():
    return {"status": "ok", "service": "CacheX Adaptive Cache Engine", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/preview_csv")
async def preview_csv(file: UploadFile = File(...)):
    """
    Parses a CSV/JSON file and returns preview rows with exact normalized values.
    Limits preview to first 100 rows to prevent browser memory exhaustion.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")

    filename = file.filename.lower()

    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use CSV or JSON.")

        required_cols = ["access_frequency", "reuse_distance", "temporal_locality", "spatial_locality"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"File missing required columns: {', '.join(missing)}")

        # Clean, numeric-coerce, and clamp values between 0.0 and 1.0
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).clip(0.0, 1.0)

        total_rows = len(df)
        if total_rows == 0:
            raise HTTPException(status_code=400, detail="Uploaded file contains no data rows.")

        # Cap preview at 100 rows to prevent JSON serialization overload
        preview_data = df[required_cols].head(100).to_dict(orient="records")
        return {"columns": required_cols, "rows": preview_data, "total": total_rows}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


@app.post("/upload_file")
async def upload_workload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Ingests a CSV/JSON telemetry file, extracts sanitized feature averages, and runs ML analysis.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")

    filename = file.filename.lower()
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith('.json'):
            df = pd.read_json(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use CSV or JSON.")
        
        required_cols = ["access_frequency", "reuse_distance", "temporal_locality", "spatial_locality"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"File missing required columns: {', '.join(missing)}")

        # Clean non-numeric or missing data
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).clip(0.0, 1.0)

        if len(df) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file contains no data rows.")

        # Calculate feature averages from the trace
        avg_features = {
            "access_frequency": round(float(df["access_frequency"].mean()), 4),
            "reuse_distance": round(float(df["reuse_distance"].mean()), 4),
            "temporal_locality": round(float(df["temporal_locality"].mean()), 4),
            "spatial_locality": round(float(df["spatial_locality"].mean()), 4)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # 1. Store Ingested Workload
    new_workload = models.Workload(
        workload_type="Ingested Trace",
        **avg_features
    )
    db.add(new_workload)
    db.commit()
    db.refresh(new_workload)

    # 2. Run AI Analysis
    prediction = analyze_and_predict(**avg_features)
    
    # 3. Store AI Policy
    new_policy = models.Policy(
        workload_id=new_workload.id,
        predicted_policy=prediction["predicted_policy"],
        hybrid_ratio=prediction["hybrid_ratio"],
        confidence=prediction["confidence"],
        explanation="; ".join(prediction["reason"]),
        latency_gain=prediction["latency_gain"],
        throughput_gain=prediction["throughput_gain"]
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)

    created_at_str = new_policy.created_at.strftime("%Y-%m-%d %H:%M:%S IST") if new_policy.created_at else "Just now"

    return {
        "status": "success",
        "workload_id": new_workload.id,
        "filename": filename,
        "extracted_features": avg_features,
        "created_at": created_at_str,
        **prediction
    }

@app.post("/upload_workload", response_model=dict)
def upload_workload(workload: schemas.WorkloadInput, db: Session = Depends(get_db)):
    """
    Upload workload data with validated ranges (0.0 to 1.0).
    """
    new_workload = models.Workload(
        workload_type="Pending",
        access_frequency=workload.access_frequency,
        reuse_distance=workload.reuse_distance,
        temporal_locality=workload.temporal_locality,
        spatial_locality=workload.spatial_locality
    )
    db.add(new_workload)
    db.commit()
    db.refresh(new_workload)
    return {"message": "Workload uploaded successfully", "workload_id": new_workload.id}

@app.post("/analyze_workload", response_model=schemas.PolicyResponse)
def analyze_workload(workload_id: int, db: Session = Depends(get_db)):
    """
    Runs workload classification and policy prediction.
    Returns predicted policy and explanation.
    """
    workload = db.query(models.Workload).filter(models.Workload.id == workload_id).first()
    if not workload:
        raise HTTPException(status_code=404, detail="Workload not found")

    # Run Analysis using the ML Model
    prediction = analyze_and_predict(
        workload.access_frequency,
        workload.reuse_distance,
        workload.temporal_locality,
        workload.spatial_locality
    )

    # Update workload type based on prediction
    workload.workload_type = prediction["workload_type"]
    workload.confidence = prediction["confidence"]
    
    # Store predicted policy
    new_policy = models.Policy(
        workload_id=workload.id,
        predicted_policy=prediction["predicted_policy"],
        hybrid_ratio=prediction["hybrid_ratio"],
        confidence=prediction["confidence"],
        explanation="; ".join(prediction["reason"]),
        latency_gain=prediction["latency_gain"],
        throughput_gain=prediction["throughput_gain"]
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)

    created_at_str = new_policy.created_at.strftime("%Y-%m-%d %H:%M:%S IST") if new_policy.created_at else "Just now"

    return {
        **prediction,
        "workload_id": workload.id,
        "created_at": created_at_str
    }

@app.get("/cache_metrics", response_model=schemas.DashboardMetricsResponse)
def get_cache_metrics(db: Session = Depends(get_db)):
    """
    Returns metrics correlated with the latest uploaded workload.
    """
    latest_workload = db.query(models.Workload).order_by(models.Workload.timestamp.desc()).first()
    if latest_workload:
        return simulate_metrics(
            latest_workload.access_frequency,
            latest_workload.temporal_locality,
            latest_workload.spatial_locality
        )
    return simulate_metrics()

@app.get("/policy_history", response_model=List[schemas.PolicyHistoryItem])
def get_policy_history(db: Session = Depends(get_db)):
    """
    Returns previous policy predictions safely with null checks.
    """
    policies = db.query(models.Policy).order_by(models.Policy.created_at.desc()).limit(50).all()
    history = []
    for p in policies:
        ts = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "Recent"
        history.append({
            "workload_type": p.workload.workload_type if p.workload else "Unknown",
            "policy": p.predicted_policy,
            "timestamp": ts
        })
    return history

@app.get("/dashboard_data")
def get_dashboard_data(db: Session = Depends(get_db)):
    """
    Returns aggregated data for charts based on latest workload.
    """
    metrics = get_cache_metrics(db)
    history = get_policy_history(db)
    
    return {
        "metrics": metrics,
        "policy_history": history
    }

@app.post("/simulate_cache_metrics", response_model=schemas.DashboardMetricsResponse)
def sim_cache_metrics(workload_id: int, db: Session = Depends(get_db)):
    """
    Generate demo metrics and store them for a workload.
    """
    metrics = simulate_metrics()
    
    new_metric = models.CacheMetric(
        workload_id=workload_id,
        cache_hit_rate=metrics["cache_hit_rate"],
        cache_miss_rate=metrics["cache_miss_rate"],
        latency=metrics["latency"],
        energy_usage=metrics["energy_usage"],
        power_consumption=metrics["power_consumption"]
    )
    db.add(new_metric)
    db.commit()
    
    return metrics

@app.post("/simulate_prefetch", response_model=dict)
def simulate_prefetch(workload_id: int, pattern: str, db: Session = Depends(get_db)):
    """
    Detect simple access patterns and predict the next block.
    """
    prediction, confidence = analyze_pattern(pattern)
    
    # Store prediction
    db_pred = models.PrefetchPrediction(
        workload_id=workload_id,
        pattern=pattern,
        predicted_next_block=prediction,
        confidence=confidence
    )
    db.add(db_pred)
    db.commit()
    
    return {
        "pattern": pattern,
        "predicted_next_block": prediction,
        "confidence": confidence
    }
