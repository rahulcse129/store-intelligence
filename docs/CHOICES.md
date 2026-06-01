# Technical Choices & Trade-off Analysis

This document details the architectural decisions made during the design and implementation of the Store Intelligence System, highlighting alternatives considered and final justifications.

---

### 1. Object Detection Model Selection

*   **Final Choice**: **YOLOv8 Nano (`yolov8n.pt`)**
*   **Alternatives Considered**: YOLOv5, Haar Cascades, Faster R-CNN, MediaPipe.
*   **Trade-off Comparison**:
    *   *Haar Cascades*: High speed, but unacceptable false-positive rates under varying store lighting.
    *   *Faster R-CNN*: Extremely high bounding box accuracy, but too heavy to run real-time on edge devices or cheap CPU cloud instances.
    *   *YOLOv8 Nano*: The perfect sweet spot. At just ~3.2M parameters, it downloads instantly, handles crowded store floors and occlusions at >30 FPS on a standard CPU, and maintains a highly reliable mean Average Precision (mAP) for the person class.

---

### 2. Spatial Tracking Heuristic

*   **Final Choice**: **Bipartite-Matching IoU / Centroid Tracker**
*   **Alternatives Considered**: DeepSORT, standard C++ ByteTrack, OpenCV trackers (KCF/CSRT).
*   **Justification**:
    *   *C++ ByteTrack / cython-bbox*: Extremely high accuracy, but represents a **notorious deployment bottleneck** because of C++ compilation requirements (`gcc`, `g++`, `lap` binding issues) inside Docker Alpine or Slim images. It routinely breaks cross-platform deploys (e.g., swapping between Windows hosts and Linux containers).
    *   *Native IoU Tracker*: A pure Python implementation utilizing NumPy and greedy bipartite cost matching. It has **zero binary compilation requirements**, runs natively on Windows/Linux containers, operates with negligible CPU overhead, and manages track ID persistence and occlusions elegantly through a custom `max_lost` threshold.

---

### 3. API & Schema Validation Layer

*   **Final Choice**: **FastAPI + Pydantic v2**
*   **Alternatives Considered**: Flask + Marshmallow, Node.js + Express + Joi.
*   **Justification**:
    *   *FastAPI*: Standard choice for asynchronous, high-throughput Python backends. It natively compiles schemas, provides out-of-the-box Swagger documentation, and achieves speeds comparable to Go and Node.js.
    *   *Pydantic*: Directly compiles the required ingestion schema, guarantees strict data-typing, sanitizes datetime strings, and returns clean, informative error arrays for malformed payloads.

---

### 4. UI Dashboard Architecture

*   **Final Choice**: **Streamlit + Plotly**
*   **Alternatives Considered**: React.js / Vue.js + Chart.js, Grafana.
*   **Justification**:
    *   *React.js*: Beautiful design control, but represents too much developer overhead and setup complexity for a 24-hour hackathon, introducing unnecessary routing and bundle configuration layers.
    *   *Streamlit*: Perfect for rapid prototyping. By integrating Plotly for interactive funnel rendering and custom CSS styling (dark-mode borders and alerts), we get a premium, responsive dashboard UI out of the box in a single Python file, connecting seamlessly to our REST API.
