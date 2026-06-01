import os
import time
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# Configure page metadata
st.set_page_config(
    page_title="Purplle Store Intelligence Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark theme overrides & premium CSS styling for luxury cosmetics brand Purplle
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Playfair+Display:ital,wght@0,600;0,800;1,400&display=swap');
    
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Outfit', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    
    .metric-card {
        background: #140828 !important; /* Extremely solid high-contrast purple-black background */
        border: 2px solid rgba(168, 85, 247, 0.7) !important; /* Thick bright purple border */
        padding: 16px;
        border-radius: 12px !important;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5) !important;
        transition: all 0.3s ease !important;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #EC4899 !important; /* Neon Pink highlight on hover */
        box-shadow: 0 10px 30px rgba(236, 72, 153, 0.3) !important;
    }
    
    .metric-title {
        font-size: 12px !important;
        color: #F3F4F6 !important; /* Extremely high-contrast crisp white title */
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        font-weight: 700 !important;
        margin-bottom: 6px !important;
    }
    
    .metric-value {
        font-size: 32px !important;
        font-weight: 800 !important;
        color: #00FFCC !important; /* Vibrant high-contrast neon green value */
        font-family: 'Outfit', sans-serif !important;
    }
    
    .anomaly-container {
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 8px;
        border-left: 5px solid;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.2s ease;
    }
    
    .anomaly-container:hover {
        transform: translateX(4px);
    }
    
    .severity-critical {
        background-color: #2D0A0E !important; /* Solid high-contrast red */
        border-left-color: #FF5A5F !important;
        border: 2px solid #FF5A5F !important;
    }
    
    .severity-warn {
        background-color: #2D1E0A !important; /* Solid high-contrast amber */
        border-left-color: #FFC107 !important;
        border: 2px solid #FFC107 !important;
    }
    
    .severity-info {
        background-color: #0A1E2D !important; /* Solid high-contrast sapphire blue */
        border-left-color: #00FFCC !important;
        border: 2px solid #00FFCC !important;
    }
    
    /* Elegant midnight sidebar styling override with extreme high-contrast text */
    [data-testid="stSidebar"] {
        background-color: #0A0212 !important;
        border-right: 2px solid rgba(168, 85, 247, 0.3);
    }
    
    /* Sidebar text force high-contrast white */
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h2 {
        color: #FFFFFF !important;
    }
    
    [data-testid="stSidebar"] p {
        color: #E2E2E9 !important;
        font-size: 13px !important;
        line-height: 1.4 !important;
    }
    
    /* Premium High-Contrast Button Styling Overrides */
    button, [data-testid="stSidebar"] button, .stButton>button {
        background-color: #A855F7 !important; /* Deep vibrant purple background */
        color: #FFFFFF !important; /* Bold, pure white text */
        border: 2px solid rgba(168, 85, 247, 0.6) !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 8px 16px !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5) !important;
        transition: all 0.2s ease !important;
    }
    
    button:hover, [data-testid="stSidebar"] button:hover, .stButton>button:hover {
        background-color: #EC4899 !important; /* Neon pink hover */
        color: #FFFFFF !important;
        border-color: #EC4899 !important;
        box-shadow: 0 4px 15px rgba(236, 72, 153, 0.4) !important;
    }

    /* Premium High-Contrast Selectbox overrides */
    div[data-testid="stSelectbox"] > div {
        background-color: #140828 !important;
        border: 2px solid rgba(168, 85, 247, 0.6) !important;
        border-radius: 8px !important;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        background-color: #140828 !important;
        border-radius: 8px !important;
        border: none !important;
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: #140828 !important;
        color: #FFFFFF !important;
    }

    /* Force selected text inside the selectbox input to be pure white and highly legible */
    div[data-testid="stSelectbox"] div[role="button"],
    div[data-testid="stSelectbox"] div[role="button"] div,
    div[data-testid="stSelectbox"] div[role="button"] span {
        color: #FFFFFF !important;
        background-color: #140828 !important;
        font-weight: 700 !important;
        font-size: 14px !important;
    }

    /* Style the selectbox options list popover */
    ul[role="listbox"], li[role="option"] {
        background-color: #140828 !important;
        color: #FFFFFF !important;
    }
    
    li[role="option"]:hover {
        background-color: #A855F7 !important;
        color: #FFFFFF !important;
    }

    /* Premium uploader styles */
    [data-testid="stFileUploader"] {
        background-color: #140828 !important;
        border: 2px dashed rgba(168, 85, 247, 0.5) !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    
    [data-testid="stFileUploader"] section {
        background-color: transparent !important;
    }

    [data-testid="stFileUploader"] label, [data-testid="stFileUploader"] p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }
