from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Dict, List, Optional, Any

# Event Ingestion/Out Schema (Exact Match)
class EventSchema(BaseModel):
    event_id: UUID
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


# Store Config Schemas
class StoreCreate(BaseModel):
    store_id: str
    location: str
    layout_json: Optional[Dict[str, Any]] = None

class StoreOut(BaseModel):
    store_id: str
    location: str
    layout_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# Zone Config Schemas
class ZoneCreate(BaseModel):
    zone_id: str
    store_id: str
    zone_name: str
    polygon_coordinates: List[List[float]]

class ZoneOut(BaseModel):
    zone_id: str
    store_id: str
    zone_name: str
    polygon_coordinates: List[List[float]]

    class Config:
        from_attributes = True


# POS Transaction Schemas
class TransactionCreate(BaseModel):
    transaction_id: str
    store_id: str
    timestamp: datetime
    amount: float


# Analytics API Response Schemas
class StoreMetricsOut(BaseModel):
    unique_visitors: int
    conversion_rate: float
    average_dwell_ms: float
    queue_depth: int
    abandonment_rate: float


class FunnelStage(BaseModel):
    stage_name: str
    count: int
    percentage: float

class FunnelOut(BaseModel):
    store_id: str
    stages: List[FunnelStage]


class HeatmapZoneDetail(BaseModel):
    zone_id: str
    zone_name: str
    visit_frequency: int
    live_occupancy: int = 0
    average_dwell_ms: float
    normalized_score: float  # 0.0 to 1.0 (relative frequency)
    confidence_indicator: float

class HeatmapOut(BaseModel):
    store_id: str
    zones: List[HeatmapZoneDetail]


class AnomalyOut(BaseModel):
    anomaly_id: UUID
    store_id: str
    anomaly_type: str
    severity: str  # INFO, WARN, CRITICAL
    timestamp: datetime
    suggested_action: str

    class Config:
        from_attributes = True


# Health API Response Schema
class HealthOut(BaseModel):
    status: str
    last_event_timestamp: Optional[datetime] = None
    stale_feed_detected: bool
    details: Dict[str, Any] = Field(default_factory=dict)
