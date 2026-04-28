// ============================================================
//  STATE
// ============================================================
let lastDisease = "";
let lastRisk = "";
let currentLat = null;
let currentLon = null;
let capturedImageBase64 = null;
let capturedMimeType = "image/jpeg";
let cameraStream = null;
let lastWeatherSnapshot = null;
let pollingInterval = null;

// ============================================================
//  ON PAGE LOAD
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
    requestNotificationPermission();
    detectLocation();
});

// ============================================================
//  NOTIFICATIONS
// ============================================================
function requestNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
}

function showNotification(title, body) {
    // In-app banner
    document.getElementById("notifText").textContent = `⚠️ ${title}: ${body}`;
    document.getElementById("notifBanner").classList.remove("hidden");

    // Browser notification
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, {
            body: body,
            icon: "/static/grape-icon.png"
        });
    }
}

function dismissNotif() {
    document.getElementById("notifBanner").classList.add("hidden");
}

// ============================================================
//  WEATHER POLLING (every 15 minutes)
// ============================================================
function startWeatherPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(checkWeatherChange, 15 * 60 * 1000);
}

async function checkWeatherChange() {
    if (!currentLat && !currentLon && !document.getElementById("location").value) return;

    const params = currentLat
        ? `lat=${currentLat}&lon=${currentLon}`
        : `location=${encodeURIComponent(document.getElementById("location").value)}`;

    try {
        const res = await fetch(`/weather_now?${params}`);
        const data = await res.json();
        if (data.error) return;

        if (lastWeatherSnapshot) {
            const tempDiff = Math.abs(data.temp - lastWeatherSnapshot.temp);
            const humDiff  = Math.abs(data.humidity - lastWeatherSnapshot.humidity);
            const descChanged = data.description !== lastWeatherSnapshot.description;

            if (tempDiff >= 5) {
                showNotification("Temperature Alert", `Temperature changed by ${tempDiff}°C — now ${data.temp}°C in ${data.city}`);
            } else if (humDiff >= 20) {
                showNotification("Humidity Alert", `Humidity shifted to ${data.humidity}% in ${data.city}. Check crop disease risk.`);
            } else if (descChanged) {
                showNotification("Weather Changed", `Conditions shifted to "${data.description}" in ${data.city}`);
            }
        }
        lastWeatherSnapshot = data;
        updateMiniWeather(data);
    } catch (err) {
        console.warn("Polling error:", err);
    }
}

function updateMiniWeather(data) {
    document.getElementById("miniCityName").textContent = data.city || "";
    document.getElementById("miniTemp").textContent = `${data.temp}°C`;
    const iconUrl = `https://openweathermap.org/img/wn/${data.icon}@2x.png`;
    document.getElementById("miniWeatherIcon").innerHTML = `<img src="${iconUrl}" width="36" height="36" alt="${data.description}">`;
}

// ============================================================
//  LOCATION DETECTION
// ============================================================
function detectLocation() {
    const gpsBtn = document.getElementById("gpsBtn");
    const status  = document.getElementById("locationStatus");

    gpsBtn.classList.add("spinning");
    status.textContent = "📡 Detecting your location...";

    if (!navigator.geolocation) {
        status.textContent = "❌ Geolocation not supported. Enter city manually.";
        gpsBtn.classList.remove("spinning");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            currentLat = pos.coords.latitude;
            currentLon = pos.coords.longitude;

            // Reverse geocode to get city name
            try {
                const res = await fetch(
                    `http://api.openweathermap.org/geo/1.0/reverse?lat=${currentLat}&lon=${currentLon}&limit=1&appid=29970895b493a3a583640ede3b46c2b0`
                );
                const geo = await res.json();
                if (geo.length > 0) {
                    const city = geo[0].name;
                    document.getElementById("location").value = `${city},${geo[0].country}`;
                    status.textContent = `✅ Location detected: ${city}`;
                } else {
                    status.textContent = `✅ GPS coords: ${currentLat.toFixed(2)}, ${currentLon.toFixed(2)}`;
                }
            } catch {
                status.textContent = `✅ GPS coords: ${currentLat.toFixed(2)}, ${currentLon.toFixed(2)}`;
            }

            gpsBtn.classList.remove("spinning");

            // Load forecast and mini weather
            loadForecast(currentLat, currentLon);
            checkWeatherChange();
            startWeatherPolling();
        },
        () => {
            gpsBtn.classList.remove("spinning");
            status.textContent = "❌ Location denied. Enter city manually.";
        }
    );
}

