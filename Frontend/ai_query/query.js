const API_BASE_URL = window.BACKEND_URL || "http://127.0.0.1:8000";

// ── DOM refs ───────────────────────────────────────────────────────
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

// ── Init ───────────────────────────────────────────────────────────
const username = localStorage.getItem("farmer_username") || "Guest";
if (userBadge) userBadge.textContent = username;

let currentLocation = { latitude: null, longitude: null };
let recognition     = null;
let listening       = false;
let sidebarOpen     = true;

// Pre-load TTS voices
let _voices = [];
function _loadVoices() { _voices = window.speechSynthesis?.getVoices() || []; }
_loadVoices();
if (window.speechSynthesis) window.speechSynthesis.addEventListener("voiceschanged", _loadVoices);

// Load history on page load
window.addEventListener("DOMContentLoaded", loadHistory);

// ── Sidebar ────────────────────────────────────────────────────────
function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    document.getElementById("sidebar").classList.toggle("collapsed", !sidebarOpen);
}

function newChat() {
    chatBox.innerHTML = `
        <div class="message ai">
            <img src="../assets/avatar.png" class="avatar" alt="AI" onerror="this.style.display='none'">
            <div class="bubble">
                <strong>ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! नमस्ते! Hello! 👋</strong><br><br>
                I am your <strong>AI Farming Assistant</strong>. Ask me about:<br>
                🌱 Crop diseases &amp; treatments<br>
                💧 Irrigation &amp; soil health<br>
                🏛 Government schemes &amp; MSP<br>
                🌤 Weather-based advice<br>
                📸 Upload a leaf photo for instant disease diagnosis<br><br>
                <em>Fill in your Farmer Profile on the left for personalised advice.</em>
            </div>
        </div>`;
    userInput.focus();
}

// ── Chat history ───────────────────────────────────────────────────
async function loadHistory() {
    const token = localStorage.getItem("farmer_token");
    if (!token) return;
    try {
        const resp = await fetch(`${API_BASE_URL}/history`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!resp.ok) return;
        const data = await resp.json();
        renderHistoryList(data.history || []);
    } catch (_) {}
}

function renderHistoryList(items) {
    const list = document.getElementById("historyList");
    if (!items.length) return;
    list.innerHTML = items.slice(0, 40).map(item => {
        const q = (item.user_query || "").replace(/\[Image scan.*?\]/g, "📸 Image scan");
        const preview = q.length > 36 ? q.slice(0, 36) + "…" : q || "…";
        const time = item.created_at
            ? new Date(item.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
            : "";
        return `<div class="history-item" onclick='replayHistory(${JSON.stringify(item)})'>
            <div class="hi-query">${escapeHtml(preview)}</div>
            <div class="hi-time">${escapeHtml(time)}</div>
        </div>`;
    }).join("");
}

function replayHistory(item) {
    appendMessage("user", escapeHtml(item.user_query || "📸 Image scan"));
    appendMessage("ai", escapeHtml(item.ai_response || "").replace(/\n/g, "<br>"));
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Helpers ────────────────────────────────────────────────────────
function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = String(text);
    return d.innerHTML;
}

function appendMessage(sender, html, isLoader = false) {
    const wrap = document.createElement("div");
    wrap.classList.add("message", sender);

    if (sender === "ai") {
        const img = document.createElement("img");
        img.src = "../assets/avatar.png";
        img.classList.add("avatar");
        img.alt = "AI";
        img.onerror = () => img.style.display = "none";
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

// ── Speech output ──────────────────────────────────────────────────
function getSpeechLang() {
    const lang = languageSelect.value;
    if (lang === "hi") return "hi-IN";
    if (lang === "pa") return "pa-IN";
    return "en-IN";
}

function getBestVoice(langCode) {
    if (!_voices.length) _loadVoices();
    let v = _voices.find(x => x.lang === langCode);
    if (v) return v;
    const prefix = langCode.split("-")[0];
    v = _voices.find(x => x.lang.startsWith(prefix));
    if (v) return v;
    if (langCode === "pa-IN") v = _voices.find(x => x.lang.startsWith("hi"));
    return v || null;
}

const stopAudioBtn = document.getElementById("stopAudioBtn");

function stopAudio() {
    window.speechSynthesis?.cancel();
    stopAudioBtn.style.display = "none";
}

function speakText(text) {
    if (!("speechSynthesis" in window) || !speakReply.checked) return;
    const clean = text.replace(/<[^>]*>/g, "").trim();
    if (!clean) return;
    const langCode = getSpeechLang();
    const utt = new SpeechSynthesisUtterance(clean);
    utt.lang  = langCode;
    const voice = getBestVoice(langCode);
    if (voice) utt.voice = voice;
    utt.rate  = 0.92;
    utt.pitch = 1.0;
    utt.onstart = () => { stopAudioBtn.style.display = "flex"; };
    utt.onend   = () => { stopAudioBtn.style.display = "none"; };
    utt.onerror = () => { stopAudioBtn.style.display = "none"; };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utt);
}

// ── Voice input ────────────────────────────────────────────────────
function toggleVoiceInput() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        appendMessage("ai", "Voice input is not supported in this browser. Try Chrome or Edge.");
        return;
    }
    if (!recognition) {
        recognition = new SR();
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        recognition.onresult = (e) => { userInput.value = e.results[0][0].transcript || ""; };
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
    if (listening) { recognition.stop(); return; }
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
            const last = document.getElementById("ai-thinking") || chatBox.lastElementChild;
            if (last) last.remove();
            appendMessage("ai", "📍 Location captured! Weather-based advice is now enabled for your area.");
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
        appendMessage("user", "📸 <em>Sent a leaf image for diagnosis…</em>");
    } else {
        appendMessage("user", escapeHtml(question).replace(/\n/g, "<br>"));
    }

    userInput.value = "";
    appendMessage("ai", "", true);

    const fd = new FormData();
    if (question)                        fd.append("query",            question);
    if (file)                            fd.append("file",             file);
    fd.append("language", languageSelect.value || "en");
    if (cropTypeInput.value.trim())      fd.append("crop_type",        cropTypeInput.value.trim());
    if (seasonSelect.value)              fd.append("season",           seasonSelect.value);
    if (landSizeInput.value.trim())      fd.append("land_size",        landSizeInput.value.trim());
    if (irrigationSelect.value)          fd.append("irrigation_type",  irrigationSelect.value);
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
        const safeResponse = escapeHtml(data.response || "").replace(/\n/g, "<br>");
        let output = safeResponse;

        if (data.detected) {
            const pct = data.confidence != null
                ? ` <span style="opacity:.75">(${Math.round(data.confidence * 100)}% confidence)</span>` : "";
            output = `<strong>🔬 Diagnosis:</strong> ${escapeHtml(data.detected)}${pct}<br><br>${safeResponse}`;
            if (Array.isArray(data.top3) && data.top3.length > 1) {
                const alts = data.top3.slice(1)
                    .map(p => `${escapeHtml(p.class)} (${Math.round(p.confidence * 100)}%)`)
                    .join(" · ");
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

        // Refresh sidebar history
        loadHistory();

    } catch (err) {
        document.getElementById("ai-thinking")?.remove();
        appendMessage("ai", `⚠ Request failed: ${escapeHtml(err.message)}`);
    }
}

// ── Event listeners ────────────────────────────────────────────────
imageInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) sendMessage(e.target.files[0]);
});

userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
