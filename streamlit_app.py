import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# MOCK ENGINES (Replace with real engines from your repo if desired)
# ------------------------------------------------------------------
class ForexEngine:
    PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "UGX/USD", "KES/USD", "SSP/USD"]
    BASE_VALUES = {
        "EUR/USD": 1.08, "GBP/USD": 1.26, "USD/JPY": 144.5,
        "UGX/USD": 3750, "KES/USD": 145, "SSP/USD": 1100
    }
    VOLATILITY = {
        "EUR/USD": 0.0003, "GBP/USD": 0.0004, "USD/JPY": 0.02,
        "UGX/USD": 2, "KES/USD": 0.1, "SSP/USD": 5
    }

    @staticmethod
    def get_live_data(minutes=60):
        """Generate one-minute tick data for all pairs."""
        np.random.seed(42)
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
        data = {"Time": times}
        for pair in ForexEngine.PAIRS:
            base = ForexEngine.BASE_VALUES[pair]
            vol = ForexEngine.VOLATILITY[pair]
            prices = base + np.cumsum(np.random.normal(0, vol, minutes))
            data[pair] = np.round(prices, 4)
        df = pd.DataFrame(data)
        return df

    @staticmethod
    def get_summary(df):
        """Calculate latest values and daily changes."""
        latest = df.iloc[-1]
        prev = df.iloc[0] if len(df) > 1 else latest
        summary = []
        for pair in ForexEngine.PAIRS:
            cur = latest[pair]
            change = cur - prev[pair]
            pct = (change / prev[pair]) * 100 if prev[pair] != 0 else 0
            summary.append({
                "Pair": pair,
                "Last": round(cur, 4),
                "Change": round(change, 4),
                "Change %": f"{pct:.2f}%"
            })
        return pd.DataFrame(summary)

    @staticmethod
    def get_correlation_matrix(df):
        """Return correlation matrix of returns."""
        returns = df[ForexEngine.PAIRS].pct_change().dropna()
        corr = returns.corr().round(2)
        return corr

    @staticmethod
    def generate_economic_calendar():
        events = [
            {"Time": "10:00", "Event": "UGX Inflation Rate (MoM)", "Impact": "High", "Forecast": "0.2%", "Previous": "0.1%"},
            {"Time": "12:30", "Event": "KES GDP Growth Rate (YoY)", "Impact": "High", "Forecast": "5.2%", "Previous": "5.0%"},
            {"Time": "14:00", "Event": "SSP Trade Balance", "Impact": "Medium", "Forecast": "-$150M", "Previous": "-$140M"},
            {"Time": "16:00", "Event": "EUR/USD Consumer Confidence", "Impact": "Low", "Forecast": "-15.2", "Previous": "-15.0"},
            {"Time": "18:30", "Event": "USD/JPY Manufacturing PMI", "Impact": "Medium", "Forecast": "49.8", "Previous": "50.1"},
        ]
        return pd.DataFrame(events)

    @staticmethod
    def get_volume(minutes=60):
        """Simulated volume bars."""
        np.random.seed(99)
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
        volume = np.random.randint(500, 5000, minutes)
        return pd.DataFrame({"Time": times, "Volume": volume})


class SaiArchitect:
    MATERIALS = {
        "Steel": {"fy": 355, "E": 210e9, "capacity_moment": 250, "capacity_shear": 200, "deflection_limit": 1/250},
        "Concrete": {"fy": 500, "E": 30e9, "capacity_moment": 180, "capacity_shear": 150, "deflection_limit": 1/300},
        "Timber": {"fy": 24, "E": 12e9, "capacity_moment": 30, "capacity_shear": 20, "deflection_limit": 1/200},
        "Composite": {"fy": 500, "E": 40e9, "capacity_moment": 300, "capacity_shear": 250, "deflection_limit": 1/400},
    }

    @staticmethod
    def structural_check(beam_length, load_magnitude, load_type, material):
        """
        Returns a dict of structural results.
        load_magnitude: for uniform load (kN/m), for point load (kN) – assumed central.
        """
        props = SaiArchitect.MATERIALS[material]
        if load_type == "Uniform (kN/m)":
            M = (load_magnitude * beam_length**2) / 8
            V = (load_magnitude * beam_length) / 2
            # max deflection for simply supported uniform load
            delta = (5 * load_magnitude * beam_length**4) / (384 * props["E"] * 0.01)  # I approximated as 0.01 m4
        else:  # Point load at midspan
            M = (load_magnitude * beam_length) / 4
            V = load_magnitude / 2
            delta = (load_magnitude * beam_length**3) / (48 * props["E"] * 0.01)

        utilization_moment = M / props["capacity_moment"]
        utilization_shear = V / props["capacity_shear"]
        limit_span = props["deflection_limit"] * beam_length
        deflection_ok = delta <= limit_span

        return {
            "Material": material,
            "Design Moment (kNm)": round(M, 2),
            "Design Shear (kN)": round(V, 2),
            "Max Deflection (mm)": round(delta*1000, 2),
            "Allowable Deflection (mm)": round(limit_span*1000, 2),
            "Moment Util.": round(utilization_moment, 2),
            "Shear Util.": round(utilization_shear, 2),
            "Deflection OK": "✅" if deflection_ok else "❌",
            "Overall Status": "OK ✅" if (utilization_moment<=1 and utilization_shear<=1 and deflection_ok) else "FAIL ❌"
        }