// ============================================================
//  FORECAST
// ============================================================
async function loadForecast(lat, lon, city) {
    const strip   = document.getElementById("forecastStrip");
    const loading = document.getElementById("forecastLoading");
    const label   = document.getElementById("forecastCityLabel");

    loading.style.display = "flex";
    strip.innerHTML = "";

    const params = lat ? `lat=${lat}&lon=${lon}` : `location=${encodeURIComponent(city)}`;

    try {
        const res  = await fetch(`/forecast?${params}`);
        const data = await res.json();

        if (data.error) {
            loading.innerHTML = `<p style="color:#f87171">⚠️ ${data.error}</p>`;
            return;
        }

        label.textContent = `📍 ${data.city}`;
        loading.style.display = "none";

        const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

        data.forecast.forEach(day => {
            const d = new Date(day.date);
            const dayName = days[d.getDay()];
            const iconUrl = `https://openweathermap.org/img/wn/${day.icon}@2x.png`;
            const rain = day.rain > 0 ? `<div class="fc-rain">🌧️ ${day.rain}mm</div>` : "";

            strip.innerHTML += `
                <div class="forecast-card">
                    <div class="fc-day">${dayName}</div>
                    <div class="fc-date">${day.date.slice(5)}</div>
                    <img class="fc-icon" src="${iconUrl}" alt="${day.description}">
                    <div class="fc-desc">${day.description}</div>
                    <div class="fc-temp">${day.temp}°C</div>
                    <div class="fc-range">${day.temp_min}° – ${day.temp_max}°</div>
                    <div class="fc-humidity">💧 ${day.humidity}%</div>
                    <div class="fc-wind">💨 ${day.wind} km/h</div>
                    ${rain}
                </div>
            `;
        });
    } catch (err) {
        loading.innerHTML = `<p style="color:#f87171">⚠️ Failed to load forecast</p>`;
    }
}

// ============================================================
//  PREDICTION
// ============================================================
async function predict() {
    const btn       = document.getElementById("predictBtn");
    const resultDiv = document.getElementById("result");
    const location  = document.getElementById("location").value.trim();
    const stage     = document.getElementById("stage").value;

    if (!location && !currentLat) {
        resultDiv.innerHTML = '<p style="color:#f87171">⚠️ Please enter or detect a location first.</p>';
        resultDiv.classList.remove("hidden");
        return;
    }

    btn.innerHTML = '<span class="spinner-sm"></span> Predicting...';
    btn.disabled = true;
    resultDiv.classList.add("hidden");

    const body = currentLat
        ? { lat: currentLat, lon: currentLon, growth_stage: stage }
        : { location, growth_stage: stage };

    try {
        const res  = await fetch("/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        const data = await res.json();

        if (data.error) {
            resultDiv.innerHTML = `<p style="color:#f87171">⚠️ ${data.error}</p>`;
        } else {
            lastDisease = data.disease;
            lastRisk    = data.risk;

            const riskColor = data.risk === "High" ? "#f87171" : data.risk === "Medium" ? "#fbbf24" : "#4ade80";

            resultDiv.innerHTML = `
                <div class="result-header">📊 Prediction Results for <strong>${data.location}</strong></div>
                <div class="result-grid">
                    <div class="result-stat">
                        <span class="stat-label">🦠 Disease</span>
                        <span class="stat-value">${data.disease}</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-label">⚠️ Risk Level</span>
                        <span class="stat-value" style="color:${riskColor}">${data.risk}</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-label">🌡️ Temperature</span>
                        <span class="stat-value">${data.temperature}°C</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-label">💧 Humidity</span>
                        <span class="stat-value">${data.humidity}%</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-label">🌧️ Rainfall</span>
                        <span class="stat-value">${data.rainfall} mm</span>
                    </div>
                </div>
                <p class="result-tip">💬 Ask the AI advisor below for treatment recommendations!</p>
            `;
        }
        resultDiv.classList.remove("hidden");
    } catch (err) {
        resultDiv.innerHTML = `<p style="color:#f87171">⚠️ Network error: ${err.message}</p>`;
        resultDiv.classList.remove("hidden");
    }

    btn.innerHTML = '<span>🔍 Predict Disease</span>';
    btn.disabled = false;
}

// ============================================================
//  CAMERA
// ============================================================
async function openCamera() {
    const preview = document.getElementById("cameraPreview");
    const video   = document.getElementById("cameraVideo");
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        video.srcObject = cameraStream;
        preview.style.display = "flex";
        document.getElementById("imagePreviewWrap").style.display = "none";
        document.getElementById("scanResult").classList.add("hidden");
    } catch (err) {
        alert("❌ Camera access denied or not available on this device.");
    }
}

