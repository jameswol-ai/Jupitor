import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Mock engine modules (replace with your real ones if available)
class ForexEngine:
    @staticmethod
    def get_live_indices():
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(20)]
        np.random.seed(42)
        ugx = 3750 + np.cumsum(np.random.normal(0, 2, 20))
        kes = 145 + np.cumsum(np.random.normal(0, 0.1, 20))
        ssp = 1100 + np.cumsum(np.random.normal(0, 5, 20))
        df = pd.DataFrame({
            "Time": times,
            "UGX/USD": np.round(ugx, 2),
            "KES/USD": np.round(kes, 2),
            "SSP/USD": np.round(ssp, 2)
        })
        return df

class SaiArchitect:
    @staticmethod
    def structural_check(beam_length, load, material="Steel"):
        if material == "Steel":
            moment = (load * beam_length**2) / 8
            capacity = 250
            utilization = moment / capacity
        else:
            moment = (load * beam_length**2) / 10
            capacity = 180
            utilization = moment / capacity
        return {
            "Design Moment (kNm)": round(moment, 2),
            "Capacity (kNm)": capacity,
            "Utilization Ratio": round(utilization, 2),
            "Status": "OK ✅" if utilization <= 1.0 else "FAIL ❌"
        }

st.set_page_config(page_title="Arc OS", layout="wide", initial_sidebar_state="expanded")

