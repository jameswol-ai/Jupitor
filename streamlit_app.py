import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime, timedelta
import hashlib
import json
import smtplib
from email.message import EmailMessage

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
    c.execute('''CREATE TABLE IF NOT EXISTS wallet_transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT, type TEXT, amount REAL,
                  phone TEXT, provider TEXT, reference TEXT,
                  status TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

def get_db_connection():
    return sqlite3.connect("arc_os.db")

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
        send_email_notification(email, "Account Created", f"Hello {username}, your Arc OS account has been created.")
        st.toast(f"📧 Account created for {email} (email sent)")
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
# EMAIL SENDING (via Streamlit secrets)
# ------------------------------------------------------------------
def send_email_notification(to_email, subject, body):
    """Send email using SMTP credentials from Streamlit secrets."""
    try:
        sender = st.secrets["email_sender"]
        password = st.secrets["email_password"]
        smtp_server = st.secrets.get("smtp_server", "smtp.gmail.com")
        smtp_port = st.secrets.get("smtp_port", 587)

        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.warning(f"Email could not be sent: {e}")
        return False

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
# MOBILE MONEY WALLET (Simulated East‑African Integration)
# ------------------------------------------------------------------
class MobileWallet:
    PROVIDERS = ["M-Pesa (Kenya)", "Airtel Money (Uganda)", "MTN MoMo (Uganda)"]

    @staticmethod
    def get_balance(username):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT SUM(CASE WHEN type='deposit' THEN amount ELSE -amount END) FROM wallet_transactions WHERE username=? AND status='completed'",
                  (username,))
        row = c.fetchone()
        return row[0] if row[0] is not None else 0.0

    @staticmethod
    def deposit_request(username, phone, amount, provider):
        """Simulate STK push: create a pending transaction and return a reference."""
        ref = f"ARC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO wallet_transactions
                     (username, type, amount, phone, provider, reference, status, timestamp)
                     VALUES (?, 'deposit', ?, ?, ?, ?, 'pending', ?)''',
                  (username, amount, phone, provider, ref, datetime.now().isoformat()))
        conn.commit()
        return ref

    @staticmethod
    def confirm_deposit(reference):
        """Simulate user entering PIN and completing the transaction."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE wallet_transactions SET status='completed' WHERE reference=?", (reference,))
        conn.commit()
        return True

    @staticmethod
    def get_transactions(username, limit=20):
        conn = get_db_connection()
        df = pd.read_sql_query(
            "SELECT * FROM wallet_transactions WHERE username=? ORDER BY timestamp DESC LIMIT ?",
            conn, params=(username, limit))
        return df

# ------------------------------------------------------------------
# FOREX ENGINE (Real-time via ExchangeRate-API)
# ------------------------------------------------------------------
class ForexEngine:
    PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "UGX/USD", "KES/USD", "SSP/USD"]

    @staticmethod
    def fetch_latest_rates():
        live_rates = {}
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
        except:
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
# AI TRADING SIGNALS (RSI + MACD)
# ------------------------------------------------------------------
class TradingSignals:
    @staticmethod
    def compute_rsi(prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        for i in range(period, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta
            up = (up * (period-1) + upval) / period
            down = (down * (period-1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        return rsi

    @staticmethod
    def compute_macd(prices, fast=12, slow=26, signal=9):
        ema_fast = pd.Series(prices).ewm(span=fast, adjust=False).mean()
        ema_slow = pd.Series(prices).ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.values, signal_line.values, histogram.values

    @staticmethod
    def generate_signals(df, pair):
        """Return buy/sell signals based on RSI and MACD."""
        prices = df[pair].values
        if len(prices) < 35:
            return []
        rsi = TradingSignals.compute_rsi(prices)
        macd, signal, hist = TradingSignals.compute_macd(prices)
        signals = []
        last_rsi = rsi[-1]
        last_macd = macd[-1]
        last_signal = signal[-1]
        prev_macd = macd[-2]
        prev_signal = signal[-2]
        # RSI condition
        if last_rsi < 30:
            signals.append(("BUY", "RSI oversold"))
        elif last_rsi > 70:
            signals.append(("SELL", "RSI overbought"))
        # MACD crossover
        if prev_macd < prev_signal and last_macd > last_signal:
            signals.append(("BUY", "MACD bullish crossover"))
        elif prev_macd > prev_signal and last_macd < last_signal:
            signals.append(("SELL", "MACD bearish crossover"))
        return signals

# ------------------------------------------------------------------
# FOREX & CRYPTO FORECAST ENGINE (Daily, Weekly, Monthly)
# ------------------------------------------------------------------
class ForexForecast:
    BASE_PRICES = {
        "EUR/USD": 1.08, "GBP/USD": 1.26, "USD/JPY": 144.5,
        "UGX/USD": 3750, "KES/USD": 145, "SSP/USD": 1100
    }
    DAILY_VOL = {
        "EUR/USD": 0.005, "GBP/USD": 0.006, "USD/JPY": 0.25,
        "UGX/USD": 15, "KES/USD": 0.8, "SSP/USD": 12
    }

    @staticmethod
    def generate_daily_history(days=90):
        np.random.seed(123)
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        df = pd.DataFrame(index=dates)
        for pair in ForexEngine.PAIRS:
            start = ForexForecast.BASE_PRICES[pair]
            vol = ForexForecast.DAILY_VOL[pair] * start
            drift = 0.0001 * start if pair in ["EUR/USD","GBP/USD"] else 0.01
            rets = np.random.normal(drift, vol, days)
            prices = start * np.exp(np.cumsum(rets / start))
            df[pair] = np.round(prices, 4)
        return df

    @staticmethod
    def forecast(df, horizon_days, pair):
        series = df[pair].tail(30)
        x = np.arange(len(series))
        y = series.values
        coeffs = np.polyfit(x, y, 1)
        last_idx = len(series) - 1
        future_x = np.array([last_idx + d for d in range(1, horizon_days+1)])
        forecast_y = np.polyval(coeffs, future_x)
        return np.round(forecast_y, 4)

class CryptoForecast:
    COINS = CryptoEngine.COINS if 'CryptoEngine' in dir() else ["bitcoin","ethereum","ripple","cardano","solana"]
    NAMES = {"bitcoin":"BTC","ethereum":"ETH","ripple":"XRP","cardano":"ADA","solana":"SOL"}
    BASE_PRICES = {"bitcoin": 67000, "ethereum": 3400, "ripple": 0.6, "cardano": 0.45, "solana": 170}
    DAILY_VOL = {"bitcoin": 1500, "ethereum": 120, "ripple": 0.03, "cardano": 0.02, "solana": 8}

    @staticmethod
    def generate_daily_history(days=90, live_prices=None):
        np.random.seed(456)
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        df = pd.DataFrame(index=dates)
        for coin in CryptoForecast.COINS:
            start = CryptoForecast.BASE_PRICES[coin]
            vol = CryptoForecast.DAILY_VOL[coin]
            drift = 0.0005 * start
            rets = np.random.normal(drift, vol, days)
            prices = start + np.cumsum(rets)
            prices = np.maximum(prices, 0.01)
            if live_prices and coin in live_prices and live_prices[coin] is not None:
                prices[-1] = live_prices[coin]
            df[coin] = np.round(prices, 2)
        return df

    @staticmethod
    def forecast(df, horizon_days, coin):
        series = df[coin].tail(30)
        x = np.arange(len(series))
        y = series.values
        coeffs = np.polyfit(x, y, 1)
        last_idx = len(series) - 1
        future_x = np.array([last_idx + d for d in range(1, horizon_days+1)])
        forecast_y = np.polyval(coeffs, future_x)
        return np.round(forecast_y, 2)

# ------------------------------------------------------------------
# CRYPTO ENGINE (Live via CoinGecko)
# ------------------------------------------------------------------
class CryptoEngine:
    COINS = ["bitcoin", "ethereum", "ripple", "cardano", "solana"]
    NAMES = {"bitcoin": "BTC", "ethereum": "ETH", "ripple": "XRP",
             "cardano": "ADA", "solana": "SOL"}

    @staticmethod
    def fetch_prices():
        try:
            ids = ",".join(CryptoEngine.COINS)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            prices = []
            for coin in CryptoEngine.COINS:
                info = data.get(coin, {})
                prices.append({
                    "Coin": CryptoEngine.NAMES[coin],
                    "Price (USD)": info.get("usd", None),
                    "24h Change %": round(info.get("usd_24h_change", 0), 2)
                })
            return pd.DataFrame(prices)
        except Exception as e:
            st.warning(f"Crypto fetch failed: {e}")
            return None

    @staticmethod
    def get_historical(coin_id, days=7):
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            prices = data["prices"]
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df.set_index("timestamp")
        except:
            return None

# ------------------------------------------------------------------
# ADVANCED STRUCTURAL ANALYSIS (FEM + Load Distribution)
# ------------------------------------------------------------------
class StructuralAnalysis:
    @staticmethod
    def truss_fem(nodes, elements, forces, constraints):
        n_nodes = len(nodes)
        ndof = 2 * n_nodes
        K = np.zeros((ndof, ndof))
        for (i, j, E, A) in elements:
            xi, yi = nodes[i]
            xj, yj = nodes[j]
            L = np.sqrt((xj-xi)**2 + (yj-yi)**2)
            c = (xj - xi) / L
            s = (yj - yi) / L
            k_local = (E * A / L) * np.array([
                [c*c, c*s, -c*c, -c*s],
                [c*s, s*s, -c*s, -s*s],
                [-c*c, -c*s, c*c, c*s],
                [-c*s, -s*s, c*s, s*s]
            ])
            dof_map = [2*i, 2*i+1, 2*j, 2*j+1]
            for a in range(4):
                for b in range(4):
                    K[dof_map[a], dof_map[b]] += k_local[a, b]
        free_dofs = []
        for node in range(n_nodes):
            if not constraints.get(node, (False,False))[0]:
                free_dofs.append(2*node)
            if not constraints.get(node, (False,False))[1]:
                free_dofs.append(2*node+1)
        K_free = K[np.ix_(free_dofs, free_dofs)]
        F_free = np.zeros(len(free_dofs))
        for node, (fx, fy) in forces.items():
            if 2*node in free_dofs:
                idx = free_dofs.index(2*node)
                F_free[idx] = fx
            if 2*node+1 in free_dofs:
                idx = free_dofs.index(2*node+1)
                F_free[idx] = fy
        try:
            u_free = np.linalg.solve(K_free, F_free)
        except np.linalg.LinAlgError:
            return None
        u = np.zeros(ndof)
        for i, dof in enumerate(free_dofs):
            u[dof] = u_free[i]
        disp = {i: (u[2*i], u[2*i+1]) for i in range(n_nodes)}
        return disp

    @staticmethod
    def beam_load_distribution(beam_length, load_type, load_mag, supports):
        if load_type == "Uniform (kN/m)":
            w = load_mag
            if supports == "simple":
                Ra = w * beam_length / 2
                Rb = w * beam_length / 2
                return {"Ra": Ra, "Rb": Rb}
            else:
                M_fixed = w * beam_length**2 / 2
                R_fixed = w * beam_length
                return {"R_fixed": R_fixed, "M_fixed": M_fixed}
        else:
            P = load_mag
            if supports == "simple":
                Ra = P / 2
                Rb = P / 2
                return {"Ra": Ra, "Rb": Rb}
            else:
                R_fixed = P
                M_fixed = P * beam_length
                return {"R_fixed": R_fixed, "M_fixed": M_fixed}

# ------------------------------------------------------------------
# BUILDING DESIGNER (3D) – unchanged
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
            send_email_notification(user_email, "Element Added", f"A new {elem_type} was added to your project.")
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
# STREAMLIT UI
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

if 'role' not in st.session_state:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=?", (st.session_state.username,))
    row = c.fetchone()
    st.session_state.role = row[0] if row else "user"

if 'forex_data' not in st.session_state:
    st.session_state.forex_data = ForexEngine.get_live_data(use_real=True)
if 'forex_volume' not in st.session_state:
    st.session_state.forex_volume = ForexEngine.get_volume()
if 'use_real_forex' not in st.session_state:
    st.session_state.use_real_forex = True

# ---------- Forecast data in session state ----------
if 'forex_daily_hist' not in st.session_state:
    st.session_state.forex_daily_hist = ForexForecast.generate_daily_history(90)
if 'crypto_live_prices' not in st.session_state:
    st.session_state.crypto_live_prices = CryptoEngine.fetch_prices()
if 'crypto_daily_hist' not in st.session_state:
    live_dict = {}
    if st.session_state.crypto_live_prices is not None:
        for _, row in st.session_state.crypto_live_prices.iterrows():
            for cid, name in CryptoEngine.NAMES.items():
                if name == row["Coin"]:
                    live_dict[cid] = row["Price (USD)"]
    st.session_state.crypto_daily_hist = CryptoForecast.generate_daily_history(90, live_dict)

# Voice command handling
if 'voice_command' not in st.session_state:
    st.session_state.voice_command = None

# ------------------------------------------------------------------
# VOICE COMMAND (Web Speech API via st_javascript)
# ------------------------------------------------------------------
def voice_command_ui():
    col1, col2 = st.columns([0.9, 0.1])
    with col2:
        if st.button("🎤 Voice Command"):
            # JavaScript to start speech recognition
            js_code = """
            <script>
            (function() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) {
                    alert("Voice recognition not supported in this browser.");
                    return 'unsupported';
                }
                const recognition = new SpeechRecognition();
                recognition.lang = 'en-US';
                recognition.interimResults = false;
                recognition.maxAlternatives = 1;
                recognition.onresult = function(event) {
                    const transcript = event.results[0][0].transcript.trim().toLowerCase();
                    window.parent.postMessage({type: 'streamlit:setComponentValue', value: transcript}, '*');
                };
                recognition.onerror = function(event) {
                    window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'error: ' + event.error}, '*');
                };
                recognition.start();
            })();
            </script>
            """
            result = st_javascript(js_code)
            if result and result != "unsupported":
                st.session_state.voice_command = result
                st.rerun()

    if st.session_state.voice_command:
        cmd = st.session_state.voice_command.lower()
        st.info(f"Voice command: {cmd}")
        # Process command
        mode_map = {
            "forex": "💱 Forex Pro",
            "structural": "🏗️ Structural Pro",
            "crypto": "₿ Crypto Tracker",
            "wallet": "💳 Mobile Wallet",
        }
        if cmd in mode_map:
            st.session_state.mode = mode_map[cmd]
            st.success(f"Switched to {mode_map[cmd]}")
        elif "balance" in cmd:
            st.session_state.mode = "💳 Mobile Wallet"
            st.success("Showing wallet balance")
        elif "forecast" in cmd:
            st.session_state.mode = "💱 Forex Pro"
            st.success("Opening forecasts")
        elif "signal" in cmd:
            st.session_state.mode = "💱 Forex Pro"
            st.success("Opening trading signals")
        elif "logout" in cmd:
            logout()
        else:
            st.warning("Command not recognized. Try: forex, crypto, structural, wallet, forecast, signals, balance, logout")
        st.session_state.voice_command = None

# ------------------------------------------------------------------
# SIDEBAR & MODE SELECTION
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Arc OS Pro")
    st.write(f"👤 {st.session_state.username} ({st.session_state.role})")
    mode_options = ["💱 Forex Pro", "🏗️ Structural Pro", "₿ Crypto Tracker", "💳 Mobile Wallet"]
    if 'mode' not in st.session_state:
        st.session_state.mode = mode_options[0]
    mode = st.radio("🧠 Engine", mode_options, index=mode_options.index(st.session_state.mode))
    st.session_state.mode = mode

    st.markdown("---")
    if mode == "💱 Forex Pro":
        st.checkbox("Real‑time forex", value=st.session_state.use_real_forex, key="use_real_forex")
    elif mode == "🏗️ Structural Pro":
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
        2. Set secrets: `email_sender`, `email_password`, `smtp_server`, `smtp_port`.
        3. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
        4. Set branch `main`, file path `streamlit_app.py`, deploy.
        """)

    if st.button("🚪 Logout"):
        logout()
    st.caption("v9.0 · Wallet + Signals + Voice")

