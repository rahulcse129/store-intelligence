import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.session import Base

class Store(Base):
    __tablename__ = "stores"

    store_id = Column(String, primary_key=True, index=True)
    location = Column(String, nullable=False)
    layout_json = Column(JSON, nullable=True)  # Store polygons and coordinates configuration

    zones = relationship("Zone", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("VisitorSession", back_populates="store", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="store", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="store", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    zone_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False)
    zone_name = Column(String, nullable=False)
    polygon_coordinates = Column(JSON, nullable=False)  # List of points [[x1, y1], [x2, y2], ...]

    store = relationship("Store", back_populates="zones")


class VisitorSession(Base):
    __tablename__ = "visitor_sessions"

    visitor_id = Column(String, primary_key=True, index=True)  # VIS_xxxxxx
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False, index=True)
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)
    converted = Column(Boolean, default=False, nullable=False)

    store = relationship("Store", back_populates="sessions")
    events = relationship("Event", back_populates="visitor", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String, nullable=False)
    visitor_id = Column(String, ForeignKey("visitor_sessions.visitor_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)  # ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL
    timestamp = Column(DateTime, nullable=False, index=True)
    zone_id = Column(String, nullable=True)
    dwell_ms = Column(Integer, default=0, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, nullable=False)
    event_metadata = Column("metadata", JSON, nullable=True)

    visitor = relationship("VisitorSession", back_populates="events")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)

    store = relationship("Store", back_populates="transactions")


class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False, index=True)
    anomaly_type = Column(String, nullable=False)  # QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE
    severity = Column(String, nullable=False)  # INFO, WARN, CRITICAL
    timestamp = Column(DateTime, nullable=False, index=True)
    suggested_action = Column(String, nullable=False)

    store = relationship("Store", back_populates="anomalies")
