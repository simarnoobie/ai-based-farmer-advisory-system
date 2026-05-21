const chatBox          = document.getElementById("chatBox");
const userInput        = document.getElementById("userInput");
const imageInput       = document.getElementById("imageInput");
const userBadge        = document.getElementById("userBadge");
const languageSelect   = document.getElementById("languageSelect");
const cropTypeInput    = document.getElementById("cropType");
const seasonSelect     = document.getElementById("seasonSelect");
const landSizeInput    = document.getElementById("landSize");
const irrigationSelect = document.getElementById("irrigationSelect");
const groundwaterStress = document.getElementById("groundwaterStress");
const mspDependency    = document.getElementById("mspDependency");
const speakReply       = document.getElementById("speakReply");
const voiceBtn         = document.getElementById("voiceBtn");
const settingsPanel    = document.getElementById("settingsPanel");
const settingsToggle   = document.getElementById("settingsToggle");

const API_BASE_URL = window.BACKEND_URL || "http://127.0.0.1:8000";

// ── Init ───────────────────────────────────────────────────────────
const username = localStorage.getItem("farmer_username") || "Guest";
if (userBadge) userBadge.textContent = username;

let currentLocation = { latitude: null, longitude: null };
let recognition     = null;
let listening       = false;

// Pre-load TTS voices (browsers load them asynchronously)
let _voices = [];
function _loadVoices() { _voices = window.speechSynthesis.getVoices(); }
_loadVoices();
if (window.speechSynthesis) {
    window.speechSynthesis.addEventListener("voiceschanged", _loadVoices);
}

// ── Helpers ────────────────────────────────────────────────────────
function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = String(text);
    return d.innerHTML;
}

function appendMessage(sender, html, isLoader = false) {
    const wrap   = document.createElement("div");
    wrap.classList.add("message", sender);

    if (sender === "ai") {
        const img = document.createElement("img");
        img.src = "../assets/avatar.png";
        img.classList.add("avatar");
        img.alt = "AI";
        wrap.appendChild(img);
    }

    const bubble = document.createElement("div");
    bubble.classList.add("bubble");

    if (isLoader) {
        bubble.classList.add("thinking");
        bubble.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        wrap.id = "ai-thinking";
    } else {
        bubble.innerHTML = html;
    }

    wrap.appendChild(bubble);
    chatBox.appendChild(wrap);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function fillPrompt(text) {
    userInput.value = text;
    userInput.focus();
}

function logout() {
    localStorage.removeItem("farmer_token");
    localStorage.removeItem("farmer_username");
    window.location.href = "../login_page/login.html";
}

// ── Settings panel toggle ──────────────────────────────────────────
function toggleSettings() {
    const isOpen = settingsPanel.classList.toggle("open");
    settingsToggle.classList.toggle("active", isOpen);
    settingsToggle.textContent = isOpen ? "✕ Close Profile" : "⚙ Farmer Profile";
}

// ── Speech ─────────────────────────────────────────────────────────
function getSpeechLang() {
    const lang = languageSelect.value;
    if (lang === "hi") return "hi-IN";
    if (lang === "pa") return "pa-IN";
    return "en-IN";
}

function getBestVoice(langCode) {
    if (!_voices.length) _loadVoices();
    // Exact match
    let v = _voices.find(x => x.lang === langCode);
    if (v) return v;
    // Prefix match (e.g. hi for hi-IN)
    const prefix = langCode.split("-")[0];
    v = _voices.find(x => x.lang.startsWith(prefix));
    if (v) return v;
    // Punjabi fallback → Hindi (closely related, same script family)
    if (langCode === "pa-IN") {
        v = _voices.find(x => x.lang.startsWith("hi"));
        if (v) return v;
    }
    return null;
}

function speakText(text) {
    if (!("speechSynthesis" in window) || !speakReply.checked) return;
    const clean    = text.replace(/<[^>]*>/g, "").trim();
    if (!clean) return;
    const langCode = getSpeechLang();
    const utt      = new SpeechSynthesisUtterance(clean);
    utt.lang  = langCode;
    const voice = getBestVoice(langCode);
    if (voice) utt.voice = voice;
    utt.rate   = 0.92;
    utt.pitch  = 1.0;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utt);
}

