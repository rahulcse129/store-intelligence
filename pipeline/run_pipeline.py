import os
import cv2
import time
import json
import requests
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from pipeline.detect import PersonDetector
from pipeline.tracker import IoUTracker
from pipeline.reid import ReIDEngine
from pipeline.zone_mapper import ZoneMapper
from pipeline.staff_detector import StaffDetector
from pipeline.event_generator import EventGenerator
from pipeline.emit import EventEmitter

class StoreIntelligencePipeline:
    def __init__(self, video_path: Optional[str] = None):
        self.video_path = video_path
        
        # Load zone configuration
        self.zone_mapper = ZoneMapper("store_layout.json")
        self.store_id = self.zone_mapper.store_id
        
        # Initialize modules
        self.detector = PersonDetector()
        self.tracker = IoUTracker()
        self.reid = ReIDEngine()
        self.staff_detector = StaffDetector()
        self.event_gen = EventGenerator(store_id=self.store_id)
        self.emitter = EventEmitter()
        
        # Simulation parameters
        self.simulation_mode = video_path is None or not os.path.exists(video_path)
        self.simulated_shoppers = {} # track_id: state
        self.frame_count = 0
        
        # Auto bootstrap database
        self.bootstrap_store()

    def bootstrap_store(self, layout_path: str = "store_layout.json"):
        """
        Auto-bootstraps store layout & zones in the database on initialization or camera switch.
        """
        print(f"[Pipeline] Bootstrapping store layout from {layout_path}...")
        api_url = os.getenv("API_URL", "http://web:8000")
        
        # Read from layout configuration
        try:
            with open(layout_path, "r") as f:
                layout = json.load(f)
                
            # Register store
            store_res = requests.post(f"{api_url}/stores", json={
                "store_id": layout["store_id"],
                "location": layout["location"],
                "layout_json": layout
            }, timeout=5.0)
            
            if store_res.status_code == 200:
                print(f"[Pipeline] Successfully bootstrapped Store: {layout['store_id']}")
                
            # Register individual zones
            for zone in layout["zones"]:
                zone_res = requests.post(f"{api_url}/zones", json={
                    "zone_id": zone["zone_id"],
                    "store_id": layout["store_id"],
                    "zone_name": zone["zone_name"],
                    "polygon_coordinates": zone["polygon_coordinates"]
                }, timeout=5.0)
                if zone_res.status_code == 200:
                    print(f"  -> Bootstrapped Zone: {zone['zone_id']}")
                    
        except Exception as e:
            print(f"[Pipeline] Bootstrapping failed (API offline?): {e}. Proceeding...")
 
    def run(self):
        """
        Main execution loop with dynamic camera switching support.
        """
        print("[Pipeline] Starting Purplle Store Intelligence Pipeline...")
        
        last_checked_camera = None
        
        while True:
            # Check for camera selection file `/app/active_camera.txt`
            active_cam_file = "/app/active_camera.txt"
            selected_video = None
            
            if os.path.exists(active_cam_file):
                try:
                    with open(active_cam_file, "r") as f:
                        cam_name = f.read().strip()
                        if cam_name:
                            # Resolve path inside mounted CCTV folder
                            potential_path = os.path.join("/app/CCTV Footage", cam_name)
                            if os.path.exists(potential_path):
                                selected_video = potential_path
                except Exception as e:
                    print(f"[Pipeline] Error reading active_camera.txt: {e}")
            
            # If no camera file selection, fallback to initial default_video
            if not selected_video:
                selected_video = self.video_path
                
            # If still no video, run in simulation mode
            if not selected_video or not os.path.exists(selected_video):
                print("[Pipeline] CCTV Video missing or offline. Running in high-fidelity SIMULATION Mode...")
                self.run_simulation()
                break # Simulation mode runs infinitely inside its own loop
                
            # If camera path changed or this is the first run
            if selected_video != last_checked_camera:
                print(f"\n[Pipeline] 🔄 SWITCHING ACTIVE CAMERA to: {os.path.basename(selected_video)}")
                last_checked_camera = selected_video
                self.frame_count = 0
                
                # Resolve layout file for active camera
                cam_basename = os.path.basename(selected_video) # e.g. "CAM 3.mp4"
                cam_id = cam_basename.split(".")[0].replace(" ", "").lower() # e.g. "cam3"
                layout_filename = f"store_layout_{cam_id}.json"
                if not os.path.exists(layout_filename):
                    layout_filename = "store_layout.json"
                
                print(f"[Pipeline] 🗺️ Loading camera-specific layout: {layout_filename}")
                self.zone_mapper = ZoneMapper(layout_filename)
                self.bootstrap_store(layout_filename)
                
                # Reset tracker/ReID to avoid cross-camera track contamination
                self.tracker = IoUTracker()
                self.reid = ReIDEngine()
                
            # Run one full pass of the video
            print(f"[Pipeline] Processing active camera feed: {selected_video}")
            self.run_video_processing(selected_video)
            
            # Brief pause before checking for camera change / restarting
            time.sleep(1.0)

    def run_video_processing(self, video_path: str):
        """
        Processes actual CCTV video footage frame-by-frame.
        """
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
            
        print(f"[Pipeline] Video properties: {width}x{height} pixels, {fps} FPS")
        
        while cap.isOpened():
            # Check for live camera switch request during execution
            if os.path.exists("/app/active_camera.txt"):
                try:
                    with open("/app/active_camera.txt", "r") as f:
                        cam_name = f.read().strip()
                        if cam_name and not video_path.endswith(cam_name):
                            print(f"[Pipeline] Mid-feed camera switch detected! Breaking current loop to load: {cam_name}")
                            break
                except Exception:
                    pass

            ret, frame = cap.read()
            if not ret:
                # Loop video when it finishes (highly elegant for long demos!)
                print("[Pipeline] Reached end of video feed. Looping back to the beginning...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
                
            self.frame_count += 1
            
            # Calculate elapsed time in video (MM:SS format)
            elapsed_seconds = self.frame_count / fps
            minutes = int(elapsed_seconds // 60)
            seconds = int(elapsed_seconds % 60)
            video_time_str = f"{minutes:02d}:{seconds:02d}"
            
            # Step 1: Detect people
            detections = self.detector.detect(frame)
            
            # Step 2: Track people across frames
            tracked_people = self.tracker.update(detections)
            
            active_visitor_ids = set()
            events_to_emit = []
            
            for person in tracked_people:
                bbox = person["bbox"]
                track_id = person["track_id"]
                confidence = person["confidence"]
                
                # Extract image crop patch for Re-ID and Color Uniform Checks
                crop = frame[bbox[1]:bbox[3], bbox[0]:bbox[2]]
                
                # Step 3: Re-ID to get stable visitor ID
                visitor_id = self.reid.get_visitor_id(track_id, crop)
                active_visitor_ids.add(visitor_id)
                
                # Step 4: Treat everyone purely as shoppers (no staff distinction)
                is_staff = False
                
                # Step 5: Zone Collision Check
                zone_id = self.zone_mapper.get_zone_for_bbox(bbox, width, height)
                
                # Step 6: Spatial state machine event triggers
                events = self.event_gen.generate_events(
                    visitor_id=visitor_id,
                    current_zone=zone_id,
                    is_staff=is_staff,
                    confidence=confidence,
                    video_timestamp=video_time_str
                )
                events_to_emit.extend(events)
            
            # Step 7: Check for lost tracks and trigger EXITs
            for tid in list(self.reid.track_to_visitor.keys()):
                if tid not in [p["track_id"] for p in tracked_people]:
                    vis_id = self.reid.track_to_visitor[tid]
                    is_staff = False
                    exit_events = self.event_gen.handle_lost_track(vis_id, is_staff, 0.90)
                    events_to_emit.extend(exit_events)
                    del self.reid.track_to_visitor[tid]
            
            # Step 8: Send events to Backend API
            if events_to_emit:
                self.emitter.emit_batch(events_to_emit)
                
            # Throttle processing slightly (simulate real-time framerate)
            time.sleep(0.033) # ~30 FPS
            
        cap.release()
        print("[Pipeline] CCTV Video processing finished.")

    def run_simulation(self):
        """
        Simulates custom shoppers, checkout queues, and sales events.
        """
        random.seed(42)
        next_track_id = 1
        
        # Staff stays active indefinitely
        staff_ids = ["VIS_staff_01", "VIS_staff_02"]
        
        # Seed initial checkout cashier
        self.emitter.emit_batch(self.event_gen.generate_events(
            visitor_id="VIS_staff_01",
            current_zone="billing",
            is_staff=True,
            confidence=0.99
        ))
        
        print("[Pipeline] Simulation loop running. Emitting real-time behavioral streams...")
        
        api_url = os.getenv("API_URL", "http://web:8000")
        
        while True:
            self.frame_count += 1
            events_to_emit = []
            now = datetime.utcnow()
            
            # Calculate elapsed simulation time in MM:SS
            elapsed_seconds = self.frame_count
            minutes = int(elapsed_seconds // 60)
            seconds = int(elapsed_seconds % 60)
            video_time_str = f"{minutes:02d}:{seconds:02d}"
            
            # 1. Periodically spawn new shoppers (ENTRY)
            if random.random() < 0.15 and len(self.simulated_shoppers) < 12:
                track_id = next_track_id
                next_track_id += 1
                
                # Mock pathing coordinates based on the detailed CAD layout zones
                brands = [
                    "eb_korean", "the_face_shop", "good_vibes", "dermdoc", "minimalist",
                    "aqualogica", "lakme_skin", "accessories", "maybelline", "faces_canada",
                    "lakme_makeup", "colorbar_sugar", "swiss_beauty", "renee_ny_bae",
                    "alps_goodness", "streax", "fragrance_nail", "makeup_unit", "pmu"
                ]
                selected_brands = random.sample(brands, k=random.randint(1, 3))
                path = ["entry"] + selected_brands + ["billing", "exit"]
                
                # Assign stable visitor ID
                vis_id = f"VIS_{random.randint(100000, 999999)}"
                
                self.simulated_shoppers[track_id] = {
                    "visitor_id": vis_id,
                    "path": path,
                    "path_index": 0,
                    "zone_dwell_frames": 0,
                    "target_dwell_frames": random.randint(20, 80),
                    "confidence": random.uniform(0.85, 0.98),
                    "is_staff": False
                }
                
            # 2. Update existing simulated shopper movements
            for tid in list(self.simulated_shoppers.keys()):
                shopper = self.simulated_shoppers[tid]
                shopper["zone_dwell_frames"] += 1
                
                current_zone = shopper["path"][shopper["path_index"]]
                
                # Generate events based on current spatial zone
                events = self.event_gen.generate_events(
                    visitor_id=shopper["visitor_id"],
                    current_zone=current_zone,
                    is_staff=shopper["is_staff"],
                    confidence=shopper["confidence"],
                    timestamp=now,
                    video_timestamp=video_time_str
                )
                events_to_emit.extend(events)
                
                # Transition to the next zone once target frames are met
                if shopper["zone_dwell_frames"] >= shopper["target_dwell_frames"]:
                    shopper["zone_dwell_frames"] = 0
                    shopper["target_dwell_frames"] = random.randint(30, 90)
                    shopper["path_index"] += 1
                    
                    # If they completed their path (exited the store)
                    if shopper["path_index"] >= len(shopper["path"]):
                        # Emit EXIT
                        exit_events = self.event_gen.handle_lost_track(
                            shopper["visitor_id"],
                            shopper["is_staff"],
                            shopper["confidence"]
                        )
                        events_to_emit.extend(exit_events)
                        
                        # Simulates POS purchase transaction with 65% conversion probability
                        # if they were in the billing zone before exiting
                        if current_zone == "billing" and random.random() < 0.65:
                            tx_id = f"TXN_{random.randint(100000, 999999)}"
                            tx_amount = round(random.uniform(500, 5000), 2)
                            try:
                                requests.post(f"{api_url}/transactions", json={
                                    "transaction_id": tx_id,
                                    "store_id": self.store_id,
                                    "timestamp": now.isoformat(),
                                    "amount": tx_amount
                                }, timeout=2.0)
                                print(f"[Simulation] Sale registered: {tx_id} - {tx_amount} Rs.")
                            except Exception:
                                pass
                        
                        # Remove visitor from simulation pool
                        del self.simulated_shoppers[tid]

            # 3. Queue Spike Anomaly Injector (Occurs occasionally on a 1% chance)
            # Floods the billing/checkout zone with mock tracks
            if random.random() < 0.01:
                print("[Simulation] INJECTING ANOMALY: Sudden check-out queue surge!")
                for i in range(8):
                    temp_track = next_track_id
                    next_track_id += 1
                    vis_id = f"VIS_surge_{random.randint(1000, 9999)}"
                    self.simulated_shoppers[temp_track] = {
                        "visitor_id": vis_id,
                        "path": ["billing", "billing", "exit"],
                        "path_index": 0,
                        "zone_dwell_frames": 0,
                        "target_dwell_frames": random.randint(80, 150),
                        "confidence": 0.95,
                        "is_staff": False
                    }

            # 4. Emit triggered behavioral telemetry
            if events_to_emit:
                self.emitter.emit_batch(events_to_emit)
                
            time.sleep(1.0) # Clock tick: 1 second per simulation cycle
            
if __name__ == "__main__":
    # Check if a specific video file is requested via environment variable (e.g., CAM 2.mp4)
    env_video = os.getenv("VIDEO_FILE")
    cctv_dir = "/app/CCTV Footage"
    default_video = None
    
    if env_video:
        # Check absolute or relative inside the CCTV folder
        if os.path.exists(env_video):
            default_video = env_video
        else:
            potential_path = os.path.join(cctv_dir, env_video)
            if os.path.exists(potential_path):
                default_video = potential_path
        if default_video:
            print(f"[Pipeline] Targeting camera video via VIDEO_FILE env: {default_video}")
            
    if not default_video and os.path.exists(cctv_dir):
        # Scan for mp4 video files
        videos = sorted([f for f in os.listdir(cctv_dir) if f.endswith(".mp4")])
        if videos:
            default_video = os.path.join(cctv_dir, videos[0])
            print(f"[Pipeline] Found CCTV footage inside mounted folder! Auto-targeting: {default_video}")
            
    pipeline = StoreIntelligencePipeline(video_path=default_video)
    pipeline.run()