</style>

""", unsafe_allow_html=True)


# Resolve FastAPI URL
API_URL = os.getenv("API_URL", "http://web:8000")
STORE_ID = "STORE_MUMBAI_01"

# Sidebar: POS Data Integration
st.sidebar.markdown("## 📥 Purplle POS Sales Integration")
st.sidebar.markdown(
    "Upload the official hackathon **Store Sales/POS spreadsheet (CSV)** "
    "to automatically correlate live customer CCTV dwell-times with actual cashier receipts in real-time."
)

uploaded_file = st.sidebar.file_uploader("Upload Store POS CSV", type=["csv"])
if uploaded_file is not None:
    try:
        # Load and clean CSV
        df = pd.read_csv(uploaded_file)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Identify critical columns in the spreadsheet
        col_id = next((c for c in df.columns if "order_id" in c or "transaction_id" in c), None)
        col_date = next((c for c in df.columns if "date" in c), None)
        col_time = next((c for c in df.columns if "time" in c), None)
        col_amount = next((c for c in df.columns if "total" in c or "gmv" in c or "amount" in c), None)
        
        if col_id and col_date and col_time and col_amount:
            st.sidebar.info("Processing POS records... Please wait.")
            success_count = 0
            total_sales_value = 0.0
            
            for _, row in df.iterrows():
                tx_id = str(row[col_id])
                date_str = str(row[col_date]).strip()
                time_str = str(row[col_time]).strip()
                
                # Normalize timestamp
                try:
                    dt = pd.to_datetime(f"{date_str} {time_str}", dayfirst=True)
                    iso_ts = dt.isoformat()
                except Exception:
                    iso_ts = datetime.utcnow().isoformat()
                
                try:
                    amt = float(row[col_amount])
                except ValueError:
                    amt = 0.0
                
                # POST transaction to FastAPI backend
                tx_res = requests.post(f"{API_URL}/transactions", json={
                    "transaction_id": tx_id,
                    "store_id": STORE_ID,
                    "timestamp": iso_ts,
                    "amount": amt
                }, timeout=2.0)
                
                if tx_res.status_code == 200:
                    success_count += 1
                    total_sales_value += amt
            
            st.sidebar.success(
                f"✅ Successful Integration!\n\n"
                f"*   **Transactions Ingested**: {success_count}\n"
                f"*   **Total Sales Volume**: ₹{total_sales_value:,.2f}\n"
                f"*   **POS Correlation**: Running in background..."
            )
        else:
            st.sidebar.error("Error: CSV must contain 'order_id', 'order_date', 'order_time', and 'total_amt' columns.")
    except Exception as e:
        st.sidebar.error(f"Error parsing POS data: {e}")

# Sidebar: Dashboard Refresh Controller
st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Dashboard Controls")

# CCTV Camera Source Selector
cctv_dir = "/app/CCTV Footage"
cctv_options = []
if os.path.exists(cctv_dir):
    try:
        cctv_options = sorted([f for f in os.listdir(cctv_dir) if f.endswith(".mp4")])
    except Exception:
        pass
if not cctv_options or len(cctv_options) < 5:
    cctv_options = ["CAM 1.mp4", "CAM 2.mp4", "CAM 3.mp4", "CAM 4.mp4", "CAM 5.mp4"]

current_active_cam = "CAM 1.mp4"
active_cam_file = "/app/active_camera.txt"
if os.path.exists(active_cam_file):
    try:
        with open(active_cam_file, "r") as f:
            current_active_cam = f.read().strip()
    except Exception:
        pass

if current_active_cam not in cctv_options:
    cctv_options.insert(0, current_active_cam)

# CCTV Quick Switch buttons
st.sidebar.markdown("### 📹 CCTV Quick Switch")
c1, c2, c3, c4, c5 = st.sidebar.columns(5)
button_selected_cam = None
with c1:
    if st.button("CAM 1", key="btn_cam1"):
        button_selected_cam = "CAM 1.mp4"
with c2:
    if st.button("CAM 2", key="btn_cam2"):
        button_selected_cam = "CAM 2.mp4"
with c3:
    if st.button("CAM 3", key="btn_cam3"):
        button_selected_cam = "CAM 3.mp4"
with c4:
    if st.button("CAM 4", key="btn_cam4"):
        button_selected_cam = "CAM 4.mp4"
with c5:
    if st.button("CAM 5", key="btn_cam5"):
        button_selected_cam = "CAM 5.mp4"

# Use button selection if pressed, else fall back to the currently active camera
selected_camera = current_active_cam
if button_selected_cam and button_selected_cam in cctv_options:
    selected_camera = button_selected_cam

if selected_camera != current_active_cam:
    try:
        with open(active_cam_file, "w") as f:
            f.write(selected_camera)
        st.sidebar.success(f"🎬 Switching feed to: {selected_camera}...")
        time.sleep(0.5)
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to switch camera: {e}")

refresh_mode = st.sidebar.selectbox(
    "Refresh Rate Selector",
    options=["Auto-Refresh (10s)", "Auto-Refresh (30s)", "Auto-Refresh (60s)", "Manual Refresh Only"],
    index=0
)
if refresh_mode == "Auto-Refresh (10s)":
    refresh_seconds = 10.0
elif refresh_mode == "Auto-Refresh (30s)":
    refresh_seconds = 30.0
elif refresh_mode == "Auto-Refresh (60s)":
    refresh_seconds = 60.0
else:
    refresh_seconds = None

anomaly_filter = st.sidebar.selectbox(
    "Anomaly Timeframe Filter",
    options=["Last 5 Minutes", "Last 15 Minutes", "Last 60 Minutes", "Show All (24h)"],
    index=0
)

if st.sidebar.button("🔄 Force Refresh Dashboard"):
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

if st.sidebar.button("🗑️ Reset Database & Telemetry"):
    try:
        reset_res = requests.post(f"{API_URL}/system/reset", timeout=5.0)
        if reset_res.status_code == 200:
            st.sidebar.success("✅ Database reset complete! Relogging events...")
            if os.path.exists(active_cam_file):
                try:
                    with open(active_cam_file, "w") as f:
                        f.write(selected_camera)
                except Exception:
                    pass
            time.sleep(0.5)
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
        else:
            st.sidebar.error("Failed to reset system data.")
    except Exception as e:
        st.sidebar.error(f"Error resetting database: {e}")

# App Header: Bespoke Premium Cosmetics header for Purplle
st.markdown("""
<div style="background: linear-gradient(135deg, #1C0A35 0%, #080111 100%); padding: 24px 30px; border-radius: 20px; border: 1px solid rgba(168, 85, 247, 0.25); margin-bottom: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.4); text-align: left;">
    <div style="font-family: 'Playfair Display', serif; font-size: 42px; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; line-height: 1.1;">
        purplle <span style="font-family: 'Outfit', sans-serif; font-weight: 300; font-size: 22px; color: #D4AF37; text-transform: uppercase; letter-spacing: 4px; margin-left: 10px; vertical-align: middle;">Store Intelligence</span>
    </div>
    <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #A9A9B3; margin-top: 8px; text-transform: uppercase; letter-spacing: 2px;">
        ✨ MUMBAI FLAGSHIP • REAL-TIME SPATIAL ANGLE TELEMETRY & CONVERSION INSIGHTS
    </div>
