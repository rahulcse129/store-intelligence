import json
import os
from typing import List, Dict, Any, Tuple, Optional

class ZoneMapper:
    def __init__(self, layout_path: str = "store_layout.json"):
        self.store_id = "UNKNOWN"
        self.zones = []
        
        if os.path.exists(layout_path):
            try:
                with open(layout_path, "r") as f:
                    layout_data = json.load(f)
                    self.store_id = layout_data.get("store_id", "UNKNOWN")
                    self.zones = layout_data.get("zones", [])
                print(f"[ZoneMapper] Successfully loaded {len(self.zones)} zones for store {self.store_id}.")
            except Exception as e:
                print(f"[ZoneMapper] Error reading layout file: {e}")
        else:
            print(f"[ZoneMapper] Store layout file '{layout_path}' not found. Initializing empty mapper.")

    @staticmethod
    def _is_point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
        """
        Ray-Casting Point-in-Polygon (PIP) algorithm (Even-Odd Rule).
        Determines if a normalized coordinate (x, y) lies inside a list of polygon vertices.
        """
        num_vertices = len(polygon)
        inside = False
        p1 = polygon[0]
        
        for i in range(1, num_vertices + 1):
            p2 = polygon[i % num_vertices]
            if y > min(p1[1], p2[1]):
                if y <= max(p1[1], p2[1]):
                    if x <= max(p1[0], p2[0]):
                        # Avoid division by zero
                        if p1[1] != p2[1]:
                            x_intersection = (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1]) + p1[0]
                        else:
                            x_intersection = p1[0]
                            
                        if p1[0] == p2[0] or x <= x_intersection:
                            inside = not inside
            p1 = p2
            
        return inside

    def get_zone_for_bbox(self, bbox: List[int], frame_width: int, frame_height: int) -> Optional[str]:
        """
        Computes which store zone the bottom-center of the person's bounding box belongs to.
        Returns the zone_id, or None if the person is not inside any registered zone.
        """
        if not self.zones:
            return None
            
        # Get bottom-center point (where the visitor's feet are touching the floor)
        px = (bbox[0] + bbox[2]) / 2.0
        py = bbox[3]
        
        # Normalize coordinates
        nx = px / frame_width
        ny = py / frame_height
        
        # Check polygons
        for zone in self.zones:
            polygon = zone["polygon_coordinates"]
            if self._is_point_in_polygon(nx, ny, polygon):
                return zone["zone_id"]
                
        return None
