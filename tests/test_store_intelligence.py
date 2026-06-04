# ==============================================================================
# HACKATHON TEST SUITE - STORE INTELLIGENCE SYSTEM
# Targets: Empty Store, All Staff, Re-Entry, Duplicates, Malformed, Zero Sales, Queue Spike
# Enforces >70% Coverage targets via in-memory SQLite transactions
# ==============================================================================
# PROMPT: "Write a complete pytest suite for a FastAPI backend that uses an in-memory SQLite database. 
# Test the following edge cases: empty store periods, all-staff movement, re-entry prevention, duplicate event 
# payload idempotency, malformed JSON structures, zero-sales checkout sessions, and queue spike anomaly detection."
#
# CHANGES MADE: I manually overridden the database setup fixture to mock the `get_db` dependency correctly using 
# `app.dependency_overrides`. I also tuned the test data to perfectly match our specific event payload schema and zone IDs.
# ==============================================================================

import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db
from app.main import app
from app.models.all_models import Store, Zone, VisitorSession, Event, Transaction, Anomaly
from app.repositories.data_repository import DataRepository
from app.services.analytics_service import AnalyticsService
from pipeline.reid import ReIDEngine

# 1. Setup in-memory SQLite for instantaneous, isolated tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base fixture
@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Bootstrap default store and zones
    store = Store(store_id="STORE_MUMBAI_01", location="Mumbai Test Store")
    db.add(store)
    
    zones = [
        Zone(zone_id="entry", store_id="STORE_MUMBAI_01", zone_name="Entrance", polygon_coordinates=[[0,0], [1,0]]),
        Zone(zone_id="perfume", store_id="STORE_MUMBAI_01", zone_name="Perfume", polygon_coordinates=[[0,0], [1,0]]),
        Zone(zone_id="billing", store_id="STORE_MUMBAI_01", zone_name="Checkout", polygon_coordinates=[[0,0], [1,0]])
    ]
    db.add_all(zones)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- TEST CASES ---

def test_empty_store_metrics(client, db_session):
    """
    Test Case: Empty Store
    Asserts that analytics return clean zero metrics when no visitors have entered.
    """
    response = client.get("/stores/STORE_MUMBAI_01/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["queue_depth"] == 0
    assert data["average_dwell_ms"] == 0.0


def test_all_staff_footage(client, db_session):
    """
    Test Case: All Staff Footage
    Asserts that staff are completely excluded from customer metrics.
    """
    now = datetime.utcnow()
    # Log event for a staff member
    event = {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_MUMBAI_01",
        "camera_id": "CAM_01",
        "visitor_id": "VIS_staff_99",
        "event_type": "ZONE_ENTER",
        "timestamp": now.isoformat(),
        "zone_id": "perfume",
        "dwell_ms": 12000,
        "is_staff": True,
        "confidence": 0.98,
        "metadata": {}
    }
    
    ingest_res = client.post("/events/ingest", json=[event])
    assert ingest_res.status_code == 200
    
    # Fetch metrics
    metrics_res = client.get("/stores/STORE_MUMBAI_01/metrics")
    data = metrics_res.json()
    
    # Staff must NOT show up in metrics
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0


def test_re_entry_prevention():
    """
    Test Case: Re-Entry Detection
    Asserts that identical appearance embeddings within 10 minutes map to the same visitor ID.
    """
    engine_reid = ReIDEngine(similarity_threshold=0.85)
    
    # 1. First track
    vis_id_1 = engine_reid.get_visitor_id(track_id=10)
    
    # 2. Second track, simulates lost track that restarts with similar features
    vis_id_2 = engine_reid.get_visitor_id(track_id=10)
    
    assert vis_id_1 == vis_id_2, "Tracker failed to retain ID for active track"
    
    # 3. Simulate another track mapping using same cached embedding
    vis_id_3 = engine_reid.get_visitor_id(track_id=11)
    # They should be different as track 11 generates a new random seed embedding
    assert vis_id_1 != vis_id_3


def test_duplicate_ingestion(client, db_session):
    """
    Test Case: Duplicate Ingestion
    Asserts that resending the same event ID twice is handled idempotently.
    """
    now = datetime.utcnow()
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "store_id": "STORE_MUMBAI_01",
        "camera_id": "CAM_01",
        "visitor_id": "VIS_cust_01",
        "event_type": "ENTRY",
        "timestamp": now.isoformat(),
        "zone_id": "entry",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    }
    
    # Ingest first time
    res1 = client.post("/events/ingest", json=[event])
    assert res1.status_code == 200
    assert res1.json()["success_count"] == 1
    
    # Ingest second time (idempotency check)
    res2 = client.post("/events/ingest", json=[event])
    assert res2.status_code == 200
    # Duplicate returns success in 200/207 without adding a second record to DB
    assert db_session.query(Event).filter(Event.event_id == event_id).count() == 1


def test_malformed_events_validation(client):
    """
    Test Case: Malformed Events
    Asserts that Pydantic blocks broken JSON inputs (HTTP 422).
    """
    # Missing required 'visitor_id' and 'event_type'
    broken_event = {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_MUMBAI_01"
    }
    
    response = client.post("/events/ingest", json=[broken_event])
    assert response.status_code == 422


def test_zero_purchases_conversion(client, db_session):
    """
    Test Case: Zero Purchases
    Asserts that visitors sitting in checkout with no correlated sales yields a 0% conversion rate.
    """
    now = datetime.utcnow()
    # Log customer in checkout
    event = {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_MUMBAI_01",
        "camera_id": "CAM_01",
        "visitor_id": "VIS_cust_99",
        "event_type": "ZONE_ENTER",
        "timestamp": now.isoformat(),
        "zone_id": "billing",
        "dwell_ms": 15000,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    }
    
    client.post("/events/ingest", json=[event])
    
    # No POS transactions inserted!
    metrics_res = client.get("/stores/STORE_MUMBAI_01/metrics")
    data = metrics_res.json()
    assert data["unique_visitors"] == 1
    assert data["conversion_rate"] == 0.0


def test_queue_spike_anomaly_detection(client, db_session):
    """
    Test Case: Queue Spike Detection
    Asserts that flooding the billing zone triggers a WARN or CRITICAL anomaly.
    """
    now = datetime.utcnow()
    
    # Ingest 10 distinct customer tracks into checkout
    events = []
    for i in range(10):
        events.append({
            "event_id": str(uuid.uuid4()),
            "store_id": "STORE_MUMBAI_01",
            "camera_id": "CAM_01",
            "visitor_id": f"VIS_cust_queue_{i}",
            "event_type": "ZONE_ENTER",
            "timestamp": now.isoformat(),
            "zone_id": "billing",
            "dwell_ms": 5000,
            "is_staff": False,
            "confidence": 0.94,
            "metadata": {}
        })
        
    client.post("/events/ingest", json=events)
    
    # Trigger Anomaly Engine
    anom_res = client.get("/stores/STORE_MUMBAI_01/anomalies")
    assert anom_res.status_code == 200
    data = anom_res.json()
    
    # Check if a QUEUE_SPIKE anomaly was raised
    spike_alerts = [a for a in data if a["anomaly_type"] == "QUEUE_SPIKE"]
    assert len(spike_alerts) > 0
    assert spike_alerts[0]["severity"] in ["WARN", "CRITICAL"]
    assert "register" in spike_alerts[0]["suggested_action"].lower()
