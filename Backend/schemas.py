from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

class WorkloadInput(BaseModel):
    access_frequency: float = Field(..., ge=0.0, le=1.0, description="Normalized memory access frequency (0.0 to 1.0)")
    reuse_distance: float = Field(..., ge=0.0, le=1.0, description="Normalized reuse distance interval (0.0 to 1.0)")
    temporal_locality: float = Field(..., ge=0.0, le=1.0, description="Normalized temporal recency metric (0.0 to 1.0)")
    spatial_locality: float = Field(..., ge=0.0, le=1.0, description="Normalized spatial proximity metric (0.0 to 1.0)")

class PolicyResponse(BaseModel):
    workload_type: str
    predicted_policy: str
    hybrid_ratio: Optional[str] = None
    confidence: float
    reason: List[str]
    latency_gain: float
    throughput_gain: float
    workload_id: Optional[int] = None
    created_at: Optional[str] = None

class DashboardMetricsResponse(BaseModel):
    cache_hit_rate: float
    cache_miss_rate: float
    latency: float
    energy_usage: Optional[float] = 0.0
    power_consumption: Optional[float] = 0.0

class PolicyHistoryItem(BaseModel):
    workload_type: str
    policy: str
    timestamp: str

class ExplainableOutput(BaseModel):
    policy: str
    confidence: float
    reason: List[str]
