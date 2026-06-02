# System Architecture Design: Store Intelligence System

This document outlines the end-to-end system design, spatial mathematics, database schemas, and architectural blueprints for the **Apex Retail Store Intelligence System**.

---

## 1. End-to-End System Blueprint

The architecture is designed as a decoupled, multi-process streaming platform running containerized edge-to-cloud components:

```mermaid
sequenceDiagram
    autonumber
    actor Shopper as Customer / Staff
    participant Cam as CCTV Camera (Edge)
    participant Pipe as AI Ingestion Pipeline
    participant API as FastAPI Backend
    participant DB as PostgreSQL
    participant Dash as Streamlit Dashboard

    Shopper->>Cam: Walks through retail store
    Cam->>Pipe: Streams raw H.264/MP4 frame stream
    Note over Pipe: YOLOv8 Bounding Box Detection<br/>ByteTrack/IoU Spatial Tracking
    Pipe->>Pipe: Color Histogram Re-ID Mapping
    Pipe->>Pipe: Point-in-Polygon Zone Collision Checks
    Pipe->>API: POST /events/ingest (Batch JSON telemetry)
    Note over API: Idempotency & Deduplication Checks
    API->>DB: INSERT/UPSERT records
    Dash->>API: GET /stores/STORE_BLR_002/metrics (Poll loop)
    API->>DB: Execute distinct count & funnel queries
    DB-->>API: Return rows
    API-->>Dash: Return structured JSON
    Dash->>Dash: Refresh Heatmaps, Funnels & Alerts
```

---

## 2. Ingestion Pipeline & Computer Vision Mechanics

### A. Detection Layer & Spatial Bounding Box Tracking
*   **Object Detection (YOLOv8)**: The pipeline reads CCTV video frames (1080p, 15fps) and uses a pre-trained YOLOv8 model targeting class `0` (person) to generate bounding boxes $[X_{min}, Y_{min}, X_{max}, Y_{max}]$ with confidence scores.
*   **Bipartite IoU Tracking**: Bounding boxes are associated across consecutive frames using Intersection over Union (IoU) scores. A bipartite matching solver pairs tracks to maintain consistent local track IDs.

### B. Point-in-Polygon (PIP) Zone Mapping
To locate customers relative to physical retail counters (e.g., Skincare, Makeup, Billing) without using heavy external GIS libraries, the pipeline implements a native, Ray-Casting Point-in-Polygon (PIP) algorithm:
1.  **Coordinate Normalization**: Bounding boxes are normalized relative to frame height and width:
    $$x_n = \frac{x}{W}, \quad y_n = \frac{y}{H}$$
2.  **Floor Contact Extraction**: To represent where the shopper's feet contact the floor, the system evaluates the bottom-center coordinate of the bounding box:
    $$P_x = \frac{X_{1n} + X_{2n}}{2.0}, \quad P_y = Y_{2n}$$
3.  **Even-Odd Rule**: The Ray-Casting algorithm projects a horizontal ray from $P(P_x, P_y)$ and counts intersections with the polygon edges defined in `store_layout_camN.json`. If the intersection count is odd, the coordinate lies inside the zone.

### C. Visitor Re-Identification (Re-ID) & Double-Counting Prevention
Temporary occlusions (display racks, columns) or group crossings frequently split track trajectories, resulting in duplicate unique customer counts. The `ReIDEngine` resolves this:
*   **Color Histogram Signatures**: BGR color histograms (8 bins per channel, 512 total dimensions) are extracted from cropped person patches.
*   **Cosine Similarity**: When a track is lost and a new track is initialized nearby, the engine computes the cosine similarity between their color embeddings:
    $$\text{Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$$
*   **Temporal Association Gate**: If similarity exceeds a threshold ($\ge 0.85$) within a 10-minute sliding window, the new track is matched to the existing global `visitor_id`, preserving session continuity.

---

## 3. Database Schema Design

The normalized relational PostgreSQL schema supports fast analytical lookups, session history tracking, and transaction correlation:

```mermaid
erDiagram
    STORE ||--o{ ZONE : houses
    STORE ||--o{ VISITOR_SESSION : records
    STORE ||--o{ EVENT : captures
    STORE ||--o{ TRANSACTION : registers
    STORE ||--o{ ANOMALY : logs
    
    STORE {
        string store_id PK
        string location
        json layout_json
    }
    ZONE {
        string zone_id PK
        string store_id FK
        string zone_name
        json polygon_coordinates
    }
    VISITOR_SESSION {
        string visitor_id PK
        string store_id FK
        timestamp first_seen
        timestamp last_seen
        boolean is_staff
        boolean converted
    }
    EVENT {
        uuid event_id PK
        string store_id FK
        string camera_id
        string visitor_id FK
        string event_type
        timestamp timestamp
        string zone_id FK
        integer dwell_ms
        boolean is_staff
        float confidence
        json event_metadata
    }
    TRANSACTION {
        string transaction_id PK
        string store_id FK
        timestamp timestamp
        float amount
    }
    ANOMALY {
        uuid anomaly_id PK
        string store_id FK
        string anomaly_type
        string severity
        string message
        timestamp timestamp
        string suggested_action
    }
```

---

## 4. API & Analytics Business Logic

### A. Idempotent Event Ingestion
CCTV edge pipelines can lose network connections and re-transmit batches of events, creating duplicated logs. The API gateway solves this:
*   Every telemetry event has a unique `event_id` (UUID-v4) generated at the edge.
*   The database schema enforces a `PRIMARY KEY` on `event_id`.
*    Fast API catches Postgres unique-constraint exceptions silently and returns a `200 OK` or `207 Multi-Status`, discarding duplicate payloads without pipeline downtime or analytics corruption.

### B. Spatial-Temporal POS Transaction Correlation
Offline customer checkout events are correlated with digital sales transactions using a spatial-temporal window search:
*   **Correlation Heuristic**: A customer session is marked as `converted = True` if they resided in the `billing` zone within a **5-minute sliding window** preceding a register receipt timestamp (`pos_transactions.csv`).
*   **Calculation**:
    $$\text{Conversion Rate} = \frac{\text{Unique Converted Customer Sessions}}{\text{Total Unique Customer Sessions}}$$

### C. Live Operations Alerts (Operational Anomalies)
The engine evaluates store behavior on-demand:
1.  **Queue Spikes (`QUEUE_SPIKE`)**: Warns store management if more than 5 unique shoppers are dwelling inside the `billing` zone simultaneously.
2.  **Dead Zones (`DEAD_ZONE`)**: Alerts staff if a primary cosmetic display records zero traffic during peak shopping hours.