</div>
""", unsafe_allow_html=True)

# Top Banner: Connection & Health Check status
try:
    health_res = requests.get(f"{API_URL}/health", timeout=2.0).json()
    db_healthy = health_res.get("status") == "healthy"
    stale_feed = health_res.get("stale_feed_detected", False)
    
    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        if db_healthy:
            st.success("📡 CCTV Feeds: CONNECTED")
        else:
            st.error("📡 CCTV Feeds: OFFLINE")
            
    with col_h2:
        if stale_feed:
            st.warning("⚠️ CCTV Telemetry Feed: STALE")
        else:
            st.success("🟢 CCTV Telemetry Feed: HEALTHY")
            
    with col_h3:
        last_t = health_res.get("last_event_timestamp")
        if last_t:
            st.info(f"⏰ Last Ingestion Event: {last_t[:19].replace('T', ' ')}")
        else:
            st.info("⏰ Last Ingestion Event: None")
except Exception:
    st.error("❌ FastAPI Analytics Gateway: OFFLINE. Database connectivity failed.")
    st.stop()

st.write("---")

# Live Active Camera Banner
CAMERA_METADATA = {
    "CAM 1.mp4": {
        "title": "📷 Active: CAM 1 — Skincare & Premium Cosmetics",
        "description": "Monitoring EB Korean Skincare, The Face Shop, Good Vibes, DermDoc, Minimalist, Aqualogica, Central Makeup Station & Fragrance aisles."
    },
    "CAM 2.mp4": {
        "title": "📷 Active: CAM 2 — Main Storefront Aisle Overview",
        "description": "Full store walkthrough perspective including Entrance Lobby, Exit Vestibule, Maybelline, Faces Canada, Lakme, Colorbar & Skincare counters."
    },
    "CAM 3.mp4": {
        "title": "📷 Active: CAM 3 — Storefront Entrance Corridor (Outside)",
        "description": "Isolates the external glass doors, vestibule entry/exit corridor to prevent hallway ReID Re-Classification."
    },
    "CAM 4.mp4": {
        "title": "📷 Active: CAM 4 — Staff Storeroom & Stocks",
        "description": "Monitoring rolling inventory shelves, stacked cardboard deliveries, lockers, swivel chairs & water dispensers."
    },
    "CAM 5.mp4": {
        "title": "📷 Active: CAM 5 — POS Cashier Desk & Accessories",
        "description": "Checkout Point-of-Sale white desks, cashier workstations & accessories display racks."
    }
}

cam_meta = CAMERA_METADATA.get(selected_camera, {
    "title": f"📷 Active: {selected_camera}",
    "description": "Dynamic CCTV feed stream with hot-reloading spatial mapping polygons."
})

st.markdown(f"""
<style>
@keyframes blink {{
    0% {{ opacity: 0.3; }}
    50% {{ opacity: 1.0; }}
    100% {{ opacity: 0.3; }}
}}
.blink-dot {{
    background-color: #EC4899;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 10px #EC4899;
    animation: blink 1.5s infinite;
    margin-right: 12px;
    vertical-align: middle;
}}
</style>
<div style="background: linear-gradient(90deg, #1C0A35 0%, #080111 100%); border: 2px solid rgba(168, 85, 247, 0.4); border-radius: 12px; padding: 18px 24px; margin-bottom: 25px; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4); display: flex; align-items: center; justify-content: space-between;">
    <div style="display: flex; align-items: center;">
        <span class="blink-dot"></span>
        <div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 17px; font-weight: 800; color: #FFFFFF; letter-spacing: 0.5px; text-transform: uppercase;">
                {cam_meta['title']}
            </div>
            <div style="font-family: 'Outfit', sans-serif; font-size: 13px; color: #A9A9B3; margin-top: 4px; line-height: 1.4;">
                {cam_meta['description']}
            </div>
        </div>
    </div>
    <div style="background: rgba(168, 85, 247, 0.15); border: 2px solid #A855F7; color: #A855F7; font-weight: 800; font-size: 11px; padding: 6px 14px; border-radius: 6px; text-transform: uppercase; letter-spacing: 1.5px; font-family: 'Outfit', sans-serif;">
        🔴 AI ANALYZING LIVE
    </div>
