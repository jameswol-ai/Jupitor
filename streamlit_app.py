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
# GLOBAL CONSTANTS
# ------------------------------------------------------------------
CRYPTO_COINS = ["bitcoin", "ethereum", "ripple", "cardano", "solana"]
CRYPTO_NAMES = {"bitcoin": "BTC", "ethereum": "ETH", "ripple": "XRP",
                "cardano": "ADA", "solana": "SOL"}

# ------------------------------------------------------------------
# DATABASE SETUP
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
# EMAIL SENDING
# ------------------------------------------------------------------
def send_email_notification(to_email, subject, body):
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
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ------------------------------------------------------------------
# MOBILE MONEY WALLET (fixed errors)
# ------------------------------------------------------------------
class MobileWallet:
    PROVIDERS = ["M-Pesa (Kenya)", "Airtel Money (Uganda)", "MTN MoMo (Uganda)"]

    @staticmethod
    def get_balance(username):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT SUM(CASE WHEN type='deposit' THEN amount WHEN type='withdrawal' THEN -amount ELSE 0 END) FROM wallet_transactions WHERE username=? AND status='completed'", (username,))
        row = c.fetchone()
        return row[0] if row[0] is not None else 0.0

    @staticmethod
    def deposit_request(username, phone, amount, provider):
        ref = f"DEP{datetime.now().strftime('%Y%m%d%H%M%S')}"
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
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE wallet_transactions SET status='completed' WHERE reference=?", (reference,))
        conn.commit()
        return True

    @staticmethod
    def withdraw_request(username, phone, amount, provider):
        balance = MobileWallet.get_balance(username)
        if amount > balance:
            return None, "Insufficient balance."
        ref = f"WTH{datetime.now().strftime('%Y%m%d%H%M%S')}"
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO wallet_transactions
                     (username, type, amount, phone, provider, reference, status, timestamp)
                     VALUES (?, 'withdrawal', ?, ?, ?, ?, 'pending', ?)''',
                  (username, amount, phone, provider, ref, datetime.now().isoformat()))
        conn.commit()
        return ref, "Withdrawal request submitted."

    @staticmethod
    def confirm_withdrawal(reference):
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
# FOREX ENGINE (unchanged)
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
            pair_map = {
                "EUR/USD": "EUR", "GBP/USD": "GBP", "USD/JPY": "JPY",
                "UGX/USD": "UGX", "KES/USD": "KES", "SSP/USD": "SSP"
            }
            for pair, code in pair_map.items():
                if code in usd_to:
                    if pair in ["EUR/USD", "GBP/USD"]:
                        live_rates[pair] = round(1 / usd_to[code], 4)
                    else:
                        live_rates[pair] = round(usd_to[code], 4)
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
                    base = live.get(pair, defaults.get(pair, 1.0))
                    vol = base * 0.0002
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
            "SELECT timestamp, rate FROM forex_quotes WHERE pair=? ORDER BY timestamp DESC LIMIT ?",
            conn, params=(pair, limit))
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
    def get_volume(minutes=60):
        np.random.seed(99)
        now = datetime.now()
        times = [now - timedelta(minutes=i) for i in range(minutes)][::-1]
        volume = np.random.randint(500, 5000, minutes)
        return pd.DataFrame({"Time": times, "Volume": volume})

# ------------------------------------------------------------------
# TRADING SIGNALS (RSI + MACD) – used by Jup AI
# ------------------------------------------------------------------
class TradingSignals:
    @staticmethod
    def compute_rsi(prices, period=14):
        deltas = np.diff(prices)
        if len(deltas) < period:
            return np.full_like(prices, np.nan)
        up = np.mean(np.maximum(deltas[:period], 0))
        down = np.mean(np.abs(np.minimum(deltas[:period], 0)))
        rsi = np.zeros_like(prices)
        if down == 0:
            rsi[:period+1] = 100.0
        else:
            rs = up / down
            rsi[:period+1] = 100.0 - 100.0 / (1.0 + rs)
        for i in range(period, len(deltas)):
            delta = deltas[i]
            up = (up * (period-1) + max(delta, 0)) / period
            down = (down * (period-1) + abs(min(delta, 0))) / period
            if down == 0:
                rsi[i+1] = 100.0
            else:
                rs = up / down
                rsi[i+1] = 100.0 - 100.0 / (1.0 + rs)
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
        if last_rsi < 30:
            signals.append(("BUY", "RSI oversold"))
        elif last_rsi > 70:
            signals.append(("SELL", "RSI overbought"))
        if prev_macd < prev_signal and last_macd > last_signal:
            signals.append(("BUY", "MACD bullish crossover"))
        elif prev_macd > prev_signal and last_macd < last_signal:
            signals.append(("SELL", "MACD bearish crossover"))
        return signals

# ------------------------------------------------------------------
# IMPROVED FORECAST (weighted linear)
# ------------------------------------------------------------------
def weighted_linear_fit(x, y, tau=7):
    n = len(x)
    weights = np.exp(-np.arange(n)[::-1] / tau)
    W = np.diag(weights)
    X = np.column_stack([np.ones_like(x), x])
    XtW = X.T @ W
    coeffs = np.linalg.solve(XtW @ X, XtW @ (W @ y))
    return coeffs

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
        coeffs = weighted_linear_fit(x, y, tau=7)
        last_idx = len(series) - 1
        future_x = np.array([last_idx + d for d in range(1, horizon_days+1)])
        return np.round(coeffs[0] + coeffs[1] * future_x, 4)

class CryptoForecast:
    BASE_PRICES = {"bitcoin": 67000, "ethereum": 3400, "ripple": 0.6, "cardano": 0.45, "solana": 170}
    DAILY_VOL = {"bitcoin": 1500, "ethereum": 120, "ripple": 0.03, "cardano": 0.02, "solana": 8}

    @staticmethod
    def generate_daily_history(days=90, live_prices=None):
        np.random.seed(456)
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        df = pd.DataFrame(index=dates)
        for coin in CRYPTO_COINS:
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
        coeffs = weighted_linear_fit(x, y, tau=7)
        last_idx = len(series) - 1
        future_x = np.array([last_idx + d for d in range(1, horizon_days+1)])
        return np.round(coeffs[0] + coeffs[1] * future_x, 2)

# ------------------------------------------------------------------
# CRYPTO ENGINE (unchanged)
# ------------------------------------------------------------------
class CryptoEngine:
    @staticmethod
    def fetch_prices():
        try:
            ids = ",".join(CRYPTO_COINS)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            prices = []
            for coin in CRYPTO_COINS:
                info = data.get(coin, {})
                prices.append({
                    "Coin": CRYPTO_NAMES[coin],
                    "Price (USD)": info.get("usd"),
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
            resp.raise_for_status()
            data = resp.json()
            prices = data["prices"]
            df = pd.DataFrame(prices, columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df.set_index("timestamp")
        except:
            return None

# ------------------------------------------------------------------
# JUP AI – TRADING NEWS AGENT (replaces Structural Pro)
# ------------------------------------------------------------------
def jup_ai_tab():
    st.subheader("🤖 Jup AI · Trading Intelligence")
    st.caption("Parametric news agent – BUY, HOLD, SELL with trade time frames.")
    # Simulated news headlines
    st.markdown("**📰 Market News (simulated)**")
    news = [
        "Fed signals possible rate cut in next meeting.",
        "Oil prices surge on supply disruption fears.",
        "BTC whales accumulate ahead of halving event.",
        "UGX weakens on political uncertainty.",
        "Ethereum DeFi TVL hits new all-time high."
    ]
    for item in news:
        st.info(item)

    # Choose market
    market = st.radio("Market", ["Forex", "Crypto"], horizontal=True)
    if market == "Forex":
        pair = st.selectbox("Select currency pair", ForexEngine.PAIRS)
        df = st.session_state.forex_data
        signals = TradingSignals.generate_signals(df, pair)
        # Trade decision logic
        buy_signals = sum(1 for s in signals if s[0]=="BUY")
        sell_signals = sum(1 for s in signals if s[0]=="SELL")
        if buy_signals > sell_signals:
            decision = "BUY"
        elif sell_signals > buy_signals:
            decision = "SELL"
        else:
            decision = "HOLD"
        st.markdown(f"### Decision: **{decision}**")
        st.caption("Based on RSI & MACD crossovers.")
        # Trade time suggestion
        time_frame = "Scalp (mins)" if abs(df[pair].pct_change().iloc[-1])>0.002 else "Swing (days)"
        st.metric("Suggested Trade Time", time_frame)
        # Forecast chart
        st.subheader("📈 Forecast (Daily, Weekly, Monthly)")
        horizon = st.selectbox("Forecast horizon", ["1 Day", "7 Days (Week)", "30 Days (Month)"])
        days = {"1 Day":1, "7 Days (Week)":7, "30 Days (Month)":30}[horizon]
        daily_hist = st.session_state.forex_daily_hist
        fcast = ForexForecast.forecast(daily_hist, days, pair)
        hist_part = daily_hist[pair].tail(30)
        idx_hist = list(hist_part.index)
        idx_fut = pd.date_range(idx_hist[-1] + pd.Timedelta(days=1), periods=days, freq='D')
        combined = np.concatenate([hist_part.values, fcast])
        chart = pd.Series(combined, index=list(idx_hist)+list(idx_fut))
        st.line_chart(chart)
    else:
        coin = st.selectbox("Select coin", CRYPTO_COINS, format_func=lambda x: CRYPTO_NAMES[x])
        # Simple sentiment from 24h change
        live = st.session_state.crypto_live_prices
        if live is not None:
            row = live[live['Coin']==CRYPTO_NAMES[coin]]
            if not row.empty:
                change = row.iloc[0]['24h Change %']
                if change > 3:
                    decision = "SELL"
                elif change < -3:
                    decision = "BUY"
                else:
                    decision = "HOLD"
                st.markdown(f"### Decision: **{decision}**")
                st.caption("Based on 24h momentum.")
                time_frame = "Scalp (minutes)" if abs(change)>5 else "Swing (days)"
                st.metric("Suggested Trade Time", time_frame)
        daily_hist = st.session_state.crypto_daily_hist
        horizon = st.selectbox("Forecast horizon", ["1 Day", "7 Days (Week)", "30 Days (Month)"])
        days = {"1 Day":1, "7 Days (Week)":7, "30 Days (Month)":30}[horizon]
        fcast = CryptoForecast.forecast(daily_hist, days, coin)
        hist_part = daily_hist[coin].tail(30)
        idx_hist = list(hist_part.index)
        idx_fut = pd.date_range(idx_hist[-1] + pd.Timedelta(days=1), periods=days, freq='D')
        combined = np.concatenate([hist_part.values, fcast])
        chart = pd.Series(combined, index=list(idx_hist)+list(idx_fut))
        st.line_chart(chart)

# ------------------------------------------------------------------
# UI & SESSION STATE
# ------------------------------------------------------------------
st.set_page_config(page_title=" ", page_icon="🔄", layout="wide")

def load_css():
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #0a0a1a, #1a1a3a, #2a2a4a); color: #e0e0e0; }
        section[data-testid="stSidebar"] { background: rgba(20,20,40,0.85); backdrop-filter: blur(12px); border-right: 1px solid rgba(255,255,255,0.1); }
        h1,h2,h3 { font-family: 'Segoe UI', sans-serif; font-weight: 600; background: linear-gradient(90deg, #00d2ff, #3a7bd5); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .glass-card { background: rgba(255,255,255,0.03); backdrop-filter: blur(16px); border-radius:18px; border:1px solid rgba(255,255,255,0.08); padding:24px; margin:12px 0; box-shadow:0 12px 40px rgba(0,0,0,0.5); }
        .metric-box { background: rgba(255,255,255,0.06); border-radius:14px; padding:18px; margin:6px 0; text-align:center; font-weight:bold; border:1px solid rgba(255,255,255,0.12); transition: all 0.2s ease; }
        .metric-box:hover { background: rgba(255,255,255,0.1); }
        div.stButton > button { background: linear-gradient(45deg, #ff416c, #ff4b2b); border:none; color:white; padding:12px 28px; font-size:16px; font-weight:bold; border-radius:50px; box-shadow:0 0 20px rgba(255,75,43,0.5); transition:all 0.3s ease; cursor:pointer; letter-spacing:0.5px; text-transform:uppercase; width:100%; border:1px solid rgba(255,255,255,0.2); }
        div.stButton > button:hover { transform:translateY(-2px); box-shadow:0 0 30px rgba(255,75,43,0.8); background:linear-gradient(45deg, #ff4b2b, #ff416c); color:white; }
        .stForm button { background: linear-gradient(45deg, #00b4db, #0083b0) !important; }
        .logo-container { display: flex; justify-content: center; margin: 10px 0 20px 0; }
    </style>""", unsafe_allow_html=True)

load_css()

def show_logo():
    st.markdown("""
    <div class="logo-container">
        <svg width="90" height="90" viewBox="0 0 100 100">
            <defs>
                <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#00d2ff;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#3a7bd5;stop-opacity:1" />
                </linearGradient>
            </defs>
            <path d="M15,80 A60,60 0 0,1 85,80" stroke="url(#arcGrad)" stroke-width="5" fill="none" stroke-linecap="round"/>
            <circle cx="50" cy="68" r="6" fill="#ff4b2b" filter="drop-shadow(0 0 6px #ff4b2b)"/>
        </svg>
    </div>
    """, unsafe_allow_html=True)

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
if 'forex_daily_hist' not in st.session_state:
    st.session_state.forex_daily_hist = ForexForecast.generate_daily_history(90)
if 'crypto_live_prices' not in st.session_state:
    st.session_state.crypto_live_prices = CryptoEngine.fetch_prices()
if 'crypto_daily_hist' not in st.session_state:
    live_dict = {}
    if st.session_state.crypto_live_prices is not None:
        for _, row in st.session_state.crypto_live_prices.iterrows():
            for cid, name in CRYPTO_NAMES.items():
                if name == row["Coin"]:
                    live_dict[cid] = row["Price (USD)"]
    st.session_state.crypto_daily_hist = CryptoForecast.generate_daily_history(90, live_dict)

# ------------------------------------------------------------------
# SIDEBAR & MODE SELECTION
# ------------------------------------------------------------------
with st.sidebar:
    show_logo()
    st.write(f"👤 {st.session_state.username} ({st.session_state.role})")
    mode_options = ["💱 Forex Pro", "🤖 Jup AI", "₿ Crypto Tracker", "💳 Mobile Wallet"]
    if 'mode' not in st.session_state:
        st.session_state.mode = mode_options[0]
    mode = st.radio("🧠 Engine", mode_options, index=mode_options.index(st.session_state.mode))
    st.session_state.mode = mode
    if mode == "💱 Forex Pro":
        st.checkbox("Real‑time forex", value=st.session_state.use_real_forex, key="use_real_forex")
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
                        st.success(msg) if success else st.error(msg)
                    else:
                        st.error("All fields required.")
    with st.expander("🚀 Deploy"):
        st.markdown("Push to GitHub, set secrets, deploy on Streamlit Cloud.")
    if st.button("🚪 Logout"):
        logout()
    st.caption("v10 · Jup AI Trading Agent")

# -------------------- Modules --------------------
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
    st.line_chart(forex_df.set_index("Time"))
    pair_hist = st.selectbox("DB History", ForexEngine.PAIRS)
    hist_df = ForexEngine.get_history(pair_hist, 30)
    if not hist_df.empty:
        st.line_chart(hist_df.set_index("timestamp"))
    else:
        st.info("No history yet.")
    st.bar_chart(st.session_state.forex_volume.set_index("Time"))
    st.table(ForexEngine.get_correlation_matrix(forex_df))
    if st.button("🔄 Refresh Live Data"):
        st.session_state.forex_data = ForexEngine.get_live_data(use_real=st.session_state.use_real_forex)
        st.session_state.forex_volume = ForexEngine.get_volume()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif mode == "₿ Crypto Tracker":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("₿ Live Crypto Prices")
    live_df = st.session_state.crypto_live_prices
    if live_df is not None:
        cols = st.columns(len(live_df))
        for i, row in live_df.iterrows():
            with cols[i]:
                change_color = "green" if row["24h Change %"] >= 0 else "red"
                st.markdown(f"""<div class="metric-box">
                    <span style="font-size:18px;">{row['Coin']}</span><br>
                    <span style="font-size:22px;">${row['Price (USD)']:,.2f}</span><br>
                    <span style="color:{change_color};">{row['24h Change %']}%</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("Could not fetch prices.")
    if st.button("🔄 Refresh Crypto"):
        st.session_state.crypto_live_prices = CryptoEngine.fetch_prices()
        st.rerun()
    coin_hist = st.selectbox("Select coin", CRYPTO_COINS, format_func=lambda x: CRYPTO_NAMES[x])
    hist = CryptoEngine.get_historical(coin_hist, 7)
    if hist is not None:
        st.line_chart(hist)
    st.markdown('</div>', unsafe_allow_html=True)

elif mode == "🤖 Jup AI":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    jup_ai_tab()
    st.markdown('</div>', unsafe_allow_html=True)

elif mode == "💳 Mobile Wallet":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("💳 Mobile Wallet")
    balance = MobileWallet.get_balance(st.session_state.username)
    st.metric("Current Balance", f"{balance:,.2f} (simulated)")

    tab1, tab2 = st.tabs(["💰 Deposit", "💸 Withdraw"])
    with tab1:
        with st.form("deposit_form"):
            phone = st.text_input("Phone number")
            amount = st.number_input("Amount", min_value=1.0, step=10.0)
            provider = st.selectbox("Provider", MobileWallet.PROVIDERS)
            submitted = st.form_submit_button("Request Deposit")
            if submitted:
                ref = MobileWallet.deposit_request(st.session_state.username, phone, amount, provider)
                st.session_state.deposit_ref = ref
                st.success(f"Deposit requested. Reference: {ref}")
        # Confirm deposit outside form
        if 'deposit_ref' in st.session_state:
            confirm_ref = st.text_input("Enter reference to confirm", key="confirm_dep_ref")
            if st.button("✅ Confirm Deposit"):
                if confirm_ref == st.session_state.deposit_ref:
                    MobileWallet.confirm_deposit(confirm_ref)
                    st.success("Deposit confirmed!")
                    del st.session_state.deposit_ref
                    st.rerun()
                else:
                    st.error("Invalid reference")
    with tab2:
        with st.form("withdraw_form"):
            phone = st.text_input("Phone number", key="w_phone")
            amount = st.number_input("Amount", min_value=1.0, step=10.0, key="w_amount")
            provider = st.selectbox("Provider", MobileWallet.PROVIDERS, key="w_provider")
            submitted = st.form_submit_button("Request Withdrawal")
            if submitted:
                ref, msg = MobileWallet.withdraw_request(st.session_state.username, phone, amount, provider)
                if ref is None:
                    st.error(msg)
                else:
                    st.session_state.withdraw_ref = ref
                    st.success(f"Withdrawal requested. Reference: {ref}")
        if 'withdraw_ref' in st.session_state:
            confirm_ref = st.text_input("Enter reference to confirm", key="confirm_wth_ref")
            if st.button("✅ Confirm Withdrawal"):
                if confirm_ref == st.session_state.withdraw_ref:
                    MobileWallet.confirm_withdrawal(confirm_ref)
                    st.success("Withdrawal successful!")
                    del st.session_state.withdraw_ref
                    st.rerun()
                else:
                    st.error("Invalid reference")

    st.subheader("Transaction History")
    txn_df = MobileWallet.get_transactions(st.session_state.username)
    if not txn_df.empty:
        st.dataframe(txn_df)
    else:
        st.info("No transactions yet.")
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    pass
