# Engineering Choices & Trade-offs: Assessment Framework

This document outlines the critical technical choices, architectural trade-offs, and solutions to real-world edge cases implemented in the **Apex Retail Store Intelligence System**.

---

## 1. Core Architectural & Pipeline Choices

### A. OpenCV Color Histograms (Re-ID) vs. Heavy Deep Learning Re-ID Models
*   **Choice**: OpenCV BGR Color Histograms with Cosine Similarity comparisons.
*   **Trade-off & Rationale**:
    *   *Deep Learning Models (e.g., OSNet, TorchReID)*: Offer extreme light and pose invariance, but run at high latency on edge hardware ($>100\text{ms}$ per crop) and require heavy GPU dependencies.
    *   *OpenCV Color Histograms*: Compute instantaneously ($<1\text{ms}$ on CPU) and maintain high discriminative capacity in controlled retail indoor lighting.
    *   To keep the edge ingestion pipeline lightweight and suitable for CPU-only environments (without requiring CUDA runtimes), we chose color histograms, backed by a strict **10-minute temporal association decay gate** to prevent old, unrelated tracks from falsely matching.

### B. Lightweight Bipartite Intersection-over-Union (IoU) Tracker vs. DeepSORT
*   **Choice**: Optimized Bipartite Centroid + IoU overlap matching.
*   **Trade-off & Rationale**:
    *   *DeepSORT / StrongSORT*: Run Kalman filters and deep association features frame-by-frame, adding substantial computational overhead.
    *   *Bipartite IoU Tracker*: Performs pure matrix operations on bounding boxes. Since our input CCTV clips run at 15fps with relatively linear pedestrian motion, a simple IoU-based Hungarian solver performs tracking updates in $<0.2\text{ms}$ per frame while running safely on a single CPU core.

### C. PostgreSQL Relational Engine vs. NoSQL (MongoDB)
*   **Choice**: PostgreSQL.
*   **Trade-off & Rationale**:
    *   *NoSQL*: Lacks formal relational schemas and ACID guarantees, making transaction correlation brittle.
    *   *PostgreSQL*: Enforces strict foreign keys (e.g., ensuring events relate back to valid stores and zones). Crucially, PostgreSQL allows us to compute complex analytical aggregates (like funnel conversions and unique visitor overlaps) directly at the database engine level, minimizing CPU and memory usage in the API layer.

---

## 2. Solving Known Retail CCTV Edge Cases

| Edge Case / Challenge | Our Architectural Solution | Why It Works |
| :--- | :--- | :--- |
| **👥 Group Entry** (2-4 people entering together) | **Bipartite Bounding Box Matching** | Instead of counting pixel clusters or using density maps, the YOLOv8 detector isolates individual human shapes. The IoU tracker links these bounding boxes to separate, independent visitor IDs, preventing group clustering. |
| **👮 Staff Movement** | **HSV Torso Profiling & Cashier Dwell Filters** *(Optional Configuration)* | Store employees walk through all zones regularly, which can skew consumer dwell metrics. Our pipeline includes a torso-crop HSV uniform mask detector. It flags users wearing corporate attire (e.g., black/purple brand outfits) and allows the backend to dynamically exclude them from consumer metrics. |
| **🔄 Re-Entry** | **Temporal Re-ID Association Gate** | Shoppers who exit the store and return within a short window can inflate unique visitor counts. If a visitor is lost and a new one enters within 10 minutes, the Re-ID engine evaluates their color signature. If it matches ($\ge 0.85$ similarity), it merges their sessions under a single, stable visitor ID. |
| **🫣 Partial Occlusion** | **Centroid Fallbacks & Dwell Intercalation** | Display racks and columns hide shoppers. When a shopper is occluded, the IoU tracker projects their last known motion vector. If the track is briefly lost and recovered, the API's event generator interpolates the gap, maintaining a single continuous session. |
| **⏳ Billing Queue Buildup** | **Queue Depth & Abandonment Mechanics** | Using the `billing` zone coordinates, the system counts active unique visitors. If a shopper resides in the billing area but exits the store *without* a corresponding POS receipt in the subsequent 5-minute window, the system registers a `BILLING_QUEUE_ABANDON` event. |
| **📭 Empty Store Periods** | **Zero-Traffic Fail-Safe Ingestion** | Raw footage often contains 5-10 minute windows with no shoppers. Rather than locking or crashing, the API's transaction and query endpoints handle empty sets gracefully, returning empty lists and `0` metrics without throwing database null errors. |
| **📸 Camera Angle Overlap** | **Cross-Camera Re-ID Deduplication** | When the main floor camera overlaps with the entry camera, a visitor is visible in both. The Re-ID engine matches their visual color signature. If they are simultaneously detected in overlapping regions, the session is merged under one global ID, preventing double-counting. |

---

## 3. Base Image & Docker Optimizations

To improve development and deployment speeds on standard hardware:
*   **Base Image Caching**: The services were refactored to share a unified Docker base image (`store_intel_base:latest`). 
*   **Benefit**: This allows heavy libraries (like PyTorch, OpenCV, and Streamlit) to be compiled only once. Rebuilding or deploying individual microservices now takes **seconds** instead of hours, optimizing CPU, disk I/O, and deployment times.
