from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
import pickle
import numpy as np
import requests
import os

from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ============================================================
# LOGIN SETUP
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
# DATABASE (OPTIONAL)
# ============================================================
try:
    from db import init_db, log_prediction, log_scan
    init_db()
    DB_ENABLED = True
except:
    DB_ENABLED = False

# ============================================================
# ENV VARIABLES
# ============================================================
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENWEATHER_API_KEY:
    raise Exception("❌ Missing OPENWEATHER_API_KEY")

if not OPENROUTER_API_KEY:
    print("⚠️ WARNING: OPENROUTER_API_KEY not set - chatbot disabled")

# ============================================================
# LOAD MODELS (SAFE)
# ============================================================
def load_models():
    try:
        return (
            pickle.load(open("disease_model.pkl", "rb")),
            pickle.load(open("risk_model.pkl", "rb")),
            pickle.load(open("stage_encoder.pkl", "rb")),
            pickle.load(open("disease_encoder.pkl","rb")),
            pickle.load(open("risk_encoder.pkl", "rb")),
        )
    except Exception as e:
        print("[ERROR] Model loading failed:", e)
        return None, None, None, None, None

disease_model, risk_model, stage_encoder, disease_encoder, risk_encoder = load_models()

# ============================================================
# WEATHER
# ============================================================
def get_weather(location=None, lat=None, lon=None):
    if lat and lon:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    else:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"

    res = requests.get(url)
    data = res.json()

    if "main" not in data:
        raise Exception(data.get("message", "Weather API error"))

    return (
        data["main"]["temp"],
        data["main"]["humidity"],
        data.get("rain", {}).get("1h", 0),
        data.get("name", location)
    )

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("app_ui"))
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
    if not disease_model:
        return jsonify({"error": "Model not loaded"})

    try:
        data = request.get_json()

        temp, hum, rain, city = get_weather(
            location=data.get("location"),
            lat=data.get("lat"),
            lon=data.get("lon")
        )

        stage = stage_encoder.transform([data["growth_stage"]])[0]

        features = np.array([[temp, hum, rain, stage]])

        disease = disease_encoder.inverse_transform(disease_model.predict(features))[0]
        risk = risk_encoder.inverse_transform(risk_model.predict(features))[0]

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
# CHATBOT
# ============================================================
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    if not OPENROUTER_API_KEY:
        return jsonify({"reply": "Chatbot not configured."})

    try:
        msg = request.json.get("message")

        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": msg}]
            }
        )

        return jsonify({
            "reply": res.json()["choices"][0]["message"]["content"]
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ============================================================
# SIMPLE HEALTH CHECK
# ============================================================
@app.route("/health")
def health():
    return "OK"

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)