</div>
""", unsafe_allow_html=True)

# Main Content Layout
col_metrics, col_funnel = st.columns([2, 3])

# Poll backend API for fresh metrics & heatmap details
try:
    heatmap = requests.get(f"{API_URL}/stores/{STORE_ID}/heatmap", timeout=2.0).json()
    zone_names = [z["zone_name"] for z in heatmap["zones"]]
    visit_freqs = [z["visit_frequency"] for z in heatmap["zones"]]
    avg_dwells = [z["average_dwell_ms"] / 1000.0 for z in heatmap["zones"]]
    norm_scores = [z["normalized_score"] for z in heatmap["zones"]]
    raw_zones = heatmap.get("zones", [])
    live_map = {z["zone_id"]: z.get("live_occupancy", 0) for z in raw_zones}
    total_live_shoppers = sum(live_map.values())
except Exception:
    zone_names = ["Makeup", "Perfume", "Checkout", "Entrance"]
    visit_freqs = [0, 0, 0, 0]
    avg_dwells = [0.0, 0.0, 0.0, 0.0]
    raw_zones = []
    live_map = {}
    total_live_shoppers = 0

try:
    metrics = requests.get(f"{API_URL}/stores/{STORE_ID}/metrics", timeout=2.0).json()
except Exception:
    metrics = {
        "unique_visitors": 0,
        "conversion_rate": 0.0,
        "average_dwell_ms": 0.0,
        "queue_depth": 0,
        "abandonment_rate": 0.0
    }

with col_metrics:
    st.markdown("#### Live Customer Traffic & Conversion Metrics")
    
    # Row 1: Today's Total vs Live Occupants
    r1_col1, r1_col2 = st.columns(2)
    with r1_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #A855F7;">
            <div class="metric-title">TOTAL VISITORS (TODAY)</div>
            <div class="metric-value" style="color: #A855F7; font-size: 26px; font-weight: 800;">{metrics['unique_visitors']}</div>
        </div>
        """, unsafe_allow_html=True)
    with r1_col2:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #00FFCC;">
            <div class="metric-title">CURRENTLY IN STORE (LIVE)</div>
            <div class="metric-value" style="color: #00FFCC; font-size: 26px; font-weight: 800;">{total_live_shoppers}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")
    
    # Row 2: Conversion Rate vs Billing Queue Depth
    r2_col1, r2_col2 = st.columns(2)
    with r2_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #10B981;">
            <div class="metric-title">STORE CONVERSION RATE</div>
            <div class="metric-value" style="color: #10B981; font-size: 26px; font-weight: 800;">{metrics['conversion_rate']*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    with r2_col2:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #FF5A5F;">
            <div class="metric-title">QUEUE DEPTH (CASHIER)</div>
            <div class="metric-value" style="color: #FF5A5F; font-size: 26px; font-weight: 800;">{metrics['queue_depth']}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")
    
    # Row 3: Queue Abandonment Rate vs Average Department Dwell
    r3_col1, r3_col2 = st.columns(2)
    with r3_col1:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #F59E0B;">
            <div class="metric-title">QUEUE ABANDONMENT RATE</div>
            <div class="metric-value" style="color: #F59E0B; font-size: 26px; font-weight: 800;">{metrics['abandonment_rate']*100:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    with r3_col2:
        avg_dwell_sec = metrics['average_dwell_ms'] / 1000.0
        st.markdown(f"""
        <div class="metric-card" style="border-left: 5px solid #3B82F6;">
            <div class="metric-title">AVG DEPARTMENT DWELL</div>
            <div class="metric-value" style="color: #3B82F6; font-size: 26px; font-weight: 800;">{int(avg_dwell_sec // 60)}m {int(avg_dwell_sec % 60)}s</div>
        </div>
        """, unsafe_allow_html=True)

# Fetch conversion funnel data
try:
    funnel = requests.get(f"{API_URL}/stores/{STORE_ID}/funnel", timeout=2.0).json()
    stages = [s["stage_name"] for s in funnel["stages"]]
    counts = [s["count"] for s in funnel["stages"]]
except Exception:
    stages = ["Entry", "Zone Visit", "Billing Queue", "Purchase"]
    counts = [0, 0, 0, 0]

with col_funnel:
    st.markdown("#### Visitor Conversion Funnel Progression")
    
    # Plotly Funnel Chart
    fig_funnel = go.Figure(go.Funnel(
        y=stages,
        x=counts,
        textinfo="value+percent initial",
        marker=dict(
            color=["#A855F7", "#EC4899", "#F59E0B", "#10B981"],
            line=dict(width=2, color="#3F3F56")
        )
    ))
    
    fig_funnel.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#A9A9B3"),
        margin=dict(l=40, r=40, t=10, b=10),
        height=320
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

st.write("---")

col_heatmap, col_anomalies = st.columns([3, 2])

# Fetch Heatmap data
try:
    heatmap = requests.get(f"{API_URL}/stores/{STORE_ID}/heatmap", timeout=2.0).json()
    zone_names = [z["zone_name"] for z in heatmap["zones"]]
    visit_freqs = [z["visit_frequency"] for z in heatmap["zones"]]
    avg_dwells = [z["average_dwell_ms"] / 1000.0 for z in heatmap["zones"]]
    norm_scores = [z["normalized_score"] for z in heatmap["zones"]]
except Exception:
    zone_names = ["Makeup", "Perfume", "Checkout", "Entrance"]
    visit_freqs = [0, 0, 0, 0]
    avg_dwells = [0.0, 0.0, 0.0, 0.0]

with col_heatmap:
    st.markdown("#### Store Physical Inferences & Department Heatmaps")
    tab_floor, tab_scatter = st.tabs(["🗺️ Live Store Digital Twin", "📈 Scatter Analytics"])
    
    with tab_floor:
        # Define physical layout layout grid based on the CAD plan
        layout_grid = {
            "entry": (0, 0, 1.5, 2, "Entrance Lobby"),
            "exit": (1.5, 0, 3, 2, "Exit Vestibule"),
            "billing": (8.5, 3, 10, 6, "Cash Counter"),
            "pmu": (8.5, 6, 10, 8.5, "Personal Makeup Unit"),
            "eb_korean": (0, 8, 1.25, 10, "EB Korean"),
            "the_face_shop": (1.25, 8, 2.5, 10, "Face Shop"),
            "good_vibes": (2.5, 8, 3.75, 10, "Good Vibes"),
            "dermdoc": (3.75, 8, 5, 10, "DermDoc"),
            "minimalist": (5, 8, 6.25, 10, "Minimalist"),
            "aqualogica": (6.25, 8, 7.5, 10, "Aqualogica"),
            "lakme_skin": (7.5, 8, 8.75, 10, "Lakme Skin"),
            "accessories": (8.75, 8, 10, 10, "Accessories"),
            "maybelline": (3, 0, 4.1, 2, "Maybelline"),
            "faces_canada": (4.1, 0, 5.2, 2, "Faces Canada"),
            "lakme_makeup": (5.2, 0, 6.3, 2, "Lakme Makeup"),
            "colorbar_sugar": (6.3, 0, 7.4, 2, "Colorbar Sugar"),
            "swiss_beauty": (7.4, 0, 8.5, 2, "Swiss Beauty"),
            "renee_ny_bae": (8.5, 0, 10, 2, "Renee & NYB"),
            "fragrance_nail": (2.5, 4, 4.5, 6, "Fragrance/Nail"),
            "makeup_unit": (5, 4, 7.5, 6, "Makeup Station"),
            "storeroom": (0, 3, 2.5, 6, "Staff Storeroom")
        }
        
        fig_map = go.Figure()
        
        # Max live occupants for color normalization (avoid divide by zero)
        raw_zones = heatmap.get("zones", []) if isinstance(heatmap, dict) else []
        freq_map = {z["zone_id"]: z["visit_frequency"] for z in raw_zones}
        live_map = {z["zone_id"]: z.get("live_occupancy", 0) for z in raw_zones}
        dwell_map = {z["zone_id"]: z["average_dwell_ms"]/1000.0 for z in raw_zones}
        
        max_live = max(live_map.values()) if live_map else 1
        annotations = []
        
        for zid, coords in layout_grid.items():
            x0, y0, x1, y1, display_name = coords
            freq = freq_map.get(zid, 0)
            live = live_map.get(zid, 0)
            dwell = dwell_map.get(zid, 0.0)
            
            # Calculate color intensity based on active live occupants
            intensity = live / max_live if max_live > 0 else 0
            # Color transition from dark slate to bright Purplle pink (#EC4899)
            r = int(30 + intensity * (236 - 30))
            g = int(30 + intensity * (72 - 30))
            b = int(46 + intensity * (153 - 46))
            color_str = f"rgb({r},{g},{b})"
            
            # Add a filled trace so that it responds to hover events and displays tooltip cleanly
            fig_map.add_trace(go.Scatter(
                x=[x0, x1, x1, x0, x0],
                y=[y0, y0, y1, y1, y0],
                fill="toself",
                fillcolor=color_str,
                line=dict(color="#3F3F56", width=2),
                mode="lines",
                name=display_name,
                text=f"<b>{display_name}</b><br>🟢 Live Shoppers: {live}<br>👥 Total Visited: {freq}<br>⏱️ Avg Dwell: {int(dwell)}s",
                hoverinfo="text",
                showlegend=False
            ))
            
            # Add labels showing Live Occupancy with a clean green dot
            annotations.append(dict(
                x=(x0 + x1)/2.0,
                y=(y0 + y1)/2.0,
                text=f"<b>{display_name}</b><br><span style='color:#00FFCC;'>🟢 {live} Live</span><br><span style='color:#A9A9B3; font-size:8px;'>👥 {freq} Tot</span>",
                showarrow=False,
                font=dict(size=9, color="#FFFFFF"),
                align="center"
            ))
            
        fig_map.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
            margin=dict(l=0, r=0, t=10, b=10),
            height=400,
            annotations=annotations
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with tab_scatter:
        # Build layout pandas df
        df_heatmap = pd.DataFrame({
            "Department": zone_names,
            "Visitor Registrations": visit_freqs,
            "Dwell Time (Sec)": avg_dwells
        })
        
        fig_heat = px.scatter(
            df_heatmap,
            x="Visitor Registrations",
            y="Dwell Time (Sec)",
            size="Visitor Registrations",
            color="Department",
            hover_name="Department",
            size_max=40,
            color_discrete_sequence=["#C072FF", "#EC4899", "#F59E0B", "#10B981", "#3B82F6"]
        )
        
        fig_heat.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#A9A9B3"),
            xaxis=dict(showgrid=True, gridcolor="#3F3F56", linecolor="#3F3F56"),
            yaxis=dict(showgrid=True, gridcolor="#3F3F56", linecolor="#3F3F56"),
            margin=dict(l=20, r=20, t=10, b=10),
            height=320
        )
        st.plotly_chart(fig_heat, use_container_width=True)

# Fetch active anomalies and apply timeframe filtering
try:
    raw_anomalies = requests.get(f"{API_URL}/stores/{STORE_ID}/anomalies", timeout=2.0).json()
    
    # Filter anomalies based on timeframe selector
    anomalies = []
    now = datetime.utcnow()
    for anomaly in raw_anomalies:
        try:
            a_time_str = anomaly["timestamp"].replace("Z", "")
            if "." in a_time_str:
                a_time = datetime.strptime(a_time_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            else:
                a_time = datetime.strptime(a_time_str, "%Y-%m-%dT%H:%M:%S")
                
            elapsed_mins = (now - a_time).total_seconds() / 60.0
            
            if anomaly_filter == "Last 5 Minutes" and elapsed_mins <= 5.0:
                anomalies.append(anomaly)
            elif anomaly_filter == "Last 15 Minutes" and elapsed_mins <= 15.0:
                anomalies.append(anomaly)
            elif anomaly_filter == "Last 60 Minutes" and elapsed_mins <= 60.0:
                anomalies.append(anomaly)
            elif anomaly_filter == "Show All (24h)":
                anomalies.append(anomaly)
        except Exception:
            anomalies.append(anomaly)
            
    # Sort by priority: severity first (CRITICAL > WARN > INFO), then by newest timestamp first
    severity_weight = {"CRITICAL": 3, "WARN": 2, "INFO": 1}
    anomalies.sort(key=lambda a: (severity_weight.get(a["severity"], 0), a["timestamp"]), reverse=True)
    
    # Strictly limit to top 2 most critical active anomalies
    anomalies = anomalies[:2]
except Exception:
    anomalies = []

with col_anomalies:
    st.markdown("#### Active Operational Anomalies")
    
    if not anomalies:
        st.success("✅ No operational anomalies currently detected. Floor flow is optimal.")
    else:
        for anomaly in anomalies:
            severity = anomaly["severity"].lower()
            severity_class = f"severity-{severity}"
            
            st.markdown(f"""
            <div class="anomaly-container {severity_class}">
                <div style="font-weight: bold; color: #FFFFFF; font-size: 13px; text-shadow: 0 1px 2px rgba(0,0,0,0.5);">
                    🚨 {anomaly['anomaly_type']} - {anomaly['severity']}
                </div>
                <div style="color: #FFFFFF; font-size: 11px; margin-top: 4px; line-weight: 700; line-height: 1.3;">
                    {anomaly['suggested_action']}
                </div>
                <div style="color: #E2E8F0; font-size: 9px; margin-top: 6px; font-weight: 600;">
                    Triggered: {anomaly['timestamp'][:19].replace('T', ' ')}
                </div>
            </div>
            """, unsafe_allow_html=True)

# Auto refresh trigger based on Sidebar Controller
if refresh_seconds:
    time.sleep(refresh_seconds)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()