function captureImage() {
    const video  = document.getElementById("cameraVideo");
    const canvas = document.createElement("canvas");
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    capturedImageBase64 = canvas.toDataURL("image/jpeg");
    capturedMimeType = "image/jpeg";
    showImagePreview(capturedImageBase64);
    stopCamera();
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null;
    }
    document.getElementById("cameraPreview").style.display = "none";
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
        alert("❌ Please select a valid image file.");
        return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert("❌ Image is too large. Please select an image under 10MB.");
        return;
    }

    capturedMimeType = file.type || "image/jpeg";

    const reader = new FileReader();
    reader.onload = (e) => {
        capturedImageBase64 = e.target.result;
        showImagePreview(capturedImageBase64);
    };
    reader.onerror = () => {
        alert("❌ Failed to read image file. Please try again.");
    };
    reader.readAsDataURL(file);

    // Reset input so same file can be re-selected
    event.target.value = "";
}

function showImagePreview(src) {
    document.getElementById("imagePreview").src = src;
    document.getElementById("imagePreviewWrap").style.display = "flex";
    document.getElementById("scanResult").classList.add("hidden");
}

// ============================================================
//  IMAGE ANALYSIS
// ============================================================
async function analyseImage() {
    if (!capturedImageBase64) {
        alert("❌ No image selected. Please capture or upload an image first.");
        return;
    }

    const btn        = document.getElementById("analyseBtn");
    const scanResult = document.getElementById("scanResult");

    btn.innerHTML = '<span class="spinner-sm"></span> Analysing...';
    btn.disabled  = true;
    scanResult.classList.add("hidden");

    try {
        // Send ONLY the base64 portion (strip the data:...;base64, prefix on server)
        const res  = await fetch("/scan_crop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                image: capturedImageBase64,
                mime_type: capturedMimeType
            })
        });

        if (!res.ok) {
            throw new Error(`Server error: ${res.status} ${res.statusText}`);
        }

        const data = await res.json();

        if (data.error) {
            scanResult.innerHTML = `
                <div class="scan-result-header">⚠️ Analysis Failed</div>
                <div class="scan-result-body" style="color:#f87171">${data.error}</div>
            `;
        } else {
            // Format analysis text with proper line breaks and emoji separators
            const formatted = data.analysis
                .replace(/\r\n/g, "\n")
                .replace(/\n{3,}/g, "\n\n")
                .replace(/\n/g, "<br>")
                .replace(/(🔍|⚠️|📋|🌱|💊|⏰|🚫)/g, '<br><strong>$1');

            scanResult.innerHTML = `
                <div class="scan-result-header">🤖 AI Crop Analysis Complete</div>
                <div class="scan-result-body">${formatted}</div>
            `;

            // Store disease context for chatbot
            const match = data.analysis.match(/DISEASE DETECTED:\s*([^\n]+)/);
            if (match) { lastDisease = match[1].trim(); }
        }
        scanResult.classList.remove("hidden");
    } catch (err) {
        scanResult.innerHTML = `
            <div class="scan-result-header">⚠️ Connection Error</div>
            <div class="scan-result-body" style="color:#f87171">
                Failed to analyse: ${err.message}<br><br>
                <small>Please check your internet connection and try again.</small>
            </div>
        `;
        scanResult.classList.remove("hidden");
    }

    btn.innerHTML = '🤖 Analyse Crop';
    btn.disabled  = false;
}

// ============================================================
//  CHATBOT
// ============================================================
async function sendChat() {
    const input   = document.getElementById("chatInput");
    const msg     = input.value.trim();
    if (!msg) return;

    const chatBox = document.getElementById("chatBox");
    chatBox.innerHTML += `<div class="user"><div class="bubble">${escapeHtml(msg)}</div></div>`;
    input.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    // Typing indicator
    const typingId = "typing_" + Date.now();
    chatBox.innerHTML += `<div class="bot" id="${typingId}"><div class="bubble typing"><span></span><span></span><span></span></div></div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const res  = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg, disease: lastDisease, risk: lastRisk })
        });

        if (!res.ok) throw new Error(`Server error: ${res.status}`);

        const data = await res.json();
        document.getElementById(typingId)?.remove();

        const reply = data.reply || data.error || "Something went wrong.";
        chatBox.innerHTML += `<div class="bot"><div class="bubble">${reply.replace(/\n/g, "<br>")}</div></div>`;
    } catch (err) {
        document.getElementById(typingId)?.remove();
        chatBox.innerHTML += `<div class="bot"><div class="bubble" style="color:#f87171">❌ Network error: ${err.message}</div></div>`;
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Alias for backward compat if needed
const chat = sendChat;

// ============================================================
//  UTILITY
// ============================================================
function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}