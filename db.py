"""
db.py – Database connection and initialization helper
All logs use anon_id (UUID) — never raw usernames
"""
import os
import pymysql
import pymysql.cursors

# ============================================================
# CONFIG — read from environment variables with safe defaults
# ============================================================
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", "3306")),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "db":       os.environ.get("DB_NAME", "app"),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True
}

def get_connection():
    """Returns a live PyMySQL connection."""
    return pymysql.connect(**DB_CONFIG)

def init_db():
    """
    Creates the app database and all tables if they don't exist.
    Safe to call on every startup.
    """
    # Connect without specifying DB first so we can CREATE DATABASE
    cfg = {k: v for k, v in DB_CONFIG.items() if k != "db"}
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            with open("schema.sql", "r", encoding="utf-8") as f:
                sql = f.read()
            # Split on semicolons and run each statement
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # Ignore "table already exists" errors
                    if "already exists" not in str(e).lower():
                        print(f"[DB INIT] Warning: {e}")
        conn.commit()
        print("[DB] Tables initialized successfully.")
    finally:
        conn.close()

def log_prediction(anon_id, location, temperature, humidity, rainfall,
                   growth_stage, disease, risk):
    """Save a prediction result to prediction_logs."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prediction_logs
                  (anon_id, location, temperature, humidity, rainfall,
                   growth_stage, predicted_disease, predicted_risk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (anon_id, location, temperature, humidity, rainfall,
                  growth_stage, disease, risk))
    finally:
        conn.close()

def log_scan(anon_id, disease_detected):
    """Save a camera scan result to scan_logs."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scan_logs (anon_id, disease_detected)
                VALUES (%s, %s)
            """, (anon_id, disease_detected[:200]))
    finally:
        conn.close()

def log_training(samples_used, accuracy, trigger_type="scheduled"):
    """Record a model retraining event."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO model_train_log (samples_used, accuracy, trigger_type)
                VALUES (%s, %s, %s)
            """, (samples_used, round(accuracy, 4), trigger_type))
    finally:
        conn.close()

def get_last_training():
    """Returns the most recent model_train_log row."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT trained_at, samples_used, accuracy
                FROM model_train_log
                ORDER BY trained_at DESC LIMIT 1
            """)
            return cur.fetchone()
    finally:
        conn.close()

def get_all_prediction_logs():
    """Returns all prediction_logs — used for self-training."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT temperature, humidity, rainfall, growth_stage,
                       predicted_disease, predicted_risk
                FROM prediction_logs
            """)
            return cur.fetchall()
    finally:
        conn.close()
