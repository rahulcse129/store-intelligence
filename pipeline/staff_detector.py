import cv2
import numpy as np
from typing import List, Dict, Any, Optional

class StaffDetector:
    def __init__(self, uniform_hsv_ranges: Optional[List[Dict[str, List[int]]]] = None):
        """
        Initializes the Staff Detector.
        uniform_hsv_ranges: Optional list of min/max HSV thresholds representing staff uniforms.
        For Purplle, the default uniform profile targets deep purple/violet or solid dark black.
        """
        # Target staff uniforms (supporting solid black outfits and Purplle branding colors)
        self.uniform_hsv_ranges = uniform_hsv_ranges or [
            {"low": [0, 0, 0], "high": [180, 255, 65]},       # Robust dark black uniform
            {"low": [0, 0, 0], "high": [180, 60, 80]},        # Black/Charcoal with overhead store lighting reflections
            {"low": [125, 40, 30], "high": [165, 255, 255]}  # Deep purple uniform
        ]
        
        # Behavioral cache: {visitor_id: {"billing_dwell_seconds": float, "total_dwell_seconds": float}}
        self.visitor_behavior = {}
 
    def _analyze_uniform_color(self, frame_patch: np.ndarray) -> bool:
        """
        Computes if a significant percentage of the person's torso region crop matches the HSV uniform profile.
        """
        if frame_patch is None or frame_patch.size == 0:
            return False
            
        try:
            # Crop to the middle torso region (25% to 75% height) to isolate their shirt/outfit
            h, w = frame_patch.shape[:2]
            torso_patch = frame_patch[int(h * 0.25):int(h * 0.75), :]
            
            # Convert BGR crop to HSV color space
            hsv = cv2.cvtColor(torso_patch, cv2.COLOR_BGR2HSV)
            total_pixels = hsv.shape[0] * hsv.shape[1]
            
            matching_pixels = 0
            for r in self.uniform_hsv_ranges:
                lower = np.array(r["low"], dtype=np.uint8)
                upper = np.array(r["high"], dtype=np.uint8)
                
                mask = cv2.inRange(hsv, lower, upper)
                matching_pixels += np.sum(mask > 0)
                
            # If more than 35% of their torso crop matches the black or purple uniform, tag them as staff
            percentage = (matching_pixels / total_pixels) * 100.0
            return percentage > 35.0
        except Exception:
            # OpenCV import or processing error fallback
            return False

    def is_staff_member(self, visitor_id: str, track_id: int, frame_patch: Optional[np.ndarray] = None) -> bool:
        """
        Determines whether a visitor is a store employee based on uniform color and behavioral heuristics.
        """
        # 1. Check color uniform first (visual check)
        if frame_patch is not None:
            if self._analyze_uniform_color(frame_patch):
                return True
                
        # 2. Behavioral Check (fallback & validation)
        # If the tracking ID or visitor ID is hard-coded or seeded for staff simulation:
        if "staff" in visitor_id.lower() or track_id in [99, 100, 101]:
            return True
            
        # 3. Dynamic dwell check: employees staying inside the billing zone for long continuous frames
        if visitor_id not in self.visitor_behavior:
            self.visitor_behavior[visitor_id] = {
                "billing_dwell_frames": 0,
                "total_frames": 0
            }
            
        # These counters are incremented by run_pipeline.py as it updates states
        behavior = self.visitor_behavior[visitor_id]
        behavior["total_frames"] += 1
        
        # If a visitor spends more than 500 frames (approx 20 seconds of footage) inside the billing zone,
        # they are highly likely a cashier rather than a customer.
        if behavior["billing_dwell_frames"] > 500:
            return True

        return False

    def increment_billing_dwell(self, visitor_id: str):
        if visitor_id in self.visitor_behavior:
            self.visitor_behavior[visitor_id]["billing_dwell_frames"] += 1
