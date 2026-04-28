from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import pickle
import numpy as np
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler

# ============================================================
# APP SETUP
# ============================================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret")

# ============================================================
# ENV VARIABLES (SECURE)
# ============================================================
API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ============================================================
# Flask-Login Setup
# ============================================================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login_page"
login_manager.login_message = ""

from auth import auth_bp, load_user_by_id
app.register_blueprint(auth_bp)

@login_manager.user_loader
def load_user(user_id):
    return load_user_by_id(user_id)

# ============================================================
# Database Init
# ============================================================
try:
    from db import init_db, log_prediction, log_scan, get_last_training
    init_db()
    DB_ENABLED = True
except Exception as e:
    DB_ENABLED = False
    print(f"[DB] Not available: {e}")

# ============================================================
# Load ML Models
# ============================================================
def load_models():
    return (
        pickle.load(open("disease_model.pkl", "rb")),
        pickle.load(open("risk_model.pkl", "rb")),
        pickle.load(open("stage_encoder.pkl", "rb")),
        pickle.load(open("disease_encoder.pkl", "rb")),
        pickle.load(open("risk_encoder.pkl", "rb")),
    )

disease_model, risk_model, stage_encoder, disease_encoder, risk_encoder = load_models()

# ============================================================
# Scheduler (Auto Retrain)
# ============================================================
def scheduled_retrain():
    if not DB_ENABLED:
        return
    try:
        from trainer import run_training
        acc, n = run_training("scheduled")
        global disease_model, risk_model, stage_encoder, disease_encoder, risk_encoder
        disease_model, risk_model, stage_encoder, disease_encoder, risk_encoder = load_models()
        print(f"[RETRAIN] Accuracy: {acc}")
    except Exception as e:
        print(f"[RETRAIN ERROR] {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_retrain, "cron", hour=2)
scheduler.start()

# ============================================================
# WEATHER FUNCTION
# ============================================================
def get_weather(location=None, lat=None, lon=None):
    if lat and lon:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    else:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"

    res = requests.get(url).json()

    if "main" not in res:
        raise Exception(res.get("message", "Weather error"))

    return (
        res["main"]["temp"],
        res["main"]["humidity"],
        res.get("rain", {}).get("1h", 0),
        res.get("name", location)
    )

# ============================================================
# CHATBOT
# ============================================================
def ask_llm(msg):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": msg}]
    }

    res = requests.post(url, headers=headers, json=payload).json()
    return res["choices"][0]["message"]["content"]

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def home():
    return redirect(url_for("auth.login_page"))

@app.route("/app")
@login_required
def app_ui():
    return render_template("index.html", username=current_user.username)

# ============================================================
# PREDICT
# ============================================================
@app.route("/predict", methods=["POST"])
@login_required
def predict():
    try:
        data = request.get_json()

        temp, hum, rain, city = get_weather(
            data.get("location"),
            data.get("lat"),
            data.get("lon")
        )

        stage = stage_encoder.transform([data["growth_stage"]])[0]
        features = np.array([[temp, hum, rain, stage]])

        disease = disease_encoder.inverse_transform(
            disease_model.predict(features)
        )[0]

        risk = risk_encoder.inverse_transform(
            risk_model.predict(features)
        )[0]

        return jsonify({
            "location": city,
            "temperature": temp,
            "humidity": hum,
            "rainfall": rain,
            "disease": disease,
            "risk": risk
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ============================================================
# FORECAST
# ============================================================
@app.route("/forecast")
@login_required
def forecast():
    location = request.args.get("location")

    url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={API_KEY}&units=metric"
    data = requests.get(url).json()

    return jsonify(data)

# ============================================================
# CHAT
# ============================================================
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    msg = request.json.get("message")
    return jsonify({"reply": ask_llm(msg)})

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)