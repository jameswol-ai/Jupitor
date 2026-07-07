def init_db():
    conn = sqlite3.connect("arc_os.db")
    c = conn.cursor()

    # Create users table if not exists, then ensure email column exists
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password_hash TEXT, role TEXT DEFAULT 'user')''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Seed admin if not exists (or update email if admin exists but email is NULL)
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        admin_hash = hashlib.sha256("arc2024".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, 'admin')",
                  ("admin", admin_hash, "admin@arcos.pro"))
    else:
        # Ensure admin has an email if column was added later
        c.execute("UPDATE users SET email='admin@arcos.pro' WHERE username='admin' AND email IS NULL")

    # Rest of table creation...
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