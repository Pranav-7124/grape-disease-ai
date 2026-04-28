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
    document.getElementById("notifText").textContent = `⚠️ ${title}: ${body}`;
    document.getElementById("notifBanner").classList.remove("hidden");

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
//  WEATHER POLLING
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
        if (data.error) {
            console.warn("Weather error:", data.error);
            return;
        }

        if (lastWeatherSnapshot) {
            const tempDiff = Math.abs(data.temp - lastWeatherSnapshot.temp);
            const humDiff  = Math.abs(data.humidity - lastWeatherSnapshot.humidity);
            const descChanged = data.description !== lastWeatherSnapshot.description;

            if (tempDiff >= 5) {
                showNotification("Temperature Alert", `Now ${data.temp}°C in ${data.city}`);
            } else if (humDiff >= 20) {
                showNotification("Humidity Alert", `Humidity ${data.humidity}% in ${data.city}`);
            } else if (descChanged) {
                showNotification("Weather Changed", data.description);
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
    document.getElementById("miniWeatherIcon").innerHTML =
        `<img src="${iconUrl}" width="36" alt="weather">`;
}

// ============================================================
//  LOCATION DETECTION
// ============================================================
function detectLocation() {
    const gpsBtn = document.getElementById("gpsBtn");
    const status  = document.getElementById("locationStatus");

    gpsBtn.classList.add("spinning");
    status.textContent = "📡 Detecting location...";

    if (!navigator.geolocation) {
        status.textContent = "❌ Not supported";
        gpsBtn.classList.remove("spinning");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            currentLat = pos.coords.latitude;
            currentLon = pos.coords.longitude;

            try {
                const res = await fetch(`/weather_now?lat=${currentLat}&lon=${currentLon}`);
                const data = await res.json();

                if (data.city) {
                    document.getElementById("location").value = data.city;
                    status.textContent = `✅ ${data.city}`;
                } else {
                    status.textContent = `✅ ${currentLat.toFixed(2)}, ${currentLon.toFixed(2)}`;
                }

            } catch {
                status.textContent = "⚠️ Location detected";
            }

            gpsBtn.classList.remove("spinning");
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
    const strip = document.getElementById("forecastStrip");
    const loading = document.getElementById("forecastLoading");

    loading.style.display = "block";
    strip.innerHTML = "";

    const params = lat ? `lat=${lat}&lon=${lon}` : `location=${encodeURIComponent(city || "")}`;

    try {
        const res = await fetch(`/forecast?${params}`);
        const data = await res.json();

        loading.style.display = "none";

        if (data.error) {
            strip.innerHTML = `<div class="forecast-error">⚠️ ${data.error}</div>`;
            return;
        }

        if (!data.forecast || data.forecast.length === 0) {
            strip.innerHTML = `<div class="forecast-error">No forecast available</div>`;
            return;
        }

        document.getElementById("forecastCityLabel").textContent = data.city || "";

        strip.innerHTML = data.forecast.map(day => `
            <div class="forecast-card">
                <div class="forecast-date">${formatDate(day.date)}</div>
                <div class="forecast-temp">${day.temp}°C</div>
                <div class="forecast-desc">${capitalize(day.description)}</div>
            </div>
        `).join("");

    } catch (err) {
        loading.style.display = "none";
        strip.innerHTML = `<div class="forecast-error">⚠️ Failed to load forecast</div>`;
        console.error("Forecast error:", err);
    }
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function capitalize(str) {
    return str.replace(/\b\w/g, l => l.toUpperCase());
}

// ============================================================
//  PREDICT
// ============================================================
async function predict() {
    const btn = document.getElementById("predictBtn");
    const resultBox = document.getElementById("result");
    const location = document.getElementById("location").value;
    const stage = document.getElementById("stage").value;

    if (!location && !currentLat) {
        showResult("❌ Please enter a location or use GPS detection.");
        return;
    }

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-inline"></span> Analyzing...`;
    resultBox.classList.add("hidden");

    const body = currentLat
        ? { lat: currentLat, lon: currentLon, growth_stage: stage }
        : { location, growth_stage: stage };

    try {
        const res = await fetch("/predict", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body)
        });

        const data = await res.json();
        resultBox.classList.remove("hidden");

        if (data.error) {
            showResult(`<div class="result-error">⚠️ ${data.error}</div>`);
        } else {
            lastDisease = data.disease;
            lastRisk = data.risk;
            showResult(`
                <div class="result-grid">
                    <div class="result-item"><strong>📍 Location</strong><span>${data.location}</span></div>
                    <div class="result-item"><strong>🌡️ Temperature</strong><span>${data.temperature}°C</span></div>
                    <div class="result-item"><strong>💧 Humidity</strong><span>${data.humidity}%</span></div>
                    <div class="result-item"><strong>🌧️ Rainfall</strong><span>${data.rainfall}mm</span></div>
                    <div class="result-item result-disease"><strong>🦠 Disease</strong><span>${data.disease}</span></div>
                    <div class="result-item result-risk"><strong>⚡ Risk</strong><span>${data.risk}</span></div>
                </div>
            `);
        }
    } catch (err) {
        resultBox.classList.remove("hidden");
        showResult(`<div class="result-error">⚠️ Network error. Please try again.</div>`);
        console.error("Predict error:", err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>🔍 Predict Disease</span>`;
    }
}

function showResult(html) {
    document.getElementById("result").innerHTML = html;
}

// ============================================================
//  CAMERA & IMAGE SCANNER
// ============================================================
function openCamera() {
    const preview = document.getElementById("cameraPreview");
    const video = document.getElementById("cameraVideo");

    preview.style.display = "flex";
    document.getElementById("imagePreviewWrap").style.display = "none";
    capturedImageBase64 = null;

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => {
                cameraStream = stream;
                video.srcObject = stream;
            })
            .catch(err => {
                alert("Could not access camera: " + err.message);
                stopCamera();
            });
    } else {
        alert("Camera not supported on this device.");
        stopCamera();
    }
}

function stopCamera() {
    const preview = document.getElementById("cameraPreview");
    const video = document.getElementById("cameraVideo");

    preview.style.display = "none";
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    video.srcObject = null;
}

function captureImage() {
    const video = document.getElementById("cameraVideo");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    capturedImageBase64 = canvas.toDataURL("image/jpeg");
    capturedMimeType = "image/jpeg";

    stopCamera();
    showImagePreview(capturedImageBase64);
}

function handleImageUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    capturedMimeType = file.type || "image/jpeg";
    const reader = new FileReader();
    reader.onload = (e) => {
        capturedImageBase64 = e.target.result;
        showImagePreview(capturedImageBase64);
    };
    reader.readAsDataURL(file);
}

function showImagePreview(src) {
    const wrap = document.getElementById("imagePreviewWrap");
    const img = document.getElementById("imagePreview");
    img.src = src;
    wrap.style.display = "flex";
    document.getElementById("scanResult").classList.add("hidden");
}

async function analyseImage() {
    if (!capturedImageBase64) {
        alert("No image captured. Please take a photo or upload one.");
        return;
    }

    const btn = document.getElementById("analyseBtn");
    const result = document.getElementById("scanResult");

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-inline"></span> Analysing...`;
    result.classList.remove("hidden");
    result.innerHTML = `<div class="scan-loading">🤖 Analysing crop image...</div>`;

    try {
        const res = await fetch("/scan", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                image: capturedImageBase64,
                mime_type: capturedMimeType
            })
        });

        const data = await res.json();

        if (data.error) {
            result.innerHTML = `<div class="scan-error">⚠️ ${data.error}</div>`;
        } else {
            result.innerHTML = `
                <div class="scan-result-box">
                    <h4>📊 Analysis Result</h4>
                    <div class="scan-disease">${data.disease_detected}</div>
                    <div class="scan-confidence">Confidence: ${data.confidence || "N/A"}</div>
                    <div class="scan-advice">${data.advice || ""}</div>
                </div>
            `;
        }
    } catch (err) {
        result.innerHTML = `<div class="scan-error">⚠️ Analysis failed. Please try again.</div>`;
        console.error("Scan error:", err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `🤖 Analyse Crop`;
    }
}

// ============================================================
//  CHATBOT
// ============================================================
async function sendChat() {
    const input = document.getElementById("chatInput");
    const box = document.getElementById("chatBox");
    const msg = input.value.trim();

    if (!msg) return;

    // Add user message
    appendChatMessage(msg, "user");
    input.value = "";

    // Add loading indicator
    const loadingId = "chat-loading-" + Date.now();
    appendChatMessage("🤔 Thinking...", "bot", loadingId);

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ message: msg })
        });

        const data = await res.json();

        // Remove loading indicator
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        if (data.error) {
            appendChatMessage(`⚠️ ${data.error}`, "bot");
        } else {
            // Format the response nicely
            const formatted = formatChatReply(data.reply);
            appendChatMessage(formatted, "bot");
        }
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        appendChatMessage("⚠️ Sorry, I couldn't connect. Please try again.", "bot");
        console.error("Chat error:", err);
    }

    // Scroll to bottom
    box.scrollTop = box.scrollHeight;
}

function appendChatMessage(text, sender, id) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = sender === "user" ? "chat-user" : "chat-bot";
    if (id) div.id = id;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = text;

    div.appendChild(bubble);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function formatChatReply(text) {
    if (!text) return "";

    // Convert markdown-style bold to HTML
    text = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\*(.+?)\*/g, "<em>$1</em>");

    // Convert bullet points
    text = text.replace(/^\s*[-•]\s+(.+)$/gm, "<li>$1</li>");
    if (text.includes("<li>")) {
        text = text.replace(/(<li>.+<\/li>)/s, "<ul>$1</ul>");
    }

    // Convert line breaks to paragraphs
    const paragraphs = text.split(/\n\n+/).map(p => {
        p = p.trim();
        if (!p) return "";
        if (p.startsWith("<ul>")) return p;
        if (p.startsWith("<li>")) return `<ul>${p}</ul>`;
        return `<p>${p.replace(/\n/g, "<br>")}</p>`;
    }).filter(Boolean);

    return paragraphs.join("");
}

