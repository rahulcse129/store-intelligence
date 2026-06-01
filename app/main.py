import time
import uuid
import json
import logging
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.database.session import engine, Base, get_db
from app.repositories.data_repository import DataRepository
from app.services.analytics_service import AnalyticsService
from app.models.all_models import Event, VisitorSession, Transaction, Anomaly
from app.schemas.all_schemas import (
    EventSchema, StoreCreate, StoreOut, ZoneCreate, ZoneOut, TransactionCreate,
    StoreMetricsOut, FunnelOut, HeatmapOut, AnomalyOut, HealthOut
)

# Initialize logging
logger = logging.getLogger("store_intel")
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Create Database tables (automatic schema sync for SQLite/Postgres in Docker)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Purplle Store Intelligence System API",
    description="Real-time CCTV visitor analytics and operational anomaly monitoring.",
    version="1.0.0"
)

# Middleware: Structured JSON Logging
@app.middleware("http")
async def json_logging_middleware(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Store trace_id in request state for downstream handlers to use
    request.state.trace_id = trace_id
    
    response = await call_next(request)
    
    latency = int((time.time() - start_time) * 1000)
    
    # Attempt to extract store_id from path parameters or query parameters
    store_id = request.path_params.get("id") or request.query_params.get("store_id") or ""
    
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": trace_id,
        "store_id": store_id,
        "endpoint": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "latency_ms": latency
    }
    
    logger.info(json.dumps(log_data))
    
    # Add trace ID to the response header
    response.headers["X-Trace-ID"] = trace_id
    return response


# Core REST Endpoints

@app.post("/events/ingest", response_class=JSONResponse)
async def ingest_events(events: List[EventSchema], db: Session = Depends(get_db)):
    """
    Batch ingestion endpoint for CCTV-generated behavioral events.
    Handles deduplication, validation, and partial success reporting.
    """
    success_count = 0
    duplicate_count = 0
    errors = []

    for event in events:
        try:
            # Check for duplicates in DB
            db_event = DataRepository.create_event(db, event)
            if db_event:
                success_count += 1
        except Exception as e:
            errors.append({"event_id": str(event.event_id), "error": str(e)})

    return JSONResponse(
        status_code=200 if not errors else 207,
        content={
            "success_count": success_count,
            "duplicate_count": duplicate_count,
            "errors": errors,
            "total_processed": len(events)
        }
    )


@app.get("/stores/{id}/metrics", response_model=StoreMetricsOut)
def get_store_metrics(id: str, db: Session = Depends(get_db)):
    """
    Exposes key metrics: Unique visitor count, conversion rate, queue depth, average dwell, and abandonment.
    """
    store = DataRepository.get_store(db, id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return AnalyticsService.get_store_metrics(db, id)


@app.get("/stores/{id}/funnel", response_model=FunnelOut)
def get_store_funnel(id: str, db: Session = Depends(get_db)):
    """
    Returns visitor progression funnel: Entry -> Shopping -> Billing Queue -> Purchase.
    """
    store = DataRepository.get_store(db, id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return AnalyticsService.get_store_funnel(db, id)


@app.get("/stores/{id}/heatmap", response_model=HeatmapOut)
def get_store_heatmap(id: str, db: Session = Depends(get_db)):
    """
    Generates normalized visitor dwell heatmaps per store zone.
    """
    store = DataRepository.get_store(db, id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return AnalyticsService.get_store_heatmap(db, id)


@app.get("/stores/{id}/anomalies", response_model=List[AnomalyOut])
def get_store_anomalies(id: str, db: Session = Depends(get_db)):
    """
    Triggers the anomaly engine to compute live anomalies (dead zones, conversion drops, queue spikes).
    """
    store = DataRepository.get_store(db, id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return AnalyticsService.detect_anomalies(db, id)


@app.get("/health", response_model=HealthOut)
def health_check(db: Session = Depends(get_db)):
    """
    Calculates overall system health, database accessibility, and checks for stale CCTV feeds.
    """
    stale_feed_detected = False
    last_event_time = None
    
    try:
        # Ping DB
        db.execute("SELECT 1")
        
        # Check overall feeds across all stores
        stores = DataRepository.get_all_stores(db)
        details = {}
        
        for store in stores:
            latest_time = DataRepository.get_latest_event_timestamp(db, store.store_id)
            if latest_time:
                # Update global latest event tracker
                if not last_event_time or latest_time > last_event_time:
                    last_event_time = latest_time
                
                # If no events in the last 15 minutes, feed is flagged as stale
                is_stale = datetime.utcnow() - latest_time > timedelta(minutes=15)
                details[store.store_id] = {
                    "last_event": latest_time.isoformat(),
                    "feed_healthy": not is_stale
                }
                if is_stale:
                    stale_feed_detected = True
            else:
                details[store.store_id] = {
                    "last_event": None,
                    "feed_healthy": False
                }
                stale_feed_detected = True
                
        return HealthOut(
            status="healthy",
            last_event_timestamp=last_event_time,
            stale_feed_detected=stale_feed_detected,
            details=details
        )
    except Exception as e:
        return HealthOut(
            status="unhealthy",
            last_event_timestamp=None,
            stale_feed_detected=True,
            details={"error": str(e)}
        )


# Setup / Bootstrapping Endpoints (For Hackathon Simplicity)

@app.post("/stores", response_model=StoreOut)
def create_store(store: StoreCreate, db: Session = Depends(get_db)):
    """
    Initializes a store configuration.
    """
    return DataRepository.create_store(db, store)


@app.post("/zones", response_model=ZoneOut)
def create_zone(zone: ZoneCreate, db: Session = Depends(get_db)):
    """
    Initializes a store zone boundary polygon.
    """
    return DataRepository.create_zone(db, zone)


@app.post("/transactions")
def create_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    """
    Simulates a POS sale transaction.
    """
    return DataRepository.create_transaction(db, tx)


@app.post("/system/reset")
def reset_system_data(db: Session = Depends(get_db)):
    """
    Deletes all transactional, event-based, visitor sessions, and anomaly records.
    Prepares the system for a fresh camera pipeline demonstration.
    """
    try:
        db.query(Anomaly).delete()
        db.query(Transaction).delete()
        db.query(Event).delete()
        db.query(VisitorSession).delete()
        db.commit()
        return {"status": "success", "message": "All database transactional records cleared successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")