st.markdown("<h1 style='text-align: center;'>🌌 Arc | AI Operating System Pro</h1>", unsafe_allow_html=True)
voice_command_ui()   # Voice button at top

# ====================== FOREX MODULE ======================
if mode == "💱 Forex Pro":
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

    # ---------- AI SIGNALS (RSI + MACD) ----------
    with st.expander("📡 AI Trading Signals (RSI & MACD)", expanded=False):
        st.markdown("Real‑time signals based on the 1‑minute live data.")
        signal_pair = st.selectbox("Choose pair for signals", ForexEngine.PAIRS, key="signal_pair")
        signals = TradingSignals.generate_signals(forex_df, signal_pair)
        if signals:
            for sig_type, reason in signals:
                color = "green" if sig_type == "BUY" else "red"
                st.markdown(f"<span style='color:{color}; font-weight:bold;'>{sig_type}</span> – {reason}", unsafe_allow_html=True)
        else:
            st.write("No strong signals at the moment.")
        # Show RSI value
        prices = forex_df[signal_pair].values
        rsi = TradingSignals.compute_rsi(prices)
        st.metric(f"RSI (14) for {signal_pair}", f"{rsi[-1]:.1f}")

    # ---------- FOREX FORECAST SECTION ----------
    st.subheader("🔮 Forex Forecasts (Daily, Weekly, Monthly)")
    forecast_horizon = st.radio("Forecast period", ["1 Day", "7 Days (Week)", "30 Days (Month)"], horizontal=True)
    horizon_map = {"1 Day": 1, "7 Days (Week)": 7, "30 Days (Month)": 30}
    days = horizon_map[forecast_horizon]
    daily_hist = st.session_state.forex_daily_hist

    forecast_table = []
    chart_data = {}
    for pair in ForexEngine.PAIRS:
        fcast = ForexForecast.forecast(daily_hist, days, pair)
        forecast_table.append({"Pair": pair, "Latest": daily_hist[pair].iloc[-1],
                               "Forecast": fcast[-1], "Change": round(fcast[-1] - daily_hist[pair].iloc[-1], 4)})
        hist_part = daily_hist[pair].tail(30)
        idx_hist = list(hist_part.index)
        idx_fut = pd.date_range(idx_hist[-1] + pd.Timedelta(days=1), periods=days, freq='D')
        combined = np.concatenate([hist_part.values, fcast])
        chart_data[pair] = pd.Series(combined, index=list(idx_hist)+list(idx_fut))

    fdf = pd.DataFrame(forecast_table)
    st.dataframe(fdf.style.applymap(lambda x: 'color: #00ff88' if isinstance(x, (int,float)) and x>0 else 'color: #ff4b4b',
                                    subset=['Change']), use_container_width=True)

    pair_for_chart = st.selectbox("Select pair for forecast chart", ForexEngine.PAIRS, key="forex_fcast_chart")
    if pair_for_chart in chart_data:
        st.line_chart(chart_data[pair_for_chart])

    if st.button("🔄 Refresh Live Data", key="forex_refresh"):
        st.session_state.forex_data = ForexEngine.get_live_data(use_real=st.session_state.use_real_forex)
        st.session_state.forex_volume = ForexEngine.get_volume()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== CRYPTO MODULE ======================
