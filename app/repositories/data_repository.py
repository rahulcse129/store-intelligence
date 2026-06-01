from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from app.models.all_models import Store, Zone, VisitorSession, Event, Transaction, Anomaly
from app.schemas.all_schemas import StoreCreate, ZoneCreate, EventSchema, TransactionCreate

class DataRepository:
    
    # Store methods
    @staticmethod
    def create_store(db: Session, store_in: StoreCreate) -> Store:
        db_store = db.query(Store).filter(Store.store_id == store_in.store_id).first()
        if db_store:
            db_store.location = store_in.location
            db_store.layout_json = store_in.layout_json
        else:
            db_store = Store(
                store_id=store_in.store_id,
                location=store_in.location,
                layout_json=store_in.layout_json
            )
            db.add(db_store)
        db.commit()
        db.refresh(db_store)
        return db_store

    @staticmethod
    def get_store(db: Session, store_id: str) -> Optional[Store]:
        return db.query(Store).filter(Store.store_id == store_id).first()

    @staticmethod
    def get_all_stores(db: Session) -> List[Store]:
        return db.query(Store).all()

    # Zone methods
    @staticmethod
    def create_zone(db: Session, zone_in: ZoneCreate) -> Zone:
        db_zone = db.query(Zone).filter(Zone.zone_id == zone_in.zone_id).first()
        if db_zone:
            db_zone.zone_name = zone_in.zone_name
            db_zone.polygon_coordinates = zone_in.polygon_coordinates
        else:
            db_zone = Zone(
                zone_id=zone_in.zone_id,
                store_id=zone_in.store_id,
                zone_name=zone_in.zone_name,
                polygon_coordinates=zone_in.polygon_coordinates
            )
            db.add(db_zone)
        db.commit()
        db.refresh(db_zone)
        return db_zone

    @staticmethod
    def get_zones_by_store(db: Session, store_id: str) -> List[Zone]:
        return db.query(Zone).filter(Zone.store_id == store_id).all()

    @staticmethod
    def get_zone(db: Session, zone_id: str) -> Optional[Zone]:
        return db.query(Zone).filter(Zone.zone_id == zone_id).first()

    # VisitorSession methods
    @staticmethod
    def get_or_create_session(db: Session, store_id: str, visitor_id: str, timestamp: datetime, is_staff: bool) -> VisitorSession:
        session = db.query(VisitorSession).filter(
            VisitorSession.visitor_id == visitor_id,
            VisitorSession.store_id == store_id
        ).first()
        
        if not session:
            session = VisitorSession(
                visitor_id=visitor_id,
                store_id=store_id,
                first_seen=timestamp,
                last_seen=timestamp,
                is_staff=is_staff,
                converted=False
            )
            db.add(session)
        else:
            if timestamp < session.first_seen:
                session.first_seen = timestamp
            if timestamp > session.last_seen:
                session.last_seen = timestamp
            if is_staff:
                session.is_staff = True
        
        db.commit()
        db.refresh(session)
        return session

    # Event methods
    @staticmethod
    def create_event(db: Session, event_in: EventSchema) -> Event:
        # First ensure the visitor session exists or update it
        DataRepository.get_or_create_session(
            db, 
            store_id=event_in.store_id,
            visitor_id=event_in.visitor_id,
            timestamp=event_in.timestamp,
            is_staff=event_in.is_staff
        )

        db_event = db.query(Event).filter(Event.event_id == event_in.event_id).first()
        if db_event:
            return db_event  # Idempotent: return existing event

        db_event = Event(
            event_id=event_in.event_id,
            store_id=event_in.store_id,
            camera_id=event_in.camera_id,
            visitor_id=event_in.visitor_id,
            event_type=event_in.event_type,
            timestamp=event_in.timestamp,
            zone_id=event_in.zone_id,
            dwell_ms=event_in.dwell_ms,
            is_staff=event_in.is_staff,
            confidence=event_in.confidence,
            event_metadata=event_in.metadata
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event

    @staticmethod
    def get_latest_event_timestamp(db: Session, store_id: str) -> Optional[datetime]:
        event = db.query(Event).filter(Event.store_id == store_id).order_by(desc(Event.timestamp)).first()
        return event.timestamp if event else None

    # POS Transaction methods
    @staticmethod
    def create_transaction(db: Session, tx_in: TransactionCreate) -> Transaction:
        db_tx = db.query(Transaction).filter(Transaction.transaction_id == tx_in.transaction_id).first()
        if db_tx:
            return db_tx
        db_tx = Transaction(
            transaction_id=tx_in.transaction_id,
            store_id=tx_in.store_id,
            timestamp=tx_in.timestamp,
            amount=tx_in.amount
        )
        db.add(db_tx)
        db.commit()
        db.refresh(db_tx)
        return db_tx

    # Anomaly methods
    @staticmethod
    def create_anomaly(db: Session, store_id: str, anomaly_type: str, severity: str, timestamp: datetime, suggested_action: str) -> Anomaly:
        anomaly = Anomaly(
            store_id=store_id,
            anomaly_type=anomaly_type,
            severity=severity,
            timestamp=timestamp,
            suggested_action=suggested_action
        )
        db.add(anomaly)
        db.commit()
        db.refresh(anomaly)
        return anomaly

    @staticmethod
    def get_anomalies(db: Session, store_id: str, limit: int = 20) -> List[Anomaly]:
        return db.query(Anomaly).filter(Anomaly.store_id == store_id).order_by(desc(Anomaly.timestamp)).limit(limit).all()
