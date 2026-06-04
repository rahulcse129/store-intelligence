# Apex Retail Store Intelligence System ⚡

A production-grade, containerized Computer Vision and Business Intelligence analytics pipeline designed for **Apex Retail**. 

Apex Retail operates 40 physical stores across 8 cities. While their online channels benefit from mature, real-time analytics, their offline physical stores have historically been a complete data blind spot. This system resolves that blind spot by processing raw CCTV camera footage, translating pixel streams into structured behavioral telemetry, and exposing real-time operational analytics through a high-performance FastAPI backend and an interactive Streamlit operations dashboard.

---

## 🏗️ System Architecture

The system is designed as a decoupled, multi-process streaming pipeline running entirely in Docker:

```
  +------------------+     +--------------------+     +---------------------+
  | CCTV Video Clips | --> | YOLOv8 Person Det  | --> | Centroid/IoU Tracker|
  +------------------+     +--------------------+     +---------------------+
                                                                 |
                                                                 v
  +------------------+     +--------------------+     +---------------------+
  | Ingestion DB     | <-- | FastAPI Ingest API | <-- | Re-ID Appearance map|
  +--------+---------+     +--------------------+     +---------------------+
           |                                                     |
           v                                                     v
  +--------+---------+     +--------------------+     +---------------------+
  | Analytics Engine | --> | Streamlit Web UI   | <-- | Zone Polygon Mapper |
  +------------------+     +--------------------+     +---------------------+
```

*   **Stage 1: Detection & Tracking Layer**: Processes 1080p, 15fps CCTV clips. Utilizes YOLOv8 for person detection and a high-performance Bipartite IoU tracker to construct continuous spatial trajectories.
*   **Stage 2: Event Generator & Stream**: Maps visitor tracks to physical store zones (Skincare, Makeup, Billing, Lobbies, etc.) using Point-in-Polygon calculations. Emits structured events matching the required challenge schema.
*   **Stage 3: Intelligence API (FastAPI)**: Ingests batches of behavioral events, handles duplicate/idempotent data checking, persists state to PostgreSQL, correlates offline shoppers with POS cash register transactions, and exposes analytical endpoints.
*   **Stage 4: Live Operations Dashboard**: A luxury Streamlit-based web dashboard displaying real-time customer volume, conversion funnels, dwell-time heatmaps, live checkout queue depths, and operational anomaly warnings.

---

## 🚀 Quick Start (Production Setup)

The entire application stack is orchestrated via Docker Compose.

### 1. Build and Run
From the root directory of the repository, execute:
```bash
docker compose up --build
```
This automatically builds and runs:
*   `db`: PostgreSQL database with health checks configured.
*   `web`: FastAPI Backend API (exposed on port `8000`).
*   `pipeline`: Background AI worker that scans active cameras and processes video frames.
*   `dashboard`: Streamlit Web User Interface (exposed on port `8501`).

### 2. Access Ports & Services
*   **FastAPI Backend & Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Streamlit Operations Dashboard**: [http://localhost:8501](http://localhost:8501)
*   **PostgreSQL Database**: Port `5432` on localhost.

---

## 📡 Core API Endpoints

The API is fully containerized and production-ready:

*   `POST /events/ingest`: Batch ingestion of structured behavioral telemetry. Performs schema validation and discards duplicate events using db-level primary key constraints.
*   `POST /transactions`: Ingests sales transaction receipts to correlate with active shopper dwell paths.
*   `GET /stores/{id}/metrics`: Computes unique visitors, average dwell times, live billing queue depth, and conversion percentages.
*   `GET /stores/{id}/funnel`: Returns conversion funnel metrics (Entry $\rightarrow$ Browse $\rightarrow$ Queue $\rightarrow$ Transaction).
*   `GET /stores/{id}/heatmap`: Returns total visits and average dwell times grouped by physical product department.
*   `GET /stores/{id}/anomalies`: Identifies live operational bottlenecks (e.g., checkout queue depths exceeding threshold limits, dead zones with zero traffic).

---

## 📄 Automated Evaluation Framework (JSONL Output)

For automated grading and evaluation systems that do not run the API directly, the pipeline is configured to automatically append all emitted tracking data to a flat text file in the project root:
*   `events.jsonl`: Contains all generated telemetry events matching the exact challenge schema. This file is dynamically populated during `docker compose up` and serves as a static dataset for detection accuracy analysis.

---

## 📦 Project Directory Structure

```text
store-intelligence/
├── app/                  # FastAPI Application Code
│   ├── main.py           # API routing, JSON logging, and startup events
│   ├── database/         # PostgreSQL DB connection session lifecycle
│   ├── models/           # SQLAlchemy DB models (Stores, Events, Sessions)
│   ├── schemas/          # Pydantic schemas for request validation
│   ├── repositories/     # CRUD abstraction layer for SQL operations
│   └── services/         # POS correlation, metrics, and funnel calculations
├── pipeline/             # Computer Vision & Tracking Code
│   ├── detect.py         # YOLOv8 Person detector with simulation fallbacks
│   ├── tracker.py        # Centroid & Bipartite IoU bounding-box tracking
│   ├── zone_mapper.py    # Ray-Casting Point-in-Polygon spatial mapping
│   ├── reid.py           # Cosine-similarity color-histogram Re-ID engine
│   ├── staff_detector.py # HSV torso color filters & billing dwell checks
│   ├── emit.py           # Asynchronous API events emitter client
│   └── run_pipeline.py   # Main video stream loop and camera switches
├── dashboard/            # Operations Dashboard Code
│   └── app.py            # Streamlit Web UI & Plotly analytics charts
├── docs/                 # Challenge Technical Documentation
│   ├── DESIGN.md         # Detailed architectural design specifications
│   └── CHOICES.md        # Technical trade-offs & edge case solutions
├── tests/                # Automated API and integration test suites
├── docker-compose.yml    # Full service stack orchestration manifest
├── Dockerfile            # Optimized base docker image for PyTorch/OpenCV
└── store_layout.json     # CAD coordinate zone polygons (Master Template)
```