# Custom CSS (unchanged cool aesthetics)
def load_css():
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e0e0e0;
        }
        section[data-testid="stSidebar"] {
            background: rgba(20, 20, 40, 0.8);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255,255,255,0.1);
        }
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif;
            font-weight: 600;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(15px);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px 0 rgba(0,0,0,0.37);
        }
        .cool-button {
            background: linear-gradient(45deg, #ff416c, #ff4b2b);
            border: none;
            color: white;
            padding: 12px 28px;
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            border-radius: 50px;
            box-shadow: 0 0 20px rgba(255,75,43,0.5);
            transition: all 0.3s ease;
            cursor: pointer;
            display: inline-block;
            margin: 10px 0;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .cool-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(255,75,43,0.8);
            background: linear-gradient(45deg, #ff4b2b, #ff416c);
        }
        .cool-button:active {
            transform: scale(0.98);
        }
        .cool-button.secondary {
            background: linear-gradient(45deg, #00b4db, #0083b0);
            box-shadow: 0 0 20px rgba(0,180,219,0.5);
        }
        .cool-button.secondary:hover {
            box-shadow: 0 0 30px rgba(0,180,219,0.8);
        }
        .metric-box {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px;
            margin: 5px 0;
            text-align: center;
            font-weight: bold;
            border: 1px solid rgba(255,255,255,0.15);
        }
        /* Streamlit native button override */
        div.stButton > button {
            background: linear-gradient(45deg, #ff416c, #ff4b2b);
            border: none;
            color: white;
            padding: 12px 28px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 50px;
            box-shadow: 0 0 20px rgba(255,75,43,0.5);
            transition: all 0.3s ease;
            cursor: pointer;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            width: 100%;
            border: 1px solid rgba(255,255,255,0.2);
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(255,75,43,0.8);
            background: linear-gradient(45deg, #ff4b2b, #ff416c);
            color: white;
        }
        div.stButton > button:active {
            transform: scale(0.98);
        }
        div.stButton > button.secondary {
            background: linear-gradient(45deg, #00b4db, #0083b0);
            box-shadow: 0 0 20px rgba(0,180,219,0.5);
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# Persistent state
if 'arc_state' not in st.session_state:
    st.session_state.arc_state = {"market": None, "structural": None}
if 'forex_data' not in st.session_state:
    st.session_state.forex_data = ForexEngine.get_live_indices()
if 'arch_result' not in st.session_state:
    st.session_state.arch_result = None

# Sidebar
with st.sidebar:
    st.markdown("## ⚙️ Arc OS Control")
    mode = st.radio("🧠 **Intelligence Engine**", ["💱 Forex (Random)", "🏗️ Arch (Sai)"], index=0)
    st.markdown("---")
    st.caption("v2.0 · Aesthetic Overdrive")

st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System</h1>", unsafe_allow_html=True)

# ------------------ FOREX MODULE ------------------
if "Forex" in mode:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💹 Random: Forex Intelligence")
    st.markdown("*Live indices for UGX, KES, SSP (simulated)*")
    st.dataframe(st.session_state.forex_data.tail(10), use_container_width=True)

    # Native line chart with Time as x-axis
    st.line_chart(st.session_state.forex_data.set_index("Time"))

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("🔄 Refresh Live Data", key="forex_refresh"):
            st.session_state.forex_data = ForexEngine.get_live_indices()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------ ARCHITECTURE MODULE ------------------
else:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏛️ Sai: Architectural Synthesis")
    st.markdown("*Structural analysis & isometric projection*")

    col_input, col_viz = st.columns([1, 2])

    with col_input:
        st.markdown("### 📐 Design Parameters")
        beam_length = st.slider("Beam Length (m)", 2.0, 10.0, 5.0, 0.5)
        load = st.slider("Uniform Load (kN/m)", 1.0, 50.0, 20.0, 1.0)
        material = st.selectbox("Material", ["Steel", "Concrete"])

        if st.button("⚡ Run Structural Analysis", key="run_analysis"):
            st.session_state.arch_result = SaiArchitect.structural_check(beam_length, load, material)

        if st.session_state.arch_result:
            res = st.session_state.arch_result
            st.markdown("### 📊 Results")
            cols = st.columns(2)
            cols[0].metric("Design Moment", f"{res['Design Moment (kNm)']} kNm")
            cols[1].metric("Utilization", f"{res['Utilization Ratio']:.2f}",
                           delta="OK" if res['Status'].startswith("OK") else "FAIL",
                           delta_color="normal" if res['Status'].startswith("OK") else "inverse")
            st.markdown(f"**Status:** {res['Status']}")

    with col_viz:
        st.markdown("### 🧊 3D Isometric Projection")
        # Embedded SVG wireframe – no external dependencies
        svg_code = """
        <svg width="320" height="250" viewBox="0 0 320 250" xmlns="http://www.w3.org/2000/svg">
            <!-- Isometric grid -->
            <line x1="30" y1="200" x2="160" y2="50" stroke="#00d2ff" stroke-width="1.5" opacity="0.4"/>
            <line x1="160" y1="50" x2="290" y2="200" stroke="#00d2ff" stroke-width="1.5" opacity="0.4"/>
            <line x1="30" y1="200" x2="290" y2="200" stroke="#00d2ff" stroke-width="1.5" opacity="0.4"/>
            <!-- Vertical lines -->
            <line x1="30" y1="200" x2="30" y2="80" stroke="#ff4b2b" stroke-width="2"/>
            <line x1="160" y1="50" x2="160" y2="0" stroke="#ff4b2b" stroke-width="2"/>
            <line x1="290" y1="200" x2="290" y2="80" stroke="#ff4b2b" stroke-width="2"/>
            <!-- Top face -->
            <line x1="30" y1="80" x2="160" y2="0" stroke="#ff4b2b" stroke-width="2"/>
            <line x1="160" y1="0" x2="290" y2="80" stroke="#ff4b2b" stroke-width="2"/>
            <line x1="30" y1="80" x2="290" y2="80" stroke="#ff4b2b" stroke-width="2"/>
            <!-- Diagonals for style -->
            <line x1="30" y1="80" x2="160" y2="50" stroke="#ff4b2b" stroke-width="1" opacity="0.6"/>
            <line x1="160" y1="0" x2="160" y2="50" stroke="#ff4b2b" stroke-width="1" opacity="0.6"/>
            <line x1="290" y1="80" x2="160" y2="50" stroke="#ff4b2b" stroke-width="1" opacity="0.6"/>
            <!-- Nodes -->
            <circle cx="30" cy="200" r="4" fill="#00d2ff"/>
            <circle cx="160" cy="50" r="4" fill="#00d2ff"/>
            <circle cx="290" cy="200" r="4" fill="#00d2ff"/>
            <circle cx="30" cy="80" r="4" fill="#ff4b2b"/>
            <circle cx="160" cy="0" r="4" fill="#ff4b2b"/>
            <circle cx="290" cy="80" r="4" fill="#ff4b2b"/>
            <!-- Beam label -->
            <text x="140" y="230" fill="#aaa" font-size="12" text-anchor="middle">Structural Frame (Iso View)</text>
        </svg>
        """
        st.markdown(svg_code, unsafe_allow_html=True)
        st.caption("Interactive 3D engine available in full version")

    st.markdown('</div>', unsafe_allow_html=True)