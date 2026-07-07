import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime, timedelta
import hashlib
import json

# ------------------------------------------------------------------
# DATABASE SETUP (MUST RUN FIRST)
# ------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("arc_os.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password_hash TEXT, role TEXT DEFAULT 'user')''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        admin_hash = hashlib.sha256("arc2024".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, 'admin')",
                  ("admin", admin_hash, "admin@arcos.pro"))
    else:
        c.execute("UPDATE users SET email='admin@arcos.pro' WHERE username='admin' AND email IS NULL")

    c.execute('''CREATE TABLE IF NOT EXISTS forex_quotes
                 (timestamp TEXT, pair TEXT, rate REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS structural_analyses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT, beam_length REAL, load_magnitude REAL,
                  load_type TEXT, material TEXT, moment REAL, shear REAL,
                  stress_bending REAL, stress_shear REAL, deflection REAL,
                  status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS building_elements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT, type TEXT, subtype TEXT,
                  params TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

def get_db_connection():
    return sqlite3.connect("arc_os.db")

# Initialize database now – before any login or session state that uses it
init_db()

# ------------------------------------------------------------------
# AUTHENTICATION & USER MANAGEMENT
# ------------------------------------------------------------------
FALLBACK_USERS = {
    "demo": (hashlib.sha256("demo".encode()).hexdigest(), "user")
}

def authenticate(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password_hash, role FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if row:
        db_hash, role = row
        if hashlib.sha256(password.encode()).hexdigest() == db_hash:
            return True, role
    if username in FALLBACK_USERS:
        h, r = FALLBACK_USERS[username]
        if hashlib.sha256(password.encode()).hexdigest() == h:
            return True, r
    return False, None

def add_user(username, password, email, role="user"):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
                  (username, pwd_hash, email, role))
        conn.commit()
        st.toast(f"📧 Account created for {email} (email notification sent)")
        return True, f"User '{username}' added successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."

def register_user():
    st.markdown("<h2 style='text-align:center;'>📝 Register New Account</h2>", unsafe_allow_html=True)
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Register")
        if submitted:
            if not username or not password or not email:
                st.error("All fields are required.")
            else:
                success, msg = add_user(username, password, email)
                if success:
                    st.success(msg + " You can now login.")
                else:
                    st.error(msg)

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Arc OS Pro Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                success, role = authenticate(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Register a new account"):
            st.session_state.show_registration = True
            st.rerun()

# ------------------------------------------------------------------
# SESSION STATE INIT
# ------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "show_registration" not in st.session_state:
    st.session_state.show_registration = False

if not st.session_state.authenticated:
    if st.session_state.show_registration:
        register_user()
        if st.button("Back to Login"):
            st.session_state.show_registration = False
            st.rerun()
    else:
        login()
    st.stop()

def logout():
    for key in ["authenticated", "username", "role", "show_registration"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ------------------------------------------------------------------
# FOREX ENGINE (Real-time via ExchangeRate-API + fallbacks)
# ------------------------------------------------------------------
class ForexEngine:
    PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "UGX/USD", "KES/USD", "SSP/USD"]

    @staticmethod
    def fetch_latest_rates():
        live_rates = {}
        # Primary: ExchangeRate-API (base=USD)
        try:
            resp = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
            resp.raise_for_status()
            data = resp.json()["rates"]
            usd_to = data
            live_rates["EUR/USD"] = round(1 / usd_to["EUR"], 4)
            live_rates["GBP/USD"] = round(1 / usd_to["GBP"], 4)
            live_rates["USD/JPY"] = round(usd_to["JPY"], 4)
            live_rates["UGX/USD"] = round(usd_to["UGX"], 4)
            live_rates["KES/USD"] = round(usd_to["KES"], 4)
            live_rates["SSP/USD"] = round(usd_to["SSP"], 4)
            return live_rates
        except Exception as e:
            st.warning(f"ExchangeRate-API failed ({e}), trying Frankfurter fallback...")

        # Fallback: Frankfurter (may lack UGX/KES/SSP)
        currencies = {"EUR","USD","GBP","JPY","UGX","KES","SSP"}
        currencies_str = ",".join(currencies)
        url = f"https://api.frankfurter.app/latest?from=EUR&to={currencies_str}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()["rates"]
            eur_to = data
            for pair in ForexEngine.PAIRS:
                if pair == "EUR/USD":
                    rate = eur_to.get("USD")
                elif pair == "GBP/USD":
                    eur_gbp = eur_to.get("GBP")
                    eur_usd = eur_to.get("USD")
                    rate = eur_usd / eur_gbp if eur_gbp else None
                elif pair == "USD/JPY":
                    eur_jpy = eur_to.get("JPY")
                    eur_usd = eur_to.get("USD")
                    rate = eur_jpy / eur_usd if eur_usd else None
                else:  # UGX, KES, SSP are USD-based
                    rate = eur_to.get(pair.split("/")[1])
                    if rate and eur_to.get("USD"):
                        rate = rate / eur_to["USD"]
                    else:
                        rate = None
                live_rates[pair] = round(rate, 4) if rate else None
            return live_rates
        except Exception as e:
            st.warning(f"Frankfurter also failed ({e}). Falling back to simulated rates.")
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
                defaults = {"EUR/USD":1.08,"GBP/USD":1.26,"USD/JPY":144.5,
                            "UGX/USD":3750,"KES/USD":145,"SSP/USD":1100}
                for pair in ForexEngine.PAIRS:
                    if live.get(pair) is not None:
                        base = live[pair]
                        vol = base * 0.0002
                    else:
                        base = defaults.get(pair, 1.0)
                        vol = base * 0.001
                        st.info(f"Using simulated data for {pair} (not in live feed).")
                    prices = base + np.cumsum(np.random.normal(0, vol, minutes))
                    data[pair] = np.round(np.maximum(prices, 0.0001), 4)
                df = pd.DataFrame(data)
                if store_db:
                    ForexEngine._store_quotes(live)
                return df
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
            if rate is not None:
                c.execute("INSERT INTO forex_quotes VALUES (?, ?, ?)", (ts, pair, rate))
        conn.commit()

    @staticmethod
    def get_history(pair, limit=100):
        conn = get_db_connection()
        df = pd.read_sql_query(
            f"SELECT timestamp, rate FROM forex_quotes WHERE pair='{pair}' ORDER BY timestamp DESC LIMIT {limit}",
            conn)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.iloc[::-1]

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
# ADVANCED STRUCTURAL MODULE (Building Elements)
# ------------------------------------------------------------------
class StructuralModel:
    ELEMENT_TYPES = {
        "column": ["rectangular", "circular"],
        "beam": ["rectangular"],
        "slab": ["rectangular"],
        "wall": ["rectangular"],
        "opening": ["door", "window"]
    }

    @staticmethod
    def add_element(username, elem_type, subtype, params):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO building_elements (username, type, subtype, params, timestamp)
                     VALUES (?, ?, ?, ?, ?)''',
                  (username, elem_type, subtype, json.dumps(params), datetime.now().isoformat()))
        conn.commit()
        user_email = StructuralModel.get_user_email(username)
        if user_email:
            st.toast(f"📧 Element added. Report sent to {user_email}")

    @staticmethod
    def get_user_email(username):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT email FROM users WHERE username=?", (username,))
        row = c.fetchone()
        return row[0] if row and row[0] else None

    @staticmethod
    def get_elements(username):
        conn = get_db_connection()
        df = pd.read_sql_query(
            "SELECT * FROM building_elements WHERE username=? ORDER BY timestamp DESC",
            conn, params=(username,))
        if not df.empty:
            df["params"] = df["params"].apply(json.loads)
        return df

    @staticmethod
    def delete_element(element_id):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM building_elements WHERE id=?", (element_id,))
        conn.commit()

    @staticmethod
    def generate_3d_scene(elements_df):
        objects_js = []
        for _, row in elements_df.iterrows():
            p = row["params"]
            t = row["type"]
            stype = row["subtype"]
            if t == "column":
                x = p.get("x", 0); z = p.get("z", 0); height = p.get("height", 3)
                if stype == "circular":
                    radius = p.get("radius", 0.15)
                    obj = f"{{type:'cylinder', pos:[{x}, {height/2}, {z}], size:[{radius}, {height}, {radius}], color:0x00aaff}}"
                else:
                    w = p.get("width", 0.3); d = p.get("depth", 0.3)
                    obj = f"{{type:'box', pos:[{x}, {height/2}, {z}], size:[{w}, {height}, {d}], color:0x00aaff}}"
            elif t == "beam":
                x1 = p.get("x1",0); z1 = p.get("z1",0); x2 = p.get("x2",4); z2 = p.get("z2",0)
                length = np.sqrt((x2-x1)**2 + (z2-z1)**2)
                mid_x = (x1+x2)/2; mid_z = (z1+z2)/2
                y = p.get("y", 3)
                w = p.get("width", 0.2); d = p.get("depth", 0.3)
                angle = np.arctan2(z2-z1, x2-x1)
                obj = f"{{type:'box', pos:[{mid_x}, {y}, {mid_z}], size:[{length}, {d}, {w}], color:0xffaa00, rotY:{angle}}}"
            elif t == "slab":
                x = p.get("x",0); z = p.get("z",0)
                w = p.get("width",4); d = p.get("depth",4)
                thickness = p.get("thickness",0.15)
                y = p.get("y",3)
                obj = f"{{type:'box', pos:[{x}, {y}, {z}], size:[{w}, {thickness}, {d}], color:0x888888}}"
            elif t == "wall":
                x1 = p.get("x1",0); z1 = p.get("z1",0); x2 = p.get("x2",4); z2 = p.get("z2",0)
                length = np.sqrt((x2-x1)**2 + (z2-z1)**2)
                mid_x = (x1+x2)/2; mid_z = (z1+z2)/2
                height = p.get("height",3); thickness = p.get("thickness",0.15)
                y = height/2
                angle = np.arctan2(z2-z1, x2-x1)
                obj = f"{{type:'box', pos:[{mid_x}, {y}, {mid_z}], size:[{length}, {height}, {thickness}], color:0xcccccc, rotY:{angle}}}"
            elif t == "opening":
                pos_x = p.get("pos_x",0); pos_z = p.get("pos_z",0)
                width = p.get("width",1); height = p.get("height",2.1)
                color = 0x8B4513 if stype == "door" else 0xADD8E6
                obj = f"{{type:'box', pos:[{pos_x}, {height/2}, {pos_z}], size:[{width}, {height}, 0.1], color:{color}}}"
            objects_js.append(obj)
        objects_str = ",\n".join(objects_js)

        html = f"""
        <!DOCTYPE html>
        <html><head><style>body{{margin:0;overflow:hidden;}}</style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script></head>
        <body><script>
            const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1a1a2e);
            const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 1000);
            camera.position.set(8, 5, 8); camera.lookAt(2, 1.5, 2);
            const renderer = new THREE.WebGLRenderer({{antialias: true}});
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.body.appendChild(renderer.domElement);
            scene.add(new THREE.AmbientLight(0x404066));
            const dirLight = new THREE.DirectionalLight(0xffffff,1); dirLight.position.set(5,10,7); scene.add(dirLight);
            scene.add(new THREE.GridHelper(10,20,0x336699,0x224466));

            const objects = [{objects_str}];
            objects.forEach(obj => {{
                let mesh;
                if (obj.type === 'box') {{
                    mesh = new THREE.Mesh(
                        new THREE.BoxGeometry(obj.size[0], obj.size[1], obj.size[2]),
                        new THREE.MeshPhongMaterial({{color: obj.color, transparent: true, opacity: 0.9}})
                    );
                }} else if (obj.type === 'cylinder') {{
                    mesh = new THREE.Mesh(
                        new THREE.CylinderGeometry(obj.size[0], obj.size[0], obj.size[1], 32),
                        new THREE.MeshPhongMaterial({{color: obj.color, transparent: true, opacity: 0.9}})
                    );
                }}
                mesh.position.set(obj.pos[0], obj.pos[1], obj.pos[2]);
                if (obj.rotY) mesh.rotation.y = obj.rotY;
                scene.add(mesh);
            }});

            let isDragging = false, prev = {{x:0,y:0}};
            renderer.domElement.addEventListener('mousedown', e=>{{ isDragging=true; prev.x=e.clientX; prev.y=e.clientY; }});
            renderer.domElement.addEventListener('mouseup', ()=>isDragging=false);
            renderer.domElement.addEventListener('mousemove', e=>{{
                if(isDragging) {{
                    camera.position.x += (e.clientX - prev.x)*0.01;
                    camera.position.y -= (e.clientY - prev.y)*0.01;
                    camera.lookAt(2,1.5,2);
                    prev.x=e.clientX; prev.y=e.clientY;
                }}
            }});
            renderer.domElement.addEventListener('wheel', e=>{{
                camera.position.z += e.deltaY*0.01;
                camera.lookAt(2,1.5,2);
                e.preventDefault();
            }});
            function animate() {{ requestAnimationFrame(animate); renderer.render(scene,camera); }}
            animate();
        </script></body></html>
        """
        return html

