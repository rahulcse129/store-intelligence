import hashlib
import time
import cv2
import numpy as np
from typing import Dict, Any, List, Optional

class ReIDEngine:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        
        # In-memory database of active and historical visitor sessions
        # visitor_db: {visitor_id: {"embedding": np.ndarray, "last_seen": float, "last_known_bbox": list}}
        self.visitor_db = {}
        
        # Active mapping: {track_id: visitor_id}
        self.track_to_visitor = {}
        
        # Track-specific appearance cache: {track_id: embedding}
        self.track_embeddings = {}

    def _generate_mock_embedding(self, track_id: int, frame_patch: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Generates a stable, reproducible vector representing a person's clothing colors/appearance.
        If a frame patch is provided, it computes a normalized color histogram.
        Otherwise, it falls back to a deterministic, pseudo-random signature.
        """
        if frame_patch is not None and frame_patch.size > 0:
            # Generate a real color histogram (3 channels, 8 bins each = 24 dimensional vector)
            hist_features = []
            for i in range(3):
                hist = cv2.calcHist([frame_patch], [i], None, [8], [0, 256])
                cv2.normalize(hist, hist)
                hist_features.extend(hist.flatten().tolist())
            return np.array(hist_features, dtype=np.float32)
        
        # Fallback stable signature: Seeded by track_id to maintain consistency per track session
        np.random.seed(track_id)
        mock_vector = np.random.rand(16)
        return mock_vector / np.linalg.norm(mock_vector)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Computes cosine similarity between two vectors.
        """
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    def get_visitor_id(self, track_id: int, frame_patch: Optional[np.ndarray] = None) -> str:
        """
        Resolves a stable visitor ID for a given track session.
        Prevents double-counting by matching appearance embeddings against historical records.
        """
        now = time.time()
        
        # 1. If we already mapped this track in the current session, return it immediately
        if track_id in self.track_to_visitor:
            # Update last seen timestamp
            vis_id = self.track_to_visitor[track_id]
            self.visitor_db[vis_id]["last_seen"] = now
            return vis_id

        # 2. Extract or generate clothing appearance embedding
        embedding = self._generate_mock_embedding(track_id, frame_patch)
        self.track_embeddings[track_id] = embedding

        # 3. Search historical sessions to check if this person has re-entered (within last 10 minutes)
        best_match_id = None
        best_similarity = -1.0
        
        for vis_id, record in self.visitor_db.items():
            # Temporal window constraint: only match re-entries within 10 minutes
            if now - record["last_seen"] < 600:
                sim = self._cosine_similarity(embedding, record["embedding"])
                if sim > best_similarity:
                    best_similarity = sim
                    best_match_id = vis_id

        # 4. If similarity is high, re-associate the track with the historical visitor ID
        if best_similarity >= self.similarity_threshold and best_match_id:
            vis_id = best_match_id
            self.track_to_visitor[track_id] = vis_id
            self.visitor_db[vis_id]["embedding"] = (self.visitor_db[vis_id]["embedding"] + embedding) / 2.0  # rolling update
            self.visitor_db[vis_id]["last_seen"] = now
        else:
            # 5. Otherwise, generate a brand new unique visitor ID (Format: VIS_xxxxxx)
            md5_hash = hashlib.md5(f"visitor_{track_id}_{now}".encode('utf-8')).hexdigest()
            vis_id = f"VIS_{md5_hash[:6]}"
            
            # Register new visitor session
            self.visitor_db[vis_id] = {
                "embedding": embedding,
                "first_seen": now,
                "last_seen": now
            }
            self.track_to_visitor[track_id] = vis_id

        return vis_id
