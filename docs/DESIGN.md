# Store Intelligence System - Architecture & Design Specifications

This document outlines the detailed system architecture, spatial mathematics, operational telemetry design, and critical trade-offs made in building the Purplle Store Intelligence System.

---

### 1. Unified System Architecture

The Store Intelligence System operates as a decoupled, multi-process streaming pipeline. It separates heavy frame extraction and computer vision processing from fast web transaction routing.

```text
  +------------------+     +--------------------+     +---------------------+
  | CCTV Video Stream| --> | YOLOv8 Person Det  | --> | Centroid/IoU Tracker|
  +------------------+     +--------------------+     +---------------------+
                                                                 |
                                                                 v
  +------------------+     +--------------------+     +---------------------+
  | Ingestion DB     | <-- | FastAPI Ingest API | <-- | Re-ID Appearance map|
  +--------+---------+     +--------------------+     +---------------------+
           |                                                     |
           v                                                     v
  +--------+---------+     +--------------------+     +---------------------+
  | Analytics Engine | --> | Streamlit UI Panel | <-- | Zone Polygon Mapper |
  +------------------+     +--------------------+     +---------------------+
```

---

### 2. Spatial Heuristics & Zone Mapping

Rather than relying on resource-intensive, compilation-dependent geometric libraries (like GDAL or Shapely), this system implements a clean, native **Ray Casting Point-in-Polygon (PIP)** checker inside `pipeline/zone_mapper.py`.

#### Footprint Normalization
To ensure the pipeline is independent of raw camera resolutions (e.g., swapping a 720p stream for a 4K feed), all calculations utilize **normalized float coordinates** ($[0.0, 1.0]$).
*   **Target Point Isolation**: The bottom-center of the person's bounding box represents the contact point where they stand on the floor:
    $$P_x = \frac{X_1 + X_2}{2.0}, \quad P_y = Y_2$$
*   **Ray-Casting Algorithm**: The PIP checks whether a horizontal ray emitted from $P(P_x, P_y)$ intersects the polygon edges an odd number of times. If odd, the visitor is inside that zone.

---

### 3. Re-Identification & Double-Counting Prevention

Tracking loss (caused by temporary column occlusions or group crossings) typically leads to track restarts and visitor double-counting. 

#### Visual Feature Signatures
The `ReIDEngine` maintains a cache of active visitor visual embeddings:
*   When a new track is initialized, it extracts a BGR color histogram (8 bins per channel) representing the visitor's clothing features.
*   It computes **Cosine Similarity** against active historical records of the last 10 minutes:
    $$\text{Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
*   If similarity $\ge 0.85$, the tracker maps the new track to the existing visitor ID (e.g., `VIS_a91c7d`), maintaining continuous metrics and preventing duplicate unique visitor counts.

---

### 4. Staff Filtration Model

In-store analytics can be heavily skewed by store staff who move continuously across zones. 
*   **Torso color profiling**: The `StaffDetector` runs HSV mask calculations. If the dominant clothing colors fall into the Purplle corporate uniform ranges (purple/black) for $>30\%$ of their bounding box crop, the session is marked `is_staff = True`.
*   **Behavioral work zone analysis**: Cashiers standing behind checkout counter boundaries continuously for long frames without executing store transitions are automatically categorized as staff.
*   **DB Filtering**: In all analytical metrics (metrics, heatmap, funnel), the SQL repository enforces a `is_staff == False` query condition.

---

### 5. POS Transaction Correlation Heuristic

The POS Correlation Engine in `analytics_service.py` attributes purchases back to spatial sessions:
*   **Attribution Rule**: A non-staff visitor is marked as `converted = True` if they recorded a `ZONE_ENTER` or `ZONE_DWELL` inside the `billing` zone within a **5-minute sliding window** preceding a register purchase timestamp.
*   **Attribution Model**: It queries matched candidate visitor sessions, updates `converted=True` in the database, and uses this to yield precise Conversion Rates:
    $$\text{Conversion Rate} = \frac{\text{Unique Converted Visitors}}{\text{Total Unique Visitors}}$$
