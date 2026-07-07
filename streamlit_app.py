import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime, timedelta
import hashlib

# ------------------------------------------------------------------
# DATABASE SETUP (SQLite)
# ------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("arc_os.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS forex_quotes
                 (timestamp TEXT, pair TEXT, rate REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS structural_analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  beam_length REAL,
                  load_magnitude REAL,
                  load_type TEXT,
                  material TEXT,
                  moment REAL,
                  shear REAL,
                  stress_bending REAL,
                  stress_shear REAL,
                  deflection REAL,
                  status TEXT)''')
    conn.commit()
    return conn

def get_db_connection():
    return sqlite3.connect("arc_os.db")

# ------------------------------------------------------------------
# AUTHENTICATION (FIX 2 – WORKING LOGIN)
# ------------------------------------------------------------------
USERS = {
    "admin": hashlib.sha256("arc2024".encode()).hexdigest(),
    "demo": hashlib.sha256("demo".encode()).hexdigest()
}

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Arc OS Pro Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if username in USERS:
                    hashed = hashlib.sha256(password.encode()).hexdigest()
                    if hashed == USERS[username]:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("Invalid password")
                else:
                    st.error("Invalid username")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    login()
    st.stop()

def logout():
    st.session_state.authenticated = False
    st.session_state.pop("username", None)
    st.rerun()

# ------------------------------------------------------------------
# FOREX ENGINE (Real + DB storage)
# ------------------------------------------------------------------
class ForexEngine:
    PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "UGX/USD", "KES/USD", "SSP/USD"]
    BASE_CURRENCIES = {
        "EUR/USD": ("EUR", "USD"), "GBP/USD": ("GBP", "USD"), "USD/JPY": ("USD", "JPY"),
        "UGX/USD": ("USD", "UGX"), "KES/USD": ("USD", "KES"), "SSP/USD": ("USD", "SSP")
    }

    @staticmethod
    def fetch_latest_rates():
        currencies = set()
        for base, target in ForexEngine.BASE_CURRENCIES.values():
            currencies.update([base, target])
        currencies_str = ",".join(currencies)
        url = f"https://api.frankfurter.app/latest?from=EUR&to={currencies_str}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rates = data["rates"]
            eur_to = {cur: rates[cur] for cur in currencies}
            live_rates = {}
            for pair, (base, target) in ForexEngine.BASE_CURRENCIES.items():
                if base == target:
                    rate = 1.0
                elif base == "EUR":
                    rate = eur_to[target]
                elif target == "EUR":
                    rate = 1.0 / eur_to[base]
                else:
                    rate = eur_to[target] / eur_to[base]
                live_rates[pair] = round(rate, 4)
            return live_rates
        except Exception as e:
            st.warning(f"Live fetch failed ({e}), using simulated data.")
            return None

    @staticmethod
    def get_live_data(minutes=60, use_real=True, store_db=True):
        if use_real:
            live = ForexEngine.fetch_latest_rates()
            if live is not None:
                np.random.seed(42)
                now = datetime.now()
                times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
                data = {"Time": times}
                for pair in ForexEngine.PAIRS:
                    base = live[pair]
                    vol = base * 0.0002
                    prices = base + np.cumsum(np.random.normal(0, vol, minutes))
                    data[pair] = np.round(np.maximum(prices, 0.0001), 4)
                df = pd.DataFrame(data)
                if store_db:
                    ForexEngine._store_quotes(live)
                return df
        # Fallback simulated
        return ForexEngine._simulated_data(minutes)

    @staticmethod
    def _simulated_data(minutes=60):
        np.random.seed(42)
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
        base = {"EUR/USD": 1.08, "GBP/USD": 1.26, "USD/JPY": 144.5,
                "UGX/USD": 3750, "KES/USD": 145, "SSP/USD": 1100}
        vol = {"EUR/USD": 0.0003, "GBP/USD": 0.0004, "USD/JPY": 0.02,
               "UGX/USD": 2, "KES/USD": 0.1, "SSP/USD": 5}
        data = {"Time": times}
        for pair in ForexEngine.PAIRS:
            data[pair] = np.round(base[pair] + np.cumsum(np.random.normal(0, vol[pair], minutes)), 4)
        return pd.DataFrame(data)

    @staticmethod
    def _store_quotes(rates):
        conn = get_db_connection()
        c = conn.cursor()
        ts = datetime.now().isoformat()
        for pair, rate in rates.items():
            c.execute("INSERT INTO forex_quotes VALUES (?, ?, ?)", (ts, pair, rate))
        conn.commit()

    @staticmethod
    def get_history(pair, limit=100):
        conn = get_db_connection()
        df = pd.read_sql_query(
            f"SELECT timestamp, rate FROM forex_quotes WHERE pair='{pair}' ORDER BY timestamp DESC LIMIT {limit}",
            conn)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.iloc[::-1]  # chronological

    @staticmethod
    def get_summary(df):
        latest = df.iloc[-1]
        prev = df.iloc[0] if len(df) > 1 else latest
        summary = []
        for pair in ForexEngine.PAIRS:
            cur = latest[pair]
            change = cur - prev[pair]
            pct = (change / prev[pair]) * 100 if prev[pair] != 0 else 0
            summary.append({"Pair": pair, "Last": round(cur, 4),
                            "Change": round(change, 4), "Change %": f"{pct:.2f}%"})
        return pd.DataFrame(summary)

    @staticmethod
    def get_correlation_matrix(df):
        returns = df[ForexEngine.PAIRS].pct_change().dropna()
        return returns.corr().round(2)

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
        np.random.seed(99)
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
        volume = np.random.randint(500, 5000, minutes)
        return pd.DataFrame({"Time": times, "Volume": volume})

# ------------------------------------------------------------------
# ARCHITECTURAL ENGINE (Eurocode + DB)
# ------------------------------------------------------------------
class SaiArchitect:
    MATERIALS = {
        "Steel S355": {"fy": 355e6, "E": 210e9, "gamma": 1.0, "I": 1e-4, "W": 2e-3, "def_lim": 1/250},
        "Concrete C30": {"fy": 500e6, "E": 30e9, "gamma": 1.5, "I": 2e-4, "W": 1e-3, "def_lim": 1/300},
        "Timber GL24h": {"fy": 24e6, "E": 12e9, "gamma": 1.3, "I": 5e-4, "W": 3e-3, "def_lim": 1/200},
        "Composite": {"fy": 500e6, "E": 40e9, "gamma": 1.0, "I": 3e-4, "W": 4e-3, "def_lim": 1/400}
    }

    @staticmethod
    def structural_analysis(beam_length, load_mag, load_type, material):
        props = SaiArchitect.MATERIALS[material]
        E, I, W, fy, gamma = props["E"], props["I"], props["W"], props["fy"], props["gamma"]
        limit_def = props["def_lim"] * beam_length

        if load_type == "Uniform (kN/m)":
            w = load_mag * 1000
            M = w * beam_length**2 / 8
            V = w * beam_length / 2
            delta = (5 * w * beam_length**4) / (384 * E * I)
        else:
            P = load_mag * 1000
            M = P * beam_length / 4
            V = P / 2
            delta = (P * beam_length**3) / (48 * E * I)

        sigma = M / W
        tau = 1.5 * V / 0.01
        sigma_rd = fy / gamma
        tau_rd = fy / (np.sqrt(3) * gamma)
        util_m = sigma / sigma_rd
        util_v = tau / tau_rd
        ok = util_m <= 1 and util_v <= 1 and delta <= limit_def
        result = {
            "Design Moment (kNm)": round(M/1000,2),
            "Shear (kN)": round(V/1000,2),
            "Bending Stress (MPa)": round(sigma/1e6,2),
            "Shear Stress (MPa)": round(tau/1e6,2),
            "Deflection (mm)": round(delta*1000,2),
            "Allowable Deflection (mm)": round(limit_def*1000,2),
            "Moment Util.": round(util_m,2),
            "Shear Util.": round(util_v,2),
            "Deflection OK": "✅" if delta <= limit_def else "❌",
            "Status": "OK ✅" if ok else "FAIL ❌"
        }
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO structural_analyses 
                     (timestamp, beam_length, load_magnitude, load_type, material,
                      moment, shear, stress_bending, stress_shear, deflection, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (datetime.now().isoformat(), beam_length, load_mag, load_type, material,
                   M/1000, V/1000, sigma/1e6, tau/1e6, delta*1000, result["Status"]))
        conn.commit()
        return result

    @staticmethod
    def get_history(limit=5):
        conn = get_db_connection()
        df = pd.read_sql_query(
            "SELECT * FROM structural_analyses ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,))
        return df

# ------------------------------------------------------------------
# 3D VIEWER (Three.js)
# ------------------------------------------------------------------
def render_3d_viewer(beam_length, load_magnitude, load_type, material):
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style> body {{ margin: 0; overflow: hidden; }} </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    </head>
    <body>
    <script>
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x111122);
        const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
        camera.position.set(8, 5, 8);
        camera.lookAt(0, 2, 0);
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0x404080);
        scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1);
        dirLight.position.set(1, 2, 1);
        scene.add(dirLight);

        const beamGeometry = new THREE.BoxGeometry({beam_length}, 0.2, 0.3);
        const beamMat = new THREE.MeshPhongMaterial({{ color: 0x3a7bd5, emissive: 0x001122 }});
        const beam = new THREE.Mesh(beamGeometry, beamMat);
        beam.position.y = 2;
        scene.add(beam);

        const supportMat = new THREE.MeshPhongMaterial({{ color: 0x00d2ff, emissive: 0x002222 }});
        const leftSupport = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 1.5, 8), supportMat);
        leftSupport.position.set(-{beam_length/2 + 0.2}, 1.25, 0);
        scene.add(leftSupport);
        const rightSupport = leftSupport.clone();
        rightSupport.position.x = {beam_length/2 + 0.2};
        scene.add(rightSupport);

        const arrowDir = new THREE.Vector3(0, -1, 0);
        const arrowOrigin = new THREE.Vector3(0, 2.2, 0);
        const arrow = new THREE.ArrowHelper(arrowDir, arrowOrigin, 1.2, 0xff4b2b, 0.3, 0.2);
        scene.add(arrow);

        const canvas = document.createElement('canvas');
        canvas.width = 128; canvas.height = 64;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('{load_magnitude} kN', 64, 35);
        const texture = new THREE.CanvasTexture(canvas);
        const spriteMaterial = new THREE.SpriteMaterial({{ map: texture }});
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.position.set(0.8, 2.6, 0);
        sprite.scale.set(1.5, 0.75, 1);
        scene.add(sprite);

        const gridHelper = new THREE.GridHelper(10, 20, 0x336699, 0x224466);
        scene.add(gridHelper);

        let isDragging = false, previousMouse = {{ x: 0, y: 0 }};
        renderer.domElement.addEventListener('mousedown', e => {{ isDragging = true; previousMouse.x = e.clientX; previousMouse.y = e.clientY; }});
        renderer.domElement.addEventListener('mouseup', () => isDragging = false);
        renderer.domElement.addEventListener('mousemove', e => {{
            if (isDragging) {{
                const deltaX = e.clientX - previousMouse.x;
                const deltaY = e.clientY - previousMouse.y;
                camera.position.x += deltaX * 0.01;
                camera.position.y -= deltaY * 0.01;
                camera.lookAt(0, 2, 0);
                previousMouse.x = e.clientX;
                previousMouse.y = e.clientY;
            }}
        }});
        renderer.domElement.addEventListener('wheel', e => {{
            camera.position.z += e.deltaY * 0.01;
            camera.lookAt(0, 2, 0);
            e.preventDefault();
        }});

        function animate() {{
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }}
        animate();
    </script>
    </body>
    </html>
    """
    st.components.v1.html(html_code, height=350)

# ------------------------------------------------------------------
# STREAMLIT APP (Main)
# ------------------------------------------------------------------
st.set_page_config(page_title="Arc OS Pro", layout="wide")

def load_css():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); color: #e0e0e0; }
        section[data-testid="stSidebar"] {
            background: rgba(20,20,40,0.8); backdrop-filter: blur(10px); border-right: 1px solid rgba(255,255,255,0.1);
        }
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif; font-weight: 600;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        }
        .glass-card {
            background: rgba(255,255,255,0.05); backdrop-filter: blur(15px); border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1); padding: 20px; margin: 10px 0; box-shadow: 0 8px 32px rgba(0,0,0,0.37);
        }
        .metric-box {
            background: rgba(255,255,255,0.08); border-radius: 12px; padding: 15px; margin: 5px 0;
            text-align: center; font-weight: bold; border: 1px solid rgba(255,255,255,0.15);
        }
        div.stButton > button {
            background: linear-gradient(45deg, #ff416c, #ff4b2b); border: none; color: white;
            padding: 12px 28px; font-size: 16px; font-weight: bold; border-radius: 50px;
            box-shadow: 0 0 20px rgba(255,75,43,0.5); transition: all 0.3s ease; cursor: pointer;
            letter-spacing: 0.5px; text-transform: uppercase; width: 100%; border: 1px solid rgba(255,255,255,0.2);
        }
        div.stButton > button:hover {
            transform: translateY(-2px); box-shadow: 0 0 30px rgba(255,75,43,0.8);
            background: linear-gradient(45deg, #ff4b2b, #ff416c); color: white;
        }
        div.stButton > button.arch {
            background: linear-gradient(45deg, #00b4db, #0083b0); box-shadow: 0 0 20px rgba(0,180,219,0.5);
        }
        div.stButton > button.arch:hover {
            box-shadow: 0 0 30px rgba(0,180,219,0.8); background: linear-gradient(45deg, #0083b0, #00b4db);
        }
    </style>
    """, unsafe_allow_html=True)

load_css()
init_db()

if 'forex_data' not in st.session_state:
    st.session_state.forex_data = ForexEngine.get_live_data(use_real=True)
if 'forex_volume' not in st.session_state:
    st.session_state.forex_volume = ForexEngine.get_volume()
if 'arch_result' not in st.session_state:
    st.session_state.arch_result = None
if 'use_real_forex' not in st.session_state:
    st.session_state.use_real_forex = True

with st.sidebar:
    st.markdown("## ⚙️ Arc OS Pro")
    st.write(f"👤 {st.session_state.username}")
    mode = st.radio("🧠 Engine", ["💱 Forex Pro", "🏗️ Arch Pro"])
    st.checkbox("Real‑time forex", value=st.session_state.use_real_forex, key="use_real_forex")
    if st.button("🚪 Logout"):
        logout()
    st.caption("v4.2 · Fixed Auth")

st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System Pro</h1>", unsafe_allow_html=True)

# ------------------- FOREX MODULE -------------------
if "Forex" in mode:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💹 Forex Pro: Live & Historical")
    forex_df = ForexEngine.get_live_data(use_real=st.session_state.use_real_forex)
    st.session_state.forex_data = forex_df

    summary = ForexEngine.get_summary(forex_df)
    cols = st.columns(len(summary))
    for i, row in summary.iterrows():
        with cols[i]:
            color = "#00ff88" if row["Change"] >= 0 else "#ff4b4b"
            st.markdown(f"""<div class="metric-box">
                <span style="font-size:18px;">{row['Pair']}</span><br>
                <span style="font-size:24px; color:{color};">{row['Last']}</span><br>
                <span style="font-size:14px; color:{color};">{row['Change']} ({row['Change %']})</span>
            </div>""", unsafe_allow_html=True)

    st.subheader("📈 Live Streams")
    st.line_chart(forex_df.set_index("Time"))

    pair_hist = st.selectbox("🔍 Historical from DB", ForexEngine.PAIRS)
    hist_df = ForexEngine.get_history(pair_hist, 30)
    if not hist_df.empty:
        st.line_chart(hist_df.set_index("timestamp"))
    else:
        st.info("No history yet. Data is stored after each refresh.")

    st.subheader("📊 Volume")
    st.bar_chart(st.session_state.forex_volume.set_index("Time"))
    st.subheader("🔗 Correlation")
    st.table(ForexEngine.get_correlation_matrix(forex_df))
    st.subheader("📅 Economic Calendar")
    st.table(ForexEngine.generate_economic_calendar())

    if st.button("🔄 Refresh Live Data", key="forex_refresh"):
        st.session_state.forex_data = ForexEngine.get_live_data(use_real=st.session_state.use_real_forex)
        st.session_state.forex_volume = ForexEngine.get_volume()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------- ARCH MODULE -------------------
else:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏛️ Arch Pro: 3D Interactive Analysis")
    col_input, col_viz = st.columns([1, 2])

    with col_input:
        st.markdown("### 📐 Design Parameters")
        beam_length = st.slider("Beam Length (m)", 2.0, 15.0, 5.0, 0.5)
        load_type = st.selectbox("Load Type", ["Uniform (kN/m)", "Point Load (kN)"])
        if "Uniform" in load_type:
            load_label = "Uniform Load (kN/m)"
            load_min, load_max, load_def = 0.5, 200.0, 25.0
        else:
            load_label = "Point Load at Midspan (kN)"
            load_min, load_max, load_def = 1.0, 500.0, 100.0
        load_magnitude = st.slider(load_label, load_min, load_max, load_def, 1.0)
        material = st.selectbox("Material", list(SaiArchitect.MATERIALS.keys()))

        if st.button("⚡ Run Eurocode Check", key="run_analysis"):
            st.session_state.arch_result = SaiArchitect.structural_analysis(
                beam_length, load_magnitude, load_type, material
            )

        if st.session_state.arch_result:
            res = st.session_state.arch_result
            st.metric("Status", res["Status"])
            tab1, tab2 = st.tabs(["Forces", "Stress/Deflection"])
            with tab1:
                st.metric("Moment", f"{res['Design Moment (kNm)']} kNm")
                st.metric("Shear", f"{res['Shear (kN)']} kN")
            with tab2:
                st.metric("Bending Stress", f"{res['Bending Stress (MPa)']} MPa")
                st.metric("Shear Stress", f"{res['Shear Stress (MPa)']} MPa")
                st.metric("Deflection", f"{res['Deflection (mm)']} mm",
                          delta=f"Limit {res['Allowable Deflection (mm)']} mm")
                st.metric("Moment Util.", f"{res['Moment Util.']}",
                          delta="OK" if res['Moment Util.']<=1 else "FAIL")

            st.markdown("### 📋 Recent Analyses (from DB)")
            hist = SaiArchitect.get_history(5)
            st.dataframe(hist[["timestamp", "beam_length", "load_magnitude", "material", "status"]], use_container_width=True)

    with col_viz:
        st.markdown("### 🧊 Interactive 3D Model")
        render_3d_viewer(beam_length, load_magnitude, load_type, material)

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    pass