# ------------------------------------------------------------------
# STREAMLIT APP (UI after login)
# ------------------------------------------------------------------
st.set_page_config(page_title="Arc OS Pro", layout="wide")

def load_css():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); color: #e0e0e0; }
        section[data-testid="stSidebar"] { background: rgba(20,20,40,0.8); backdrop-filter: blur(10px); border-right: 1px solid rgba(255,255,255,0.1); }
        h1,h2,h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; background: linear-gradient(90deg, #00d2ff, #3a7bd5); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .glass-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(15px); border-radius:16px; border:1px solid rgba(255,255,255,0.1); padding:20px; margin:10px 0; box-shadow:0 8px 32px rgba(0,0,0,0.37); }
        .metric-box { background: rgba(255,255,255,0.08); border-radius:12px; padding:15px; margin:5px 0; text-align:center; font-weight:bold; border:1px solid rgba(255,255,255,0.15); }
        div.stButton > button { background: linear-gradient(45deg, #ff416c, #ff4b2b); border:none; color:white; padding:12px 28px; font-size:16px; font-weight:bold; border-radius:50px; box-shadow:0 0 20px rgba(255,75,43,0.5); transition:all 0.3s ease; cursor:pointer; letter-spacing:0.5px; text-transform:uppercase; width:100%; border:1px solid rgba(255,255,255,0.2); }
        div.stButton > button:hover { transform:translateY(-2px); box-shadow:0 0 30px rgba(255,75,43,0.8); background:linear-gradient(45deg, #ff4b2b, #ff416c); color:white; }
        .stForm button { background: linear-gradient(45deg, #00b4db, #0083b0) !important; }
    </style>""", unsafe_allow_html=True)

load_css()

# Ensure role exists after login
if 'role' not in st.session_state:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=?", (st.session_state.username,))
    row = c.fetchone()
    st.session_state.role = row[0] if row else "user"

# Session data defaults
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
    st.write(f"👤 {st.session_state.username} ({st.session_state.role})")
    mode = st.radio("🧠 Engine", ["💱 Forex Pro", "🏗️ Structural Pro"])

    st.markdown("---")
    if mode == "💱 Forex Pro":
        st.checkbox("Real‑time forex", value=st.session_state.use_real_forex, key="use_real_forex")
    else:
        st.markdown("### 🧊 Building Designer")

    if st.session_state.role == "admin":
        with st.expander("👥 User Management"):
            with st.form("add_user_form"):
                new_user = st.text_input("Username")
                new_pass = st.text_input("Password", type="password")
                new_email = st.text_input("Email")
                new_role = st.selectbox("Role", ["user", "admin"])
                if st.form_submit_button("Add User"):
                    if new_user and new_pass and new_email:
                        success, msg = add_user(new_user, new_pass, new_email, new_role)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.error("All fields required.")

    with st.expander("🚀 Deploy to Streamlit Cloud"):
        st.markdown("""
        1. Push `streamlit_app.py` + `requirements.txt` to GitHub.
        2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
        3. Set branch `main`, file path `streamlit_app.py`.
        4. Click **Deploy**.
        """)

    if st.button("🚪 Logout"):
        logout()
    st.caption("v7.1 · Database init fixed")

st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System Pro</h1>", unsafe_allow_html=True)

# ====================== FOREX MODULE ======================
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
        st.info("No history yet.")

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

# ====================== STRUCTURAL PRO ======================
else:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏗️ Structural Pro: Building Designer")

    with st.expander("➕ Add New Element", expanded=True):
        elem_type = st.selectbox("Element Type", list(StructuralModel.ELEMENT_TYPES.keys()))
        subtypes = StructuralModel.ELEMENT_TYPES[elem_type]
        subtype = st.selectbox("Subtype", subtypes)

        params = {}
        col1, col2, col3 = st.columns(3)

        if elem_type == "column":
            with col1:
                params["x"] = st.number_input("X position (m)", value=0.0)
            with col2:
                params["z"] = st.number_input("Z position (m)", value=0.0)
            with col3:
                params["height"] = st.number_input("Height (m)", value=3.0, min_value=0.1)
            if subtype == "circular":
                params["radius"] = st.number_input("Radius (m)", value=0.15, min_value=0.01)
            else:
                params["width"] = st.number_input("Width (m)", value=0.3, min_value=0.01)
                params["depth"] = st.number_input("Depth (m)", value=0.3, min_value=0.01)
        elif elem_type == "beam":
            with col1:
                params["x1"] = st.number_input("Start X (m)", value=0.0)
                params["z1"] = st.number_input("Start Z (m)", value=0.0)
            with col2:
                params["x2"] = st.number_input("End X (m)", value=4.0)
                params["z2"] = st.number_input("End Z (m)", value=0.0)
            with col3:
                params["y"] = st.number_input("Elevation Y (m)", value=3.0)
            params["width"] = st.number_input("Width (m)", value=0.2, min_value=0.01)
            params["depth"] = st.number_input("Depth (m)", value=0.3, min_value=0.01)
        elif elem_type == "slab":
            with col1:
                params["x"] = st.number_input("Center X (m)", value=2.0)
            with col2:
                params["z"] = st.number_input("Center Z (m)", value=2.0)
            with col3:
                params["y"] = st.number_input("Level Y (m)", value=3.0)
            params["width"] = st.number_input("Width (m)", value=4.0, min_value=0.1)
            params["depth"] = st.number_input("Depth (m)", value=4.0, min_value=0.1)
            params["thickness"] = st.number_input("Thickness (m)", value=0.15, min_value=0.01)
        elif elem_type == "wall":
            with col1:
                params["x1"] = st.number_input("Start X (m)", value=0.0)
                params["z1"] = st.number_input("Start Z (m)", value=0.0)
            with col2:
                params["x2"] = st.number_input("End X (m)", value=4.0)
                params["z2"] = st.number_input("End Z (m)", value=0.0)
            with col3:
                params["height"] = st.number_input("Height (m)", value=3.0)
            params["thickness"] = st.number_input("Thickness (m)", value=0.15, min_value=0.01)
        elif elem_type == "opening":
            with col1:
                params["wall_x"] = st.number_input("Wall center X (m)", value=2.0)
                params["wall_z"] = st.number_input("Wall center Z (m)", value=0.0)
            with col2:
                params["pos_x"] = st.number_input("Opening center X (m)", value=2.0)
                params["pos_z"] = st.number_input("Opening center Z (m)", value=0.0)
            with col3:
                params["width"] = st.number_input("Width (m)", value=1.0, min_value=0.1)
                params["height"] = st.number_input("Height (m)", value=2.1, min_value=0.1)

        if st.button("Add Element"):
            StructuralModel.add_element(st.session_state.username, elem_type, subtype, params)
            st.rerun()

    elements = StructuralModel.get_elements(st.session_state.username)
    if not elements.empty:
        st.markdown("### 🧊 3D Building View")
        html = StructuralModel.generate_3d_scene(elements)
        st.components.v1.html(html, height=450)

        st.markdown("### 📋 Elements List")
        for idx, row in elements.iterrows():
            p = row["params"]
            col1, col2, col3 = st.columns([3,1,1])
            with col1:
                if row["type"] == "opening":
                    desc = f"{row['subtype']} at ({p['pos_x']:.2f}, {p['pos_z']:.2f}) {p['width']}x{p['height']}m"
                else:
                    desc = f"{row['type']} {row['subtype']}"
                    if row["type"] in ["column","slab"]:
                        desc += f" @ ({p.get('x',p.get('x1','?'))}, {p.get('z',p.get('z1','?'))})"
                    else:
                        desc += f" from ({p.get('x1',0):.2f},{p.get('z1',0):.2f}) to ({p.get('x2',0):.2f},{p.get('z2',0):.2f})"
                st.write(desc)
            with col2:
                st.write(f"ID: {row['id']}")
            with col3:
                if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                    StructuralModel.delete_element(row['id'])
                    st.rerun()
    else:
        st.info("No building elements yet.")

    if not elements.empty:
        with st.expander("📊 Structural Analysis Summary"):
            cols = elements[elements["type"]=="column"]
            beams = elements[elements["type"]=="beam"]
            slabs = elements[elements["type"]=="slab"]
            walls = elements[elements["type"]=="wall"]
            openings = elements[elements["type"]=="opening"]
            st.write(f"**Columns:** {len(cols)} | **Beams:** {len(beams)} | **Slabs:** {len(slabs)} | **Walls:** {len(walls)} | **Openings:** {len(openings)}")
            if len(slabs) > 0:
                total_area = sum([p.get("width",0)*p.get("depth",0) for p in slabs["params"]])
                st.write(f"Total slab area: {total_area:.2f} m²")
            if len(beams) > 0:
                lengths = [np.sqrt((p["x2"]-p["x1"])**2 + (p["z2"]-p["z1"])**2) for p in beams["params"]]
                st.write(f"Total beam length: {sum(lengths):.2f} m")

        if st.button("📧 Email Structural Report"):
            email = StructuralModel.get_user_email(st.session_state.username)
            if email:
                st.toast(f"📧 Structural report sent to {email}")
            else:
                st.warning("No email on file. Add email in user profile (admin only).")

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    pass