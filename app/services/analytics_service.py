from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.models.all_models import Store, Zone, VisitorSession, Event, Transaction, Anomaly
from app.repositories.data_repository import DataRepository
from app.schemas.all_schemas import (
    StoreMetricsOut, FunnelOut, FunnelStage, HeatmapOut, HeatmapZoneDetail, AnomalyOut
)

class AnalyticsService:

    @staticmethod
    def correlate_pos_transactions(db: Session, store_id: str) -> int:
        """
        Correlates billing zone visits with POS transactions.
        Rule: If a non-staff visitor was in the billing zone within 5 minutes before
        a transaction timestamp, mark the visitor as converted.
        Returns the number of newly converted sessions.
        """
        # Fetch all transactions that haven't been correlated yet (or just look at recent ones)
        transactions = db.query(Transaction).filter(Transaction.store_id == store_id).all()
        
        # Get billing zone events (ZONE_ENTER/ZONE_DWELL in billing zone)
        billing_events = db.query(Event).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone_id.ilike("%billing%") | Event.zone_id.ilike("%queue%")
        ).all()
        
        conversions_count = 0
        
        for tx in transactions:
            tx_time = tx.timestamp
            five_mins_before = tx_time - timedelta(minutes=5)
            
            # Find visitors in billing zone in that [tx_time - 5m, tx_time] window
            candidate_visitors = set()
            for event in billing_events:
                if five_mins_before <= event.timestamp <= tx_time:
                    candidate_visitors.add(event.visitor_id)
            
            # Update matching visitor sessions as converted
            if candidate_visitors:
                sessions = db.query(VisitorSession).filter(
                    VisitorSession.visitor_id.in_(list(candidate_visitors)),
                    VisitorSession.store_id == store_id,
                    VisitorSession.converted == False
                ).all()
                
                for sess in sessions:
                    sess.converted = True
                    conversions_count += 1
                    
        if conversions_count > 0:
            db.commit()
            
        return conversions_count

    @staticmethod
    def get_store_metrics(db: Session, store_id: str) -> StoreMetricsOut:
        """
        Calculates store metrics:
        - unique visitors (non-staff)
        - conversion rate (converted visitors / total visitors)
        - average dwell time
        - queue depth (current live billing zone queue count)
        - abandonment rate
        """
        # 1. Trigger correlation before serving metrics to ensure data freshness
        AnalyticsService.correlate_pos_transactions(db, store_id)

        # 2. Unique visitors (non-staff)
        total_visitors = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False
        ).count()

        # 3. Conversion Rate
        converted_visitors = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.converted == True
        ).count()
        
        conversion_rate = (converted_visitors / total_visitors) if total_visitors > 0 else 0.0

        # 4. Average Dwell (based on sum of all zone dwells for non-staff)
        avg_dwell_res = db.query(func.avg(Event.dwell_ms)).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.event_type == "ZONE_DWELL"
        ).scalar()
        
        average_dwell_ms = float(avg_dwell_res) if avg_dwell_res else 0.0

        # 5. Queue Depth (visitors in billing zone in the last 10 minutes who haven't exited)
        ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
        
        # Subquery to get each visitor's latest event in the billing zone
        latest_billing_events = db.query(
            Event.visitor_id,
            func.max(Event.timestamp).label("max_time")
        ).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone_id.ilike("%billing%") | Event.zone_id.ilike("%queue%"),
            Event.timestamp >= ten_mins_ago
        ).group_by(Event.visitor_id).subquery()

        # Count how many of these latest events were ZONE_ENTER or ZONE_DWELL (meaning they are still inside the zone)
        queue_count = db.query(Event).join(
            latest_billing_events,
            (Event.visitor_id == latest_billing_events.c.visitor_id) & (Event.timestamp == latest_billing_events.c.max_time)
        ).filter(
            Event.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"])
        ).count()

        # 6. Abandonment Rate (visited billing zone but did NOT convert)
        # Visitors who were in billing zone
        billing_visitors = db.query(Event.visitor_id).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone_id.ilike("%billing%") | Event.zone_id.ilike("%queue%")
        ).distinct().subquery()

        total_billing_visitors = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.visitor_id.in_(billing_visitors),
            VisitorSession.is_staff == False
        ).count()

        billing_converts = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.visitor_id.in_(billing_visitors),
            VisitorSession.is_staff == False,
            VisitorSession.converted == True
        ).count()

        abandonment_rate = (
            (total_billing_visitors - billing_converts) / total_billing_visitors
            if total_billing_visitors > 0
            else 0.0
        )

        return StoreMetricsOut(
            unique_visitors=total_visitors,
            conversion_rate=conversion_rate,
            average_dwell_ms=average_dwell_ms,
            queue_depth=queue_count,
            abandonment_rate=abandonment_rate
        )

    @staticmethod
    def get_store_funnel(db: Session, store_id: str) -> FunnelOut:
        """
        Funnel stages: Entry -> Zone Visit -> Billing Queue -> Purchase
        """
        # Ensure fresh conversions
        AnalyticsService.correlate_pos_transactions(db, store_id)

        # Stage 1: Entry (Total unique visitors entering)
        stage1_count = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False
        ).count()

        # Stage 2: Zone Visit (Entered any store zone)
        shopping_zones = db.query(Event.visitor_id).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]),
            ~Event.zone_id.ilike("%billing%"),
            ~Event.zone_id.ilike("%queue%"),
            Event.zone_id != None
        ).distinct().subquery()
        stage2_count = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.visitor_id.in_(shopping_zones),
            VisitorSession.is_staff == False
        ).count()

        # Stage 3: Billing Queue
        billing_zone = db.query(Event.visitor_id).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone_id.ilike("%billing%") | Event.zone_id.ilike("%queue%")
        ).distinct().subquery()
        stage3_count = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.visitor_id.in_(billing_zone),
            VisitorSession.is_staff == False
        ).count()

        # Stage 4: Purchase (Converted)
        stage4_count = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.converted == True
        ).count()

        stages = [
            FunnelStage(
                stage_name="Entry",
                count=stage1_count,
                percentage=100.0
            ),
            FunnelStage(
                stage_name="Zone Visit",
                count=stage2_count,
                percentage=(stage2_count / stage1_count * 100) if stage1_count > 0 else 0.0
            ),
            FunnelStage(
                stage_name="Billing Queue",
                count=stage3_count,
                percentage=(stage3_count / stage2_count * 100) if stage2_count > 0 else 0.0
            ),
            FunnelStage(
                stage_name="Purchase",
                count=stage4_count,
                percentage=(stage4_count / stage3_count * 100) if stage3_count > 0 else 0.0
            )
        ]

        return FunnelOut(store_id=store_id, stages=stages)

    @staticmethod
    def get_store_heatmap(db: Session, store_id: str) -> HeatmapOut:
        """
        Calculates visitation metrics per zone, including live occupancy.
        """
        zones = DataRepository.get_zones_by_store(db, store_id)
        
        heatmap_details = []
        frequencies = {}
        dwells = {}
        confidences = {}

        # Fetch all events once to process in-memory
        events = db.query(Event).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.zone_id != None
        ).all()

        # Calculate current live occupants inside each zone (visitors active in last 10m who haven't exited)
        ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
        latest_visitor_times = db.query(
            Event.visitor_id,
            func.max(Event.timestamp).label("max_time")
        ).filter(
            Event.store_id == store_id,
            Event.is_staff == False,
            Event.timestamp >= ten_mins_ago
        ).group_by(Event.visitor_id).subquery()
        
        active_visitor_states = db.query(
            Event.visitor_id,
            Event.zone_id,
            Event.event_type
        ).join(
            latest_visitor_times,
            (Event.visitor_id == latest_visitor_times.c.visitor_id) & 
            (Event.timestamp == latest_visitor_times.c.max_time)
        ).all()
        
        live_counts = {}
        for visitor_id, zone_id, event_type in active_visitor_states:
            if zone_id and event_type in ["ZONE_ENTER", "ZONE_DWELL"]:
                live_counts[zone_id] = live_counts.get(zone_id, 0) + 1

        for zone in zones:
            z_id = zone.zone_id
            z_events = [e for e in events if e.zone_id == z_id]
            
            # frequency = count of ZONE_ENTER events
            freq = len([e for e in z_events if e.event_type == "ZONE_ENTER"])
            frequencies[z_id] = freq

            # average dwell
            dwell_vals = [e.dwell_ms for e in z_events if e.event_type == "ZONE_DWELL"]
            dwells[z_id] = float(np.mean(dwell_vals)) if dwell_vals else 0.0

            # confidence indicator (average detection confidence score)
            conf_vals = [e.confidence for e in z_events]
            confidences[z_id] = float(np.mean(conf_vals)) if conf_vals else 0.0

        max_freq = max(frequencies.values()) if frequencies else 0

        for zone in zones:
            z_id = zone.zone_id
            norm_score = (frequencies[z_id] / max_freq) if max_freq > 0 else 0.0
            
            heatmap_details.append(
                HeatmapZoneDetail(
                    zone_id=z_id,
                    zone_name=zone.zone_name,
                    visit_frequency=frequencies[z_id],
                    live_occupancy=live_counts.get(z_id, 0),
                    average_dwell_ms=dwells[z_id],
                    normalized_score=norm_score,
                    confidence_indicator=confidences[z_id]
                )
            )

        return HeatmapOut(store_id=store_id, zones=heatmap_details)

    @staticmethod
    def detect_anomalies(db: Session, store_id: str) -> List[AnomalyOut]:
        """
        Runs anomaly detection heuristics:
        1. Queue Spike: Current queue depth > historical average * 1.5
        2. Conversion Drop: Today's conversion rate < 7-day moving average * 0.8
        3. Dead Zone: Any zone with zero events in the last 30 minutes
        """
        now = datetime.utcnow()
        active_anomalies = []

        # Fetch metrics to get current state
        metrics = AnalyticsService.get_store_metrics(db, store_id)

        # -- ANOMALY 1: QUEUE SPIKE DETECTION --
        # Historical queue depth average (last 24 hours)
        yesterday = now - timedelta(hours=24)
        avg_queue_depth = db.query(func.avg(Event.dwell_ms)).filter(
            Event.store_id == store_id,
            Event.zone_id.ilike("%billing%"),
            Event.timestamp >= yesterday
        ).scalar()
        
        # Mocking normal average if empty database
        avg_queue = float(avg_queue_depth / 1000) if avg_queue_depth else 2.0 
        threshold_factor = 1.5
        
        if metrics.queue_depth > (avg_queue * threshold_factor) and metrics.queue_depth > 3:
            db_anomaly = DataRepository.create_anomaly(
                db,
                store_id=store_id,
                anomaly_type="QUEUE_SPIKE",
                severity="WARN" if metrics.queue_depth < 8 else "CRITICAL",
                timestamp=now,
                suggested_action=f"Open billing register 2. Current queue depth is {metrics.queue_depth}."
            )
            active_anomalies.append(db_anomaly)

        # -- ANOMALY 2: CONVERSION DROP --
        # Get 7-day historical conversion rate average
        seven_days_ago = now - timedelta(days=7)
        past_converts = db.query(VisitorSession).filter(
            VisitorSession.store_id == store_id,
            VisitorSession.is_staff == False,
            VisitorSession.first_seen >= seven_days_ago
        ).all()
        
        if past_converts:
            total_past = len(past_converts)
            conv_past = len([s for s in past_converts if s.converted])
            avg_conv_rate = conv_past / total_past
        else:
            avg_conv_rate = 0.30  # Standard fallback index
            
        if metrics.conversion_rate < (avg_conv_rate * 0.7) and metrics.unique_visitors > 5:
            db_anomaly = DataRepository.create_anomaly(
                db,
                store_id=store_id,
                anomaly_type="CONVERSION_DROP",
                severity="CRITICAL",
                timestamp=now,
                suggested_action="Billing delays or long queues detected. Verify POS transaction feed and cashier staffing."
            )
            active_anomalies.append(db_anomaly)

        # -- ANOMALY 3: DEAD ZONE DETECTION --
        # Check zones that have 0 events in last 30 minutes
        thirty_mins_ago = now - timedelta(minutes=30)
        zones = DataRepository.get_zones_by_store(db, store_id)
        
        for zone in zones:
            event_count = db.query(Event).filter(
                Event.store_id == store_id,
                Event.zone_id == zone.zone_id,
                Event.timestamp >= thirty_mins_ago
            ).count()
            
            # Only trigger if there are active visitors in the store overall, to avoid empty store false positives
            active_visitors_in_store = db.query(VisitorSession).filter(
                VisitorSession.store_id == store_id,
                VisitorSession.last_seen >= thirty_mins_ago
            ).count()

            if event_count == 0 and active_visitors_in_store > 3:
                db_anomaly = DataRepository.create_anomaly(
                    db,
                    store_id=store_id,
                    anomaly_type="DEAD_ZONE",
                    severity="INFO",
                    timestamp=now,
                    suggested_action=f"Zone '{zone.zone_name}' has 0 active shoppers in the last 30 minutes. Check visual merchandising or physical access barriers."
                )
                active_anomalies.append(db_anomaly)

        # Fetch recent active anomalies to return
        db_anomalies = DataRepository.get_anomalies(db, store_id)
        return [AnomalyOut.from_orm(anom) for anom in db_anomalies]
