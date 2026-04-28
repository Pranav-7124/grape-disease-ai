"""
auth.py – Flask Blueprint for login/signup/logout
Passwords: bcrypt hashed (never stored in plain text)
Users tracked by anon_id (UUID) — username never appears in logs
"""
import uuid
import bcrypt
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pymysql

try:
    from db import get_connection
    DB_ENABLED = True
except Exception:
    DB_ENABLED = False
    get_connection = None

auth_bp = Blueprint("auth", __name__)

# ============================================================
# User Model (Flask-Login)
# ============================================================
class User(UserMixin):
    def __init__(self, id, username, anon_id):
        self.id       = id
        self.username = username
        self.anon_id  = anon_id

    def get_id(self):
        return str(self.id)

def load_user_by_id(user_id):
    """Load user from DB by integer PK — used by Flask-Login."""
    if not DB_ENABLED or get_connection is None:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, anon_id FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                return User(row["id"], row["username"], row["anon_id"])
    finally:
        conn.close()
    return None

# ============================================================
# Routes
# ============================================================

@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@auth_bp.route("/register", methods=["POST"])
def register():
    if not DB_ENABLED or get_connection is None:
        return jsonify({"error": "Database unavailable"}), 503

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Bcrypt hash — work factor 12
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    anon_id = str(uuid.uuid4())  # Anonymization UUID

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (anon_id, username, password_hash) VALUES (%s, %s, %s)",
                (anon_id, username, hashed.decode("utf-8"))
            )
        conn.commit()

        # Immediately log the user in
        user = User(cur.lastrowid, username, anon_id)
        # Re-fetch to get actual ID
        with conn.cursor() as cur2:
            cur2.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur2.fetchone()
            user.id = row["id"]

        login_user(user, remember=True)
        return jsonify({"success": True, "username": username})

    except pymysql.err.IntegrityError:
        return jsonify({"error": "Username already taken"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@auth_bp.route("/login", methods=["POST"])
def login():
    if not DB_ENABLED or get_connection is None:
        return jsonify({"error": "Database unavailable"}), 503

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, anon_id, password_hash FROM users WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Invalid username or password"}), 401

    # Verify bcrypt hash
    if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
        return jsonify({"error": "Invalid username or password"}), 401

    user = User(row["id"], row["username"], row["anon_id"])
    login_user(user, remember=True)
    return jsonify({"success": True, "username": username})

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_page"))