elif mode == "₿ Crypto Tracker":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("₿ Live Crypto Prices")
    prices_df = st.session_state.crypto_live_prices
    if prices_df is not None:
        cols = st.columns(len(prices_df))
        for i, row in prices_df.iterrows():
            with cols[i]:
                change = row["24h Change %"]
                color = "#00ff88" if change >= 0 else "#ff4b4b"
                st.markdown(f"""<div class="metric-box">
                    <span style="font-size:18px;">{row['Coin']}</span><br>
                    <span style="font-size:24px;">${row['Price (USD)']:,.2f}</span><br>
                    <span style="font-size:14px; color:{color};">24h: {change:.2f}%</span>
                </div>""", unsafe_allow_html=True)

        selected = st.selectbox("Select coin for historical chart", CryptoEngine.COINS)
        hist = CryptoEngine.get_historical(selected, days=7)
        if hist is not None:
            st.line_chart(hist["price"])

        st.subheader("🔮 Crypto Forecasts (Daily, Weekly, Monthly)")
        crypto_horizon = st.radio("Forecast period", ["1 Day", "7 Days (Week)", "30 Days (Month)"], key="crypto_horizon", horizontal=True)
        horizon_map_c = {"1 Day": 1, "7 Days (Week)": 7, "30 Days (Month)": 30}
        c_days = horizon_map_c[crypto_horizon]
        crypto_hist = st.session_state.crypto_daily_hist
        c_forecast_table = []
        c_chart_data = {}
        for coin in CryptoForecast.COINS:
            fcast = CryptoForecast.forecast(crypto_hist, c_days, coin)
            c_forecast_table.append({"Coin": CryptoForecast.NAMES[coin],
                                     "Latest": crypto_hist[coin].iloc[-1],
                                     "Forecast": fcast[-1],
                                     "Change": round(fcast[-1] - crypto_hist[coin].iloc[-1], 2)})
            hist_part = crypto_hist[coin].tail(30)
            idx_hist = list(hist_part.index)
            idx_fut = pd.date_range(idx_hist[-1] + pd.Timedelta(days=1), periods=c_days, freq='D')
            combined = np.concatenate([hist_part.values, fcast])
            c_chart_data[coin] = pd.Series(combined, index=list(idx_hist)+list(idx_fut))

        c_df = pd.DataFrame(c_forecast_table)
        st.dataframe(c_df.style.applymap(lambda x: 'color: #00ff88' if isinstance(x, (int,float)) and x>0 else 'color: #ff4b4b',
                                         subset=['Change']), use_container_width=True)

        coin_for_chart = st.selectbox("Select coin for forecast chart", CryptoForecast.COINS, format_func=lambda x: CryptoForecast.NAMES[x], key="crypto_fcast_chart")
        if coin_for_chart in c_chart_data:
            st.line_chart(c_chart_data[coin_for_chart])

    else:
        st.error("Could not fetch crypto data.")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== STRUCTURAL PRO ======================
