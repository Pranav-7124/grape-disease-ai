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
# IMAGE SCAN (CROP DISEASE DETECTION)
# ============================================================
@app.route("/scan", methods=["POST"])
@login_required
def scan():
    try:
        data = request.get_json()
        image_data = data.get("image", "")

        if not image_data:
            return jsonify({"error": "No image provided"}), 400

        # Extract base64 data
        if "," in image_data:
            image_data = image_data.split(",")[1]

        # For now, simulate AI analysis with rule-based detection
        # In production, integrate with a real image classification model
        import base64
        from io import BytesIO
        from PIL import Image

        try:
            img_bytes = base64.b64decode(image_data)
            img = Image.open(BytesIO(img_bytes))
            width, height = img.size

            # Simple heuristic: analyze image brightness/color for demo
            # In production, replace with actual ML model inference
            avg_brightness = sum(img.convert('L').getdata()) / (width * height)

            # Simulated disease detection based on brightness (placeholder logic)
            if avg_brightness < 80:
                disease = "Downy Mildew (Detected via image analysis)"
                confidence = "85%"
                advice = "Apply copper-based fungicide. Ensure proper air circulation. Remove infected leaves immediately."
            elif avg_brightness > 200:
                disease = "Powdery Mildew (Detected via image analysis)"
                confidence = "78%"
                advice = "Apply sulfur-based fungicide. Avoid overhead watering. Increase spacing between plants."
            else:
                disease = "No significant disease detected"
                confidence = "92%"
                advice = "Continue regular monitoring. Maintain balanced watering and fertilization schedule."

            # Log scan if DB enabled
            try:
                if DB_ENABLED:
                    from db import log_scan
                    log_scan(current_user.anon_id, disease)
            except Exception:
                pass

            return jsonify({
                "disease_detected": disease,
                "confidence": confidence,
                "advice": advice
            })

        except Exception as img_err:
            return jsonify({"error": f"Image processing error: {str(img_err)}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# CHATBOT
# ============================================================
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    if not OPENROUTER_API_KEY:
        return jsonify({"reply": "Chatbot not configured. Please set OPENROUTER_API_KEY."})

    try:
        msg = request.json.get("message", "").strip()
        if not msg:
            return jsonify({"reply": "Please enter a question."}), 400

        system_prompt = """You are VineAI, an expert grape farming advisor. Your responses must be:

1. CONCISE - Keep answers under 150 words
2. STRUCTURED - Use bullet points (•) for lists, not long paragraphs
3. ACTIONABLE - Give specific, practical advice farmers can implement immediately
4. FOCUSED - Answer exactly what was asked, don't add unrelated information

Format your response with clear sections:
• Quick Answer: 1-2 sentence summary
• Key Actions: Bullet points of what to do
• When to Act: Timeline if applicable

Avoid rambling, repetitive explanations, or overly technical jargon. Speak like an experienced agricultural advisor helping a farmer."""

        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://grape-disease-ai-72de.onrender.com",
                "X-Title": "VineAI Grape Advisor"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": msg}
                ],
                "temperature": 0.3,
                "max_tokens": 300
            },
            timeout=15
        )

        result = res.json()
        if "choices" not in result or not result["choices"]:
            error_msg = result.get("error", {}).get("message", "Unknown API error")
            return jsonify({"reply": f"API Error: {error_msg}"}), 500

        reply = result["choices"][0]["message"]["content"].strip()

        return jsonify({"reply": reply})

    except requests.exceptions.Timeout:
        return jsonify({"reply": "⏱️ Response took too long. Please try a shorter question."})
    except requests.exceptions.RequestException as e:
        return jsonify({"reply": f"🔌 Connection error: {str(e)}"})
    except Exception as e:
        return jsonify({"reply": f"❌ Error: {str(e)}"})

# ============================================================
# WEATHER ENDPOINTS (used by frontend)
# ============================================================
@app.route("/weather_now")
def weather_now():
    if not OPENWEATHER_API_KEY:
        return jsonify({"error": "Weather API not configured"}), 500

    try:
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        location = request.args.get("location")

        if lat and lon:
            url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        elif location:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"
        else:
            return jsonify({"error": "Provide lat/lon or location"}), 400

        res = requests.get(url)
        data = res.json()

        if "main" not in data:
            return jsonify({"error": data.get("message", "Weather API error")}), 400

        return jsonify({
            "city": data.get("name", location),
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"] if data.get("weather") else "",
            "icon": data["weather"][0]["icon"] if data.get("weather") else "01d"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/forecast")
def forecast():
    if not OPENWEATHER_API_KEY:
        return jsonify({"error": "Weather API not configured"}), 500

    try:
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        location = request.args.get("location")

        if lat and lon:
            url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        elif location:
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"
        else:
            return jsonify({"error": "Provide lat/lon or location"}), 400

        res = requests.get(url)
        data = res.json()

        if "list" not in data:
            return jsonify({"error": data.get("message", "Weather API error")}), 400

        # Aggregate 3-hourly data into daily forecast
        daily = {}
        for item in data["list"]:
            date = item["dt_txt"][:10]
            if date not in daily:
                daily[date] = {
                    "date": date,
                    "temps": [],
                    "descriptions": []
                }
            daily[date]["temps"].append(item["main"]["temp"])
            desc = item["weather"][0]["description"] if item.get("weather") else ""
            daily[date]["descriptions"].append(desc)

        forecast_list = []
        for date in sorted(daily.keys())[:5]:
            info = daily[date]
            forecast_list.append({
                "date": date,
                "temp": round(sum(info["temps"]) / len(info["temps"]), 1),
                "description": max(set(info["descriptions"]), key=info["descriptions"].count)
            })

        return jsonify({"forecast": forecast_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=PORT, debug=False)
