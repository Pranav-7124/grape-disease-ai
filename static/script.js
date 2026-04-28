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
        if (data.error) return;

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
        `<img src="${iconUrl}" width="36">`;
}

// ============================================================
//  LOCATION DETECTION (FIXED - NO API KEY)
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
            status.textContent = "❌ Location denied";
        }
    );
}

// ============================================================
//  FORECAST
// ============================================================
async function loadForecast(lat, lon, city) {
    const strip = document.getElementById("forecastStrip");
    strip.innerHTML = "";

    const params = lat ? `lat=${lat}&lon=${lon}` : `location=${city}`;

    const res = await fetch(`/forecast?${params}`);
    const data = await res.json();

    if (!data.forecast) return;

    data.forecast.forEach(day => {
        strip.innerHTML += `
            <div class="forecast-card">
                <div>${day.date}</div>
                <div>${day.temp}°C</div>
                <div>${day.description}</div>
            </div>
        `;
    });
}

// ============================================================
//  PREDICT
// ============================================================
async function predict() {
    const location = document.getElementById("location").value;
    const stage = document.getElementById("stage").value;

    const body = currentLat
        ? { lat: currentLat, lon: currentLon, growth_stage: stage }
        : { location, growth_stage: stage };

    const res = await fetch("/predict", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
    });

    const data = await res.json();

    document.getElementById("result").innerHTML = JSON.stringify(data, null, 2);
}

// ============================================================
//  CHAT
// ============================================================
async function sendChat() {
    const msg = document.getElementById("chatInput").value;

    const res = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ message: msg })
    });

    const data = await res.json();
    document.getElementById("chatBox").innerHTML += `<p>${data.reply}</p>`;
}