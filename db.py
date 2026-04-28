"""
db.py – Database connection and initialization helper
Supports MySQL (via PyMySQL) with automatic SQLite fallback.
All logs use anon_id (UUID) — never raw usernames.
"""
import os

# ============================================================
# BACKEND SELECTION
# ============================================================
DB_HOST = os.environ.get("DB_HOST")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
USE_MYSQL = bool(DB_HOST and DB_PASSWORD)

if USE_MYSQL:
    import pymysql
    import pymysql.cursors

    DB_CONFIG = {
        "host":     DB_HOST,
        "port":     int(os.environ.get("DB_PORT", "3306")),
        "user":     os.environ.get("DB_USER", "root"),
        "password": DB_PASSWORD,
        "db":       os.environ.get("DB_NAME", "app"),
        "charset":  "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True
    }

    def get_connection():
        return pymysql.connect(**DB_CONFIG)

else:
    import sqlite3

    DB_PATH = os.environ.get("DB_PATH", "app.db")

    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


# ============================================================
# QUERY HELPER (adapts placeholder style)
# ============================================================
def _execute(sql, params=None, fetch=None):
    """Execute SQL with backend-agnostic parameter binding."""
    if not USE_MYSQL:
        sql = sql.replace("%s", "?")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        if fetch == "one":
            row = cur.fetchone()
            return dict(row) if row else None
        elif fetch == "all":
            return [dict(row) for row in cur.fetchall()]
        else:
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


# ============================================================
# INIT
# ============================================================
def init_db():
    """Creates all tables if they don't exist. Safe to call on every startup."""
    if USE_MYSQL:
        cfg = {k: v for k, v in DB_CONFIG.items() if k != "db"}
        conn = pymysql.connect(**cfg)
        try:
            with conn.cursor() as cur:
                with open("schema.sql", "r", encoding="utf-8") as f:
                    raw = f.read()
                for stmt in [s.strip() for s in raw.split(";") if s.strip()]:
                    try:
                        cur.execute(stmt)
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            print(f"[DB INIT] Warning: {e}")
            conn.commit()
            print("[DB] MySQL tables initialized successfully.")
        finally:
            conn.close()
    else:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT UNIQUE NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS prediction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT NOT NULL,
                    location TEXT,
                    temperature REAL,
                    humidity REAL,
                    rainfall REAL,
                    growth_stage TEXT,
                    predicted_disease TEXT,
                    predicted_risk TEXT,
                    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scan_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anon_id TEXT NOT NULL,
                    disease_detected TEXT,
                    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS model_train_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    samples_used INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0.0,
                    trigger_type TEXT DEFAULT 'scheduled'
                );
            """)
            conn.commit()
            print("[DB] SQLite tables initialized successfully.")
        finally:
            conn.close()


# ============================================================
# CRUD OPERATIONS
# ============================================================
def log_prediction(anon_id, location, temperature, humidity, rainfall,
                   growth_stage, disease, risk):
    _execute("""
        INSERT INTO prediction_logs
          (anon_id, location, temperature, humidity, rainfall,
           growth_stage, predicted_disease, predicted_risk)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (anon_id, location, temperature, humidity, rainfall,
          growth_stage, disease, risk))

def log_scan(anon_id, disease_detected):
    _execute("""
        INSERT INTO scan_logs (anon_id, disease_detected)
        VALUES (%s, %s)
    """, (anon_id, disease_detected[:200]))

def log_training(samples_used, accuracy, trigger_type="scheduled"):
    _execute("""
        INSERT INTO model_train_log (samples_used, accuracy, trigger_type)
        VALUES (%s, %s, %s)
    """, (samples_used, round(accuracy, 4), trigger_type))

def get_last_training():
    return _execute("""
        SELECT trained_at, samples_used, accuracy
        FROM model_train_log
        ORDER BY trained_at DESC LIMIT 1
    """, fetch="one")

def get_all_prediction_logs():
    return _execute("""
        SELECT temperature, humidity, rainfall, growth_stage,
               predicted_disease, predicted_risk
        FROM prediction_logs
    """, fetch="all")


# ============================================================
# AUTH HELPERS (backend-agnostic)
# ============================================================
def create_user(anon_id, username, password_hash):
    """Insert a new user and return the new row id."""
    return _execute("""
        INSERT INTO users (anon_id, username, password_hash)
        VALUES (%s, %s, %s)
    """, (anon_id, username, password_hash))

def get_user_by_id(user_id):
    return _execute("""
        SELECT id, username, anon_id, password_hash
        FROM users WHERE id = %s
    """, (user_id,), fetch="one")

def get_user_by_username(username):
    return _execute("""
        SELECT id, username, anon_id, password_hash
        FROM users WHERE username = %s
    """, (username,), fetch="one")