elif mode == "🏗️ Structural Pro":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🏗️ Structural Pro: Analysis & Design")
    tab1, tab2, tab3 = st.tabs(["3D Building Designer", "Beam Load Distribution", "Truss FEM"])

    with tab1:
        with st.expander("➕ Add New Element", expanded=True):
            elem_type = st.selectbox("Element Type", list(StructuralModel.ELEMENT_TYPES.keys()), key="3d_type")
            subtypes = StructuralModel.ELEMENT_TYPES[elem_type]
            subtype = st.selectbox("Subtype", subtypes, key="3d_sub")
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
                    params["x1"] = st.number_input("Start X", value=0.0)
                    params["z1"] = st.number_input("Start Z", value=0.0)
                with col2:
                    params["x2"] = st.number_input("End X", value=4.0)
                    params["z2"] = st.number_input("End Z", value=0.0)
                with col3:
                    params["y"] = st.number_input("Elevation Y", value=3.0)
                params["width"] = st.number_input("Width (m)", value=0.2, min_value=0.01)
                params["depth"] = st.number_input("Depth (m)", value=0.3, min_value=0.01)
            elif elem_type == "slab":
                with col1:
                    params["x"] = st.number_input("Center X", value=2.0)
                with col2:
                    params["z"] = st.number_input("Center Z", value=2.0)
                with col3:
                    params["y"] = st.number_input("Level Y", value=3.0)
                params["width"] = st.number_input("Width", value=4.0, min_value=0.1)
                params["depth"] = st.number_input("Depth", value=4.0, min_value=0.1)
                params["thickness"] = st.number_input("Thickness", value=0.15, min_value=0.01)
            elif elem_type == "wall":
                with col1:
                    params["x1"] = st.number_input("Start X", value=0.0)
                    params["z1"] = st.number_input("Start Z", value=0.0)
                with col2:
                    params["x2"] = st.number_input("End X", value=4.0)
                    params["z2"] = st.number_input("End Z", value=0.0)
                with col3:
                    params["height"] = st.number_input("Height", value=3.0)
                params["thickness"] = st.number_input("Thickness", value=0.15, min_value=0.01)
            elif elem_type == "opening":
                with col1:
                    params["wall_x"] = st.number_input("Wall center X", value=2.0)
                    params["wall_z"] = st.number_input("Wall center Z", value=0.0)
                with col2:
                    params["pos_x"] = st.number_input("Opening X", value=2.0)
                    params["pos_z"] = st.number_input("Opening Z", value=0.0)
                with col3:
                    params["width"] = st.number_input("Width", value=1.0, min_value=0.1)
                    params["height"] = st.number_input("Height", value=2.1, min_value=0.1)
            if st.button("Add Element", key="add_elem"):
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
                        desc = f"{row['subtype']} at ({p['pos_x']:.2f}, {p['pos_z']:.2f})"
                    else:
                        desc = f"{row['type']} {row['subtype']}"
                        if row["type"] in ["column","slab"]:
                            desc += f" @ ({p.get('x',0)}, {p.get('z',0)})"
                        else:
                            desc += f" from ({p.get('x1',0)},{p.get('z1',0)}) to ({p.get('x2',0)},{p.get('z2',0)})"
                    st.write(desc)
                with col2:
                    st.write(f"ID: {row['id']}")
                with col3:
                    if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                        StructuralModel.delete_element(row['id'])
                        st.rerun()
        else:
            st.info("No building elements yet.")

    with tab2:
        st.subheader("📐 Beam Load Distribution")
        beam_len = st.number_input("Beam Length (m)", 1.0, 20.0, 5.0)
        load_type = st.selectbox("Load Type", ["Uniform (kN/m)", "Point Load (kN)"])
        load_val = st.number_input("Load Magnitude", 1.0, 500.0, 20.0)
        supports = st.selectbox("Support Type", ["simple", "cantilever"])
        if st.button("Calculate Reactions"):
            reactions = StructuralAnalysis.beam_load_distribution(beam_len, load_type, load_val, supports)
            st.write("**Reactions:**")
            for k, v in reactions.items():
                st.metric(k, f"{v:.2f} kN" if "M" not in k else f"{v:.2f} kN·m")
            email = StructuralModel.get_user_email(st.session_state.username)
            if email:
                send_email_notification(email, "Beam Analysis Results", str(reactions))
                st.toast(f"📧 Results sent to {email}")

    with tab3:
        st.subheader("🧮 Simple 2D Truss FEM")
        st.markdown("Define nodes (x,y), elements (node i, node j, E, A), forces, and constraints.")
        nodes_input = st.text_area("Nodes (one per line: x,y)", "0,0\n4,0\n2,3")
        elements_input = st.text_area("Elements (one per line: i,j,E,A)", "0,2,210e9,0.01\n2,1,210e9,0.01\n0,1,210e9,0.005")
        forces_input = st.text_area("Forces (node:fx,fy)", "2:0,-10")
        constraints_input = st.text_area("Constraints (node:dx,dy e.g. 0:True,True)", "0:True,True\n1:False,True")
        if st.button("Run FEM Analysis"):
            try:
                nodes = [tuple(map(float, line.split(','))) for line in nodes_input.strip().split('\n')]
                elements = []
                for line in elements_input.strip().split('\n'):
                    parts = line.split(',')
                    i, j, E, A = int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3])
                    elements.append((i, j, E, A))
                forces = {}
                for line in forces_input.strip().split('\n'):
                    node, vec = line.split(':')
                    fx, fy = map(float, vec.split(','))
                    forces[int(node)] = (fx, fy)
                constraints = {}
                for line in constraints_input.strip().split('\n'):
                    node, vals = line.split(':')
                    dx, dy = vals.split(',')
                    constraints[int(node)] = (dx.strip()=='True', dy.strip()=='True')
                disp = StructuralAnalysis.truss_fem(nodes, elements, forces, constraints)
                if disp:
                    st.write("**Node Displacements:**")
                    for node, (dx, dy) in disp.items():
                        st.write(f"Node {node}: Δx = {dx:.6f} m, Δy = {dy:.6f} m")
                    email = StructuralModel.get_user_email(st.session_state.username)
                    if email:
                        send_email_notification(email, "FEM Analysis Results", str(disp))
                        st.toast(f"📧 Results sent to {email}")
                else:
                    st.error("Singular matrix. Check constraints.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# ====================== MOBILE WALLET ======================
elif mode == "💳 Mobile Wallet":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💳 Mobile Money Wallet (East Africa)")
    balance = MobileWallet.get_balance(st.session_state.username)
    st.metric("Your Balance (USD)", f"${balance:,.2f}")

    with st.expander("➕ Deposit via Mobile Money", expanded=False):
        with st.form("deposit_form"):
            phone = st.text_input("Phone Number (e.g., 2567XXXXXXXX)")
            amount = st.number_input("Amount (USD)", min_value=1.0, step=1.0)
            provider = st.selectbox("Provider", MobileWallet.PROVIDERS)
            if st.form_submit_button("Request STK Push"):
                if phone and amount > 0:
                    ref = MobileWallet.deposit_request(st.session_state.username, phone, amount, provider)
                    st.success(f"STK Push sent to {phone}. Reference: {ref}")
                    st.info("Simulate: Enter PIN to confirm...")
                    if st.button("Confirm Payment (Simulate)"):
                        MobileWallet.confirm_deposit(ref)
                        st.success("Deposit confirmed! Balance updated.")
                        st.rerun()
                else:
                    st.error("Please fill phone and amount.")

    st.subheader("📋 Transaction History")
    trans = MobileWallet.get_transactions(st.session_state.username)
    if not trans.empty:
        st.dataframe(trans[['timestamp','type','amount','phone','provider','status']], use_container_width=True)
    else:
        st.write("No transactions yet.")
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    pass
