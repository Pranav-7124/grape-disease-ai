"""
auth.py – Simple file-based auth (no database required)
Passwords: bcrypt hashed (never stored in plain text)
"""
import os
import json
import uuid
import bcrypt
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import UserMixin, login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__)

# ============================================================
# Simple JSON file storage for users
# ============================================================
USERS_FILE = os.environ.get("USERS_FILE", "users.json")

def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

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
    users = _load_users()
    for uid, u in users.items():
        if str(u.get("id")) == str(user_id):
            return User(u["id"], u["username"], u["anon_id"])
    return None

# ============================================================
# Routes
# ============================================================

@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    users = _load_users()

    if username in users:
        return jsonify({"error": "Username already taken"}), 409

    # Bcrypt hash
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    anon_id = str(uuid.uuid4())
    user_id = max([u.get("id", 0) for u in users.values()] or [0]) + 1

    users[username] = {
        "id": user_id,
        "anon_id": anon_id,
        "username": username,
        "password_hash": hashed.decode("utf-8")
    }
    _save_users(users)

    user = User(user_id, username, anon_id)
    login_user(user, remember=True)
    return jsonify({"success": True, "username": username})

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    users = _load_users()
    row = users.get(username)

    if not row:
        return jsonify({"error": "Invalid username or password"}), 401

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
