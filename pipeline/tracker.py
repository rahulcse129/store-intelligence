import numpy as np
from typing import List, Dict, Any, Tuple

class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_lost: int = 30):
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost
        self.next_id = 1
        
        # tracks: {track_id: {"bbox": [x1,y1,x2,y2], "lost_count": int, "confidence": float}}
        self.tracks = {}

    @staticmethod
    def _calculate_iou(boxA: List[int], boxB: List[int]) -> float:
        """
        Calculates Intersection-over-Union of two bounding boxes.
        """
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea == 0:
            return 0.0

        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Updates the tracker with new detections.
        Returns a list of tracked people: [{"track_id": int, "bbox": [x1,y1,x2,y2], "confidence": float}]
        """
        # 1. Gather active tracks
        active_ids = [tid for tid, track in self.tracks.items() if track["lost_count"] == 0]
        
        matched_detections = set()
        matched_tracks = set()
        
        updated_tracks = []

        # 2. Match active tracks with new detections based on highest IoU
        if active_ids and detections:
            # Build IoU cost matrix
            cost_matrix = np.zeros((len(active_ids), len(detections)))
            for i, tid in enumerate(active_ids):
                for j, det in enumerate(detections):
                    cost_matrix[i, j] = self._calculate_iou(self.tracks[tid]["bbox"], det["bbox"])
            
            # Greedy matching
            for i, tid in enumerate(active_ids):
                best_det_idx = np.argmax(cost_matrix[i])
                best_iou = cost_matrix[i, best_det_idx]
                
                if best_iou >= self.iou_threshold and best_det_idx not in matched_detections:
                    matched_tracks.add(tid)
                    matched_detections.add(best_det_idx)
                    
                    # Update track info
                    self.tracks[tid]["bbox"] = detections[best_det_idx]["bbox"]
                    self.tracks[tid]["confidence"] = detections[best_det_idx]["confidence"]
                    self.tracks[tid]["lost_count"] = 0
                    
                    updated_tracks.append({
                        "track_id": tid,
                        "bbox": self.tracks[tid]["bbox"],
                        "confidence": self.tracks[tid]["confidence"]
                    })

        # 3. Handle unmatched active tracks (increment lost count)
        for tid in list(self.tracks.keys()):
            if tid not in matched_tracks:
                self.tracks[tid]["lost_count"] += 1
                
                # If track exceeds max_lost limit, delete it
                if self.tracks[tid]["lost_count"] > self.max_lost:
                    del self.tracks[tid]
                elif self.tracks[tid]["lost_count"] == 1:
                    # Return it for one frame as 'lost' prediction (or ignore it)
                    pass

        # 4. Handle unmatched new detections (assign new track IDs)
        for j, det in enumerate(detections):
            if j not in matched_detections:
                new_id = self.next_id
                self.next_id += 1
                
                self.tracks[new_id] = {
                    "bbox": det["bbox"],
                    "lost_count": 0,
                    "confidence": det["confidence"]
                }
                
                updated_tracks.append({
                    "track_id": new_id,
                    "bbox": det["bbox"],
                    "confidence": det["confidence"]
                })

        return updated_tracks
