import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

class EventGenerator:
    def __init__(self, store_id: str, camera_id: str = "CAM_MAIN_01"):
        self.store_id = store_id
        self.camera_id = camera_id
        
        # State tracker: {visitor_id: {"current_zone": str, "zone_entry_time": float, "last_event_time": float}}
        self.visitor_states = {}

    def generate_events(self, 
                        visitor_id: str, 
                        current_zone: Optional[str], 
                        is_staff: bool, 
                        confidence: float,
                        timestamp: Optional[datetime] = None,
                        video_timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Processes a visitor's spatial position and returns a list of triggered behavioral events.
        """
        events = []
        now_dt = timestamp or datetime.utcnow()
        now_ts = now_dt.timestamp()

        # If this is a brand new visitor we haven't seen in this session
        if visitor_id not in self.visitor_states:
            self.visitor_states[visitor_id] = {
                "current_zone": None,
                "zone_entry_time": now_ts,
                "last_event_time": now_ts,
                "last_video_timestamp": video_timestamp
            }
            # 1. Trigger general store ENTRY event
            events.append(self._create_event_dict(
                visitor_id=visitor_id,
                event_type="ENTRY",
                zone_id=current_zone or "lobby",
                dwell_ms=0,
                is_staff=is_staff,
                confidence=confidence,
                timestamp=now_dt,
                video_timestamp=video_timestamp
            ))

        state = self.visitor_states[visitor_id]
        state["last_video_timestamp"] = video_timestamp
        old_zone = state["current_zone"]

        # Case 1: Visitor crossed into a new zone
        if current_zone != old_zone:
            # 2. Trigger ZONE_EXIT for the old zone if they were in one
            if old_zone:
                dwell_ms = int((now_ts - state["zone_entry_time"]) * 1000)
                events.append(self._create_event_dict(
                    visitor_id=visitor_id,
                    event_type="ZONE_EXIT",
                    zone_id=old_zone,
                    dwell_ms=dwell_ms,
                    is_staff=is_staff,
                    confidence=confidence,
                    timestamp=now_dt,
                    video_timestamp=video_timestamp
                ))
            
            # 3. Trigger ZONE_ENTER for the new zone if they walked into one
            if current_zone:
                state["current_zone"] = current_zone
                state["zone_entry_time"] = now_ts
                events.append(self._create_event_dict(
                    visitor_id=visitor_id,
                    event_type="ZONE_ENTER",
                    zone_id=current_zone,
                    dwell_ms=0,
                    is_staff=is_staff,
                    confidence=confidence,
                    timestamp=now_dt,
                    video_timestamp=video_timestamp
                ))
            else:
                state["current_zone"] = None

        # Case 2: Visitor is still inside the same zone (Trigger periodic DWELL telemetry)
        elif current_zone and current_zone == old_zone:
            dwell_ms = int((now_ts - state["zone_entry_time"]) * 1000)
            
            # Fire DWELL updates periodically (e.g. every 5 seconds) to avoid spamming the DB
            if now_ts - state["last_event_time"] >= 5.0:
                events.append(self._create_event_dict(
                    visitor_id=visitor_id,
                    event_type="ZONE_DWELL",
                    zone_id=current_zone,
                    dwell_ms=dwell_ms,
                    is_staff=is_staff,
                    confidence=confidence,
                    timestamp=now_dt,
                    video_timestamp=video_timestamp
                ))
                state["last_event_time"] = now_ts

        # Case 3: Visitor hits the exit portal
        if current_zone == "exit":
            events.append(self._create_event_dict(
                visitor_id=visitor_id,
                event_type="EXIT",
                zone_id="exit",
                dwell_ms=0,
                is_staff=is_staff,
                confidence=confidence,
                timestamp=now_dt,
                video_timestamp=video_timestamp
            ))
            # Clear visitor state
            if visitor_id in self.visitor_states:
                del self.visitor_states[visitor_id]

        return events

    def handle_lost_track(self, visitor_id: str, is_staff: bool, confidence: float) -> List[Dict[str, Any]]:
        """
        Triggers an EXIT event if a person's track has been permanently lost from the screen.
        """
        events = []
        if visitor_id in self.visitor_states:
            state = self.visitor_states[visitor_id]
            now_dt = datetime.utcnow()
            dwell_ms = int((now_dt.timestamp() - state["zone_entry_time"]) * 1000)
            video_timestamp = state.get("last_video_timestamp")
            
            # Close the last active zone
            if state["current_zone"]:
                events.append(self._create_event_dict(
                    visitor_id=visitor_id,
                    event_type="ZONE_EXIT",
                    zone_id=state["current_zone"],
                    dwell_ms=dwell_ms,
                    is_staff=is_staff,
                    confidence=confidence,
                    timestamp=now_dt,
                    video_timestamp=video_timestamp
                ))

            # Trigger general EXIT event
            events.append(self._create_event_dict(
                visitor_id=visitor_id,
                event_type="EXIT",
                zone_id="exit",
                dwell_ms=dwell_ms,
                is_staff=is_staff,
                confidence=confidence,
                timestamp=now_dt,
                video_timestamp=video_timestamp
            ))
            
            del self.visitor_states[visitor_id]
            
        return events

    def _create_event_dict(self, 
                           visitor_id: str, 
                           event_type: str, 
                           zone_id: str, 
                           dwell_ms: int, 
                           is_staff: bool, 
                           confidence: float,
                           timestamp: datetime,
                           video_timestamp: Optional[str] = None) -> Dict[str, Any]:
        """
        Helper to construct a dictionary matching exactly the Pydantic schema constraints.
        """
        return {
            "event_id": str(uuid.uuid4()),
            "store_id": self.store_id,
            "camera_id": self.camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "zone_id": zone_id,
            "dwell_ms": dwell_ms,
            "is_staff": is_staff,
            "confidence": round(confidence, 2),
            "metadata": {"video_timestamp": video_timestamp} if video_timestamp else {}
        }
