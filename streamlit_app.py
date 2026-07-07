import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Mock engine modules (replace with real ones from your repo if available)
class ForexEngine:
    @staticmethod
    def get_live_indices():
        """Return simulated forex rates for UGX, KES, SSP."""
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(20)]
        # Generate random walk data
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
        """Fake Eurocode check – returns a dict of results."""
        if material == "Steel":
            moment = (load * beam_length**2) / 8
            capacity = 250  # kNm
            utilization = moment / capacity
        else:  # Concrete
            moment = (load * beam_length**2) / 10
            capacity = 180
            utilization = moment / capacity
        return {
            "Design Moment (kNm)": round(moment, 2),
            "Capacity (kNm)": capacity,
            "Utilization Ratio": round(utilization, 2),
            "Status": "OK ✅" if utilization <= 1.0 else "FAIL ❌"
        }

    @staticmethod
    def generate_3d_frame():
        """Create a simple 3D structural frame for visualisation."""
        # nodes and edges of a small frame
        nodes = np.array([
            [0, 0, 0], [4, 0, 0], [0, 0, 3], [4, 0, 3],
            [0, 5, 0], [4, 5, 0], [0, 5, 3], [4, 5, 3]
        ])
        edges = [(0,1), (0,2), (1,3), (2,3),
                 (0,4), (1,5), (2,6), (3,7),
                 (4,5), (4,6), (5,7), (6,7)]
        return nodes, edges

# Page config
st.set_page_config(page_title="Arc OS", layout="wide", initial_sidebar_state="expanded")