# ------------------------------------------------------------------
# STREAMLIT APP
# ------------------------------------------------------------------
st.set_page_config(page_title="Arc OS", layout="wide")

# ---- CSS ----
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
        .metric-box {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px;
            margin: 5px 0;
            text-align: center;
            font-weight: bold;
            border: 1px solid rgba(255,255,255,0.15);
        }
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
        /* secondary button for architecture */
        div.stButton > button.arch {
            background: linear-gradient(45deg, #00b4db, #0083b0);
            box-shadow: 0 0 20px rgba(0,180,219,0.5);
        }
        div.stButton > button.arch:hover {
            box-shadow: 0 0 30px rgba(0,180,219,0.8);
            background: linear-gradient(45deg, #0083b0, #00b4db);
        }
        /* override streamlit dataframe */
        .stDataFrame, .stTable {
            background: transparent !important;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# ---- Session State ----
if 'forex_data' not in st.session_state:
    st.session_state.forex_data = ForexEngine.get_live_data()
if 'arch_result' not in st.session_state:
    st.session_state.arch_result = None
if 'forex_volume' not in st.session_state:
    st.session_state.forex_volume = ForexEngine.get_volume()

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## ⚙️ Arc OS Control")
    mode = st.radio("🧠 **Intelligence Engine**", ["💱 Forex Pro", "🏗️ Arch Pro"], index=0)
    st.markdown("---")
    st.caption("v2.0 · Data‑Rich Overdrive")

st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System</h1>", unsafe_allow_html=True)

# ====================== FOREX PRO ======================
if "Forex" in mode:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💹 Forex Pro: Multi‑Asset Intelligence")

    # Summary dashboard
    summary = ForexEngine.get_summary(st.session_state.forex_data)
    cols = st.columns(len(summary))
    for i, row in summary.iterrows():
        with cols[i]:
            color = "#00ff88" if row["Change"] >= 0 else "#ff4b4b"
            st.markdown(f"""
            <div class="metric-box">
                <span style="font-size:18px;">{row['Pair']}</span><br>
                <span style="font-size:24px; color:{color};">{row['Last']}</span><br>
                <span style="font-size:14px; color:{color};">{row['Change']} ({row['Change %']})</span>
            </div>
            """, unsafe_allow_html=True)

    # Chart: all pairs
    st.subheader("📈 Real‑Time Price Streams")
    st.line_chart(st.session_state.forex_data.set_index("Time"))

    # Volume bars
    st.subheader("📊 Volume")
    st.bar_chart(st.session_state.forex_volume.set_index("Time"))

    # Correlation matrix
    st.subheader("🔗 Correlation Matrix (1‑min returns)")
    corr = ForexEngine.get_correlation_matrix(st.session_state.forex_data)
    st.table(corr)

    # Economic calendar
    st.subheader("📅 Economic Calendar (Today)")
    st.table(ForexEngine.generate_economic_calendar())

    # Refresh button
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("🔄 Refresh All Live Data", key="forex_refresh"):
            st.session_state.forex_data = ForexEngine.get_live_data()
            st.session_state.forex_volume = ForexEngine.get_volume()
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ====================== ARCH PRO ======================
else:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏛️ Arch Pro: Structural Synthesis & Design")

    col_input, col_viz = st.columns([1, 2])

    with col_input:
        st.markdown("### 📐 Load & Geometry")
        beam_length = st.slider("Beam Length (m)", 2.0, 12.0, 5.0, 0.5)
        load_type = st.selectbox("Load Type", ["Uniform (kN/m)", "Point Load (kN)"])
        if "Uniform" in load_type:
            load_label = "Uniform Load (kN/m)"
            load_min, load_max, load_default = 1.0, 100.0, 20.0
        else:
            load_label = "Point Load at Midspan (kN)"
            load_min, load_max, load_default = 1.0, 200.0, 50.0
        load_magnitude = st.slider(load_label, load_min, load_max, load_default, 1.0)
        material = st.selectbox("Material", list(SaiArchitect.MATERIALS.keys()))

        if st.button("⚡ Run Full Analysis", key="run_analysis"):
            st.session_state.arch_result = SaiArchitect.structural_check(
                beam_length, load_magnitude, load_type, material
            )

        if st.session_state.arch_result:
            res = st.session_state.arch_result
            st.markdown("### 📊 Results")
            col1, col2 = st.columns(2)
            col1.metric("Design Moment", f"{res['Design Moment (kNm)']} kNm")
            col2.metric("Shear Force", f"{res['Design Shear (kN)']} kN")
            col1.metric("Max Deflection", f"{res['Max Deflection (mm)']} mm",
                        delta=f"Limit {res['Allowable Deflection (mm)']} mm",
                        delta_color="off")
            col2.metric("Moment Util.", f"{res['Moment Util.']:.2f}",
                        delta="OK" if res['Moment Util.']<=1 else "FAIL",
                        delta_color="normal" if res['Moment Util.']<=1 else "inverse")
            st.markdown(f"**Deflection Status:** {res['Deflection OK']}  |  **Overall:** {res['Overall Status']}")

            # Load combination table (just a sample)
            combos = pd.DataFrame([
                {"Case": "Dead Load", "Factor": 1.35, "Moment (kNm)": round(0.7*res['Design Moment (kNm)'],2)},
                {"Case": "Live Load", "Factor": 1.5, "Moment (kNm)": round(0.3*res['Design Moment (kNm)'],2)},
                {"Case": "Wind Load", "Factor": 1.5, "Moment (kNm)": round(0.1*res['Design Moment (kNm)'],2)},
            ])
            st.table(combos)

    with col_viz:
        st.markdown("### 🧊 3D Isometric Projection (Enhanced)")
        # SVG with supports, loads, and dimensions
        svg = f"""
        <svg width="380" height="280" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L9,3 z" fill="#ff4b2b"/>
                </marker>
            </defs>
            <!-- Grid -->
            <line x1="30" y1="220" x2="180" y2="80" stroke="#00d2ff" stroke-width="1" opacity="0.3"/>
            <line x1="180" y1="80" x2="330" y2="220" stroke="#00d2ff" stroke-width="1" opacity="0.3"/>
            <line x1="30" y1="220" x2="330" y2="220" stroke="#00d2ff" stroke-width="1" opacity="0.3"/>
            <!-- Beam top -->
            <line x1="80" y1="160" x2="280" y2="160" stroke="#ffffff" stroke-width="4" opacity="0.9"/>
            <!-- Beam left face -->
            <line x1="80" y1="160" x2="30" y2="220" stroke="#ffffff" stroke-width="2"/>
            <line x1="280" y1="160" x2="330" y2="220" stroke="#ffffff" stroke-width="2"/>
            <line x1="30" y1="220" x2="330" y2="220" stroke="#ffffff" stroke-width="2"/>
            <!-- Supports -->
            <polygon points="50,220 60,220 55,240" fill="#00d2ff"/>
            <polygon points="310,220 320,220 315,240" fill="#00d2ff"/>
            <!-- Load arrows -->
            <line x1="180" y1="80" x2="180" y2="140" stroke="#ff4b2b" stroke-width="3" marker-end="url(#arrow)"/>
            <text x="190" y="110" fill="#ff4b2b" font-size="14">{load_magnitude} kN</text>
            <!-- Dimensions -->
            <text x="130" y="150" fill="#aaa" font-size="12">{beam_length} m</text>
            <text x="5" y="190" fill="#aaa" font-size="12">L = {beam_length}m</text>
            <!-- Labels -->
            <text x="120" y="260" fill="#aaa" font-size="12">Simply Supported Beam – {material}</text>
        </svg>
        """
        st.markdown(svg, unsafe_allow_html=True)
        st.caption("Interactive 3D (coming soon)")

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    pass