// ── Voice input ────────────────────────────────────────────────────
function toggleVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        appendMessage("ai", "Voice input is not supported in this browser. Try Chrome or Edge.");
        return;
    }

    if (!recognition) {
        recognition = new SpeechRecognition();
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = (e) => {
            userInput.value = e.results[0][0].transcript || "";
        };
        recognition.onend = () => {
            listening = false;
            voiceBtn.classList.remove("recording");
            voiceBtn.title = "Voice input";
            if (userInput.value.trim()) sendMessage();
        };
        recognition.onerror = () => {
            listening = false;
            voiceBtn.classList.remove("recording");
            voiceBtn.title = "Voice input";
        };
    }

    if (listening) {
        recognition.stop();
        return;
    }
    recognition.lang = getSpeechLang();
    recognition.start();
    listening = true;
    voiceBtn.classList.add("recording");
    voiceBtn.title = "Stop recording";
}

// ── Location ───────────────────────────────────────────────────────
function captureLocation() {
    if (!navigator.geolocation) {
        appendMessage("ai", "Geolocation is not supported in this browser.");
        return;
    }
    appendMessage("ai", "Fetching your location…");
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            currentLocation.latitude  = pos.coords.latitude;
            currentLocation.longitude = pos.coords.longitude;
            // Replace the "fetching" message
            const last = document.getElementById("ai-thinking") || chatBox.lastElementChild;
            if (last) last.remove();
            appendMessage("ai", "📍 Location captured! Weather-based advice is now enabled.");
        },
        () => {
            const last = chatBox.lastElementChild;
            if (last) last.remove();
            appendMessage("ai", "Could not get location. You can continue without it.");
        }
    );
}

// ── Send message ───────────────────────────────────────────────────
async function sendMessage(file = null) {
    const question = userInput.value.trim();
    const token    = localStorage.getItem("farmer_token");

    if (!question && !file) return;

    if (file) {
        appendMessage("user", "&#128247; <em>Sent a leaf image for diagnosis…</em>");
    } else {
        appendMessage("user", escapeHtml(question).replace(/\n/g, "<br>"));
    }

    userInput.value = "";
    appendMessage("ai", "", true); // loader

    const fd = new FormData();
    if (question)                    fd.append("query",      question);
    if (file)                        fd.append("file",       file);
    fd.append("language", languageSelect.value || "en");
    if (cropTypeInput.value.trim())  fd.append("crop_type",       cropTypeInput.value.trim());
    if (seasonSelect.value)          fd.append("season",          seasonSelect.value);
    if (landSizeInput.value.trim())  fd.append("land_size",       landSizeInput.value.trim());
    if (irrigationSelect.value)      fd.append("irrigation_type", irrigationSelect.value);
    fd.append("groundwater_stress", groundwaterStress.checked ? "true" : "false");
    fd.append("msp_dependency",     mspDependency.checked     ? "true" : "false");
    if (currentLocation.latitude  !== null) fd.append("latitude",  currentLocation.latitude);
    if (currentLocation.longitude !== null) fd.append("longitude", currentLocation.longitude);

    try {
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(`${API_BASE_URL}/ask`, { method: "POST", body: fd, headers });

        document.getElementById("ai-thinking")?.remove();

        if (!res.ok) {
            let detail = `Server error (${res.status})`;
            try { detail = (await res.json()).detail || detail; } catch (_) {}
            throw new Error(detail);
        }

        const data = await res.json();

        // Escape LLM/model output before injecting into HTML
        const safeResponse = escapeHtml(data.response || "").replace(/\n/g, "<br>");
        let output = safeResponse;

        if (data.detected) {
            const pct = data.confidence != null
                ? ` <span style="opacity:.75">(${Math.round(data.confidence * 100)}% confidence)</span>`
                : '';
            output = `<strong>🔬 Diagnosis:</strong> ${escapeHtml(data.detected)}${pct}<br><br>${safeResponse}`;
            if (Array.isArray(data.top3) && data.top3.length > 1) {
                const alts = data.top3.slice(1)
                    .map(p => `${escapeHtml(p.class)} (${Math.round(p.confidence * 100)}%)`)
                    .join(' · ');
                output += `<div class="policy-ref">📊 <strong>Other possibilities:</strong> ${alts}</div>`;
            }
        }
        if (Array.isArray(data.policies) && data.policies.length > 0) {
            const refs = data.policies
                .map(p => `${escapeHtml(p.title)} <span style="opacity:.7">(${escapeHtml(p.source)})</span>`)
                .join(" · ");
            output += `<div class="policy-ref">🏛 <strong>Relevant schemes:</strong> ${refs}</div>`;
        }

        appendMessage("ai", output);
        speakText(data.response || "");

    } catch (err) {
        console.error(err);
        document.getElementById("ai-thinking")?.remove();
        appendMessage("ai", `⚠ Request failed: ${escapeHtml(err.message)}`);
    }
}

// ── Event listeners ────────────────────────────────────────────────
imageInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) sendMessage(e.target.files[0]);
});

userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) sendMessage();
});