# ----- Custom CSS for aesthetics -----
def load_css():
    st.markdown("""
    <style>
        /* Background and global font */
        .stApp {
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e0e0e0;
        }
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background: rgba(20, 20, 40, 0.8);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255,255,255,0.1);
        }
        /* Headers */
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif;
            font-weight: 600;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        /* Glass-morphism cards */
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(15px);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px 0 rgba(0,0,0,0.37);
        }
        /* Cool button styling */
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
        /* Secondary button */
        .cool-button.secondary {
            background: linear-gradient(45deg, #00b4db, #0083b0);
            box-shadow: 0 0 20px rgba(0,180,219,0.5);
        }
        .cool-button.secondary:hover {
            box-shadow: 0 0 30px rgba(0,180,219,0.8);
        }
        /* Metric boxes */
        .metric-box {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px;
            margin: 5px 0;
            text-align: center;
            font-weight: bold;
            border: 1px solid rgba(255,255,255,0.15);
        }
        /* Plotly chart background transparent */
        .js-plotly-plot, .plot-container {
            background: transparent !important;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# ----- Persistent State -----
if 'arc_state' not in st.session_state:
    st.session_state.arc_state = {
        "market": None,
        "structural": None
    }
if 'forex_data' not in st.session_state:
    st.session_state.forex_data = ForexEngine.get_live_indices()
if 'arch_result' not in st.session_state:
    st.session_state.arch_result = None

# ----- Sidebar -----
with st.sidebar:
    st.markdown("## ⚙️ Arc OS Control")
    mode = st.radio(
        "🧠 **Intelligence Engine**",
        ["💱 Forex (Random)", "🏗️ Arch (Sai)"],
        index=0
    )
    st.markdown("---")
    st.caption("v2.0 · Aesthetic Overdrive")

# ----- Main Title -----
st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System</h1>", unsafe_allow_html=True)

# ----- Engine Dispatcher -----
if "Forex" in mode:
    # ---------- FOREX MODULE ----------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💹 Random: Forex Intelligence")
    st.markdown("*Live indices for UGX, KES, SSP (simulated)*")
    st.dataframe(st.session_state.forex_data.tail(10), use_container_width=True)

    # Chart
    fig = px.line(st.session_state.forex_data.melt(id_vars="Time"),
                  x="Time", y="value", color="variable",
                  title="Currency Trends", template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    # Cool refresh button
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.markdown('<button class="cool-button" id="refresh-forex">🔄 Refresh Live Data</button>', unsafe_allow_html=True):
            pass
        # Actually handle the click using a native button for interaction, but keep the cool look with custom HTML.
        # We'll use a hidden native button triggered by the HTML via a callback workaround.
        # Simpler: Use a Streamlit button inside a container styled with the same CSS.
        st.markdown("""
        <style>
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
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.2);
            width: 100%;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(255,75,43,0.8);
            background: linear-gradient(45deg, #ff4b2b, #ff416c);
            color: white;
        }
        </style>
        """, unsafe_allow_html=True)
        if st.button("🔄 Refresh Live Data", key="forex_refresh"):
            st.session_state.forex_data = ForexEngine.get_live_indices()
            st.experimental_rerun()

    st.markdown('</div>', unsafe_allow_html=True)

else:
    # ---------- ARCHITECTURE MODULE ----------
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏛️ Sai: Architectural Synthesis")
    st.markdown("*Structural analysis & 3D projection*")

    col_input, col_viz = st.columns([1, 2])

    with col_input:
        st.markdown("### 📐 Design Parameters")
        beam_length = st.slider("Beam Length (m)", 2.0, 10.0, 5.0, 0.5)
        load = st.slider("Uniform Load (kN/m)", 1.0, 50.0, 20.0, 1.0)
        material = st.selectbox("Material", ["Steel", "Concrete"])

        # Cool "Run Analysis" button
        st.markdown("""
        <style>
        div.stButton > button#run_analysis {
            background: linear-gradient(45deg, #00b4db, #0083b0);
            border: none;
            color: white;
            padding: 12px 28px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 50px;
            box-shadow: 0 0 20px rgba(0,180,219,0.5);
            transition: all 0.3s ease;
            cursor: pointer;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            width: 100%;
            margin-top: 20px;
        }
        div.stButton > button#run_analysis:hover {
            box-shadow: 0 0 30px rgba(0,180,219,0.8);
            background: linear-gradient(45deg, #0083b0, #00b4db);
        }
        </style>
        """, unsafe_allow_html=True)

        if st.button("⚡ Run Structural Analysis", key="run_analysis"):
            st.session_state.arch_result = SaiArchitect.structural_check(beam_length, load, material)

        if st.session_state.arch_result:
            st.markdown("### 📊 Results")
            res = st.session_state.arch_result
            cols = st.columns(2)
            cols[0].metric("Design Moment", f"{res['Design Moment (kNm)']} kNm")
            cols[1].metric("Utilization", f"{res['Utilization Ratio']:.2f}", 
                           delta="OK" if res['Status'].startswith("OK") else "FAIL",
                           delta_color="normal" if res['Status'].startswith("OK") else "inverse")
            st.markdown(f"**Status:** {res['Status']}")

    with col_viz:
        st.markdown("### 🧊 3D Isometric Projection")
        nodes, edges = SaiArchitect.generate_3d_frame()
        # Create Plotly 3D scatter + lines
        fig = go.Figure()
        # Add nodes
        fig.add_trace(go.Scatter3d(
            x=nodes[:,0], y=nodes[:,1], z=nodes[:,2],
            mode='markers',
            marker=dict(size=8, color='cyan', opacity=0.9),
            name='Nodes'
        ))
        # Add edges as lines
        for edge in edges:
            x = [nodes[edge[0],0], nodes[edge[1],0]]
            y = [nodes[edge[0],1], nodes[edge[1],1]]
            z = [nodes[edge[0],2], nodes[edge[1],2]]
            fig.add_trace(go.Scatter3d(
                x=x, y=y, z=z,
                mode='lines',
                line=dict(color='rgba(255,255,255,0.4)', width=4),
                showlegend=False
            ))
        fig.update_layout(
            scene=dict(
                xaxis_title='X (m)',
                yaxis_title='Y (m)',
                zaxis_title='Z (m)',
                aspectmode='data',
                bgcolor='rgba(0,0,0,0)'
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            paper_bgcolor='rgba(0,0,0,0)',
            template='plotly_dark'
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)