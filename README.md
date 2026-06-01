# Purplle Store Intelligence System ⚡

A high-performance, real-time Computer Vision and Backend analytics pipeline designed for Purplle Retail stores. It automatically tracks customer footprints, analyzes department engagement, filters employees, correlates POS register transactions, and monitors store anomalies (like checkout queue depths and dead zones).

---

## 🚀 Quick Start (Production Mode)

The entire system is completely containerized. You can launch the database, FastAPI backend, analytics pipeline, and Streamlit dashboard in a single command.

### 1. Build and Launch
Run the following command from the project root directory:

```bash
docker compose up --build
```

### 2. Verify Services
Once initialized, the services will be running on:
*   **FastAPI Backend & Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Streamlit Operations Dashboard**: [http://localhost:8501](http://localhost:8501)
*   **PostgreSQL Database Port**: `5432`

---

## 📦 Project Repository Structure

```text
store-intelligence/
├── pipeline/
│   ├── detect.py          # YOLOv8 Person detection layer
│   ├── tracker.py         # Pure-Python Bipartite IoU Tracker 
│   ├── zone_mapper.py     # Polygon Point-in-Polygon spatial mapping
│   ├── reid.py            # Cosine appearance embedding Re-ID
│   ├── staff_detector.py  # Torso color uniform & behavioral filters
│   ├── emit.py            # Async REST event queue emitter
│   └── run_pipeline.py    # Main camera extraction & Simulation loop
├── app/
│   ├── main.py            # FastAPI controller, routes & JSON logging
│   ├── database/          # SQLAlchemy session configurations
│   ├── models/            # SQLAlchemy database schemas
│   ├── schemas/           # Pydantic validation schemas
│   ├── services/          # Analytics aggregates & POS correlation
│   └── repositories/      # SQL database CRUD repository
├── dashboard/
│   └── app.py             # Streamlit real-time Plotly dashboard
├── docs/
│   ├── DESIGN.md          # Spatial math, Re-ID & logic architecture
│   └── CHOICES.md         # Technology justification reports
├── tests/                 # Full pytest integration test cases
├── docker-compose.yml     # Orchestration configs
├── Dockerfile             # Multi-stage container file
└── store_layout.json      # Polygon mapping coordinates
```

---

## 📡 Analytics API Overview

All core analytics APIs are fully documented on the Swagger router.

*   `POST /events/ingest`: Receives streaming batches of behavioral events. Validates payloads via Pydantic and filters out duplicates.
*   `GET /stores/{id}/metrics`: Returns unique visitor counts, average dwells, live checkout queue depths, and queue abandonment rates.
*   `GET /stores/{id}/funnel`: Progression funnels displaying absolute conversion drop-offs (Entry $\rightarrow$ Browse $\rightarrow$ Queue $\rightarrow$ Sale).
*   `GET /stores/{id}/heatmap`: Visits and dwell metrics per department.
*   `GET /stores/{id}/anomalies`: Computes live operational warnings (Queue Spikes, Dead Zones).
*   `GET /health`: Core health checks including stale CCTV stream alerts.

---

## ⚡ Video Processing vs. Simulation Modes

The background `pipeline` container is built with auto-detect logic:
*   **CCTV Video Mode**: If a raw CCTV video file is supplied inside the pipeline execution parameters, it runs YOLOv8 and tracks coordinates frame-by-frame.
*   **Auto-Simulation Mode**: If no footage is loaded, it boots in **High-Fidelity Simulation Mode**, generating random coordinates representing visitors walking through lobbies, shopping departments, checkout lines, and exiting. It regularly spawns register sales and cashiers to provide live, interactive dashboard metrics immediately on launch!
