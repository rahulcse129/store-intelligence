import cv2
import numpy as np
from typing import List, Dict, Any, Tuple

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

class PersonDetector:
    def __init__(self, model_path: str = "yolov8n.pt"):
        self.model_path = model_path
        self.model = None
        if YOLO_AVAILABLE:
            try:
                # Load pre-trained nano YOLOv8 model (automatically downloads coco weights if missing)
                self.model = YOLO(model_path)
            except Exception as e:
                print(f"[Detector] Could not load YOLOv8 model: {e}. Falling back to simulation.")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs YOLOv8 person detection on a single CV2 image frame.
        Returns a list of dicts: [{"bbox": [x1, y1, x2, y2], "confidence": float}]
        """
        detections = []
        if self.model is None or frame is None:
            # Fallback mock simulation of person coordinates moving around
            return self._get_mock_detections()
            
        try:
            results = self.model(frame, verbose=False)[0]
            boxes = results.boxes
            
            for box in boxes:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                
                # Class 0 in COCO is 'person'
                if class_id == 0:
                    xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    detections.append({
                        "bbox": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                        "confidence": confidence
                    })
        except Exception as e:
            print(f"[Detector] Error running model inference: {e}. Falling back to simulation.")
            return self._get_mock_detections()

        return detections

    def _get_mock_detections(self) -> List[Dict[str, Any]]:
        """
        Returns mock person bounding boxes simulating movements inside a 1920x1080 frame.
        """
        # This will be orchestrated by run_pipeline.py which holds the actual simulated shopper state,
        # but as a default fallback we can spit out static bounding boxes.
        return [
            {"bbox": [200, 300, 300, 600], "confidence": 0.89},
            {"bbox": [800, 400, 900, 750], "confidence": 0.94}
        ]
