import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import io
import hashlib
import secrets
import json
import logging
import time
import urllib.parse
import urllib.request
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models  # type: ignore
import mysql.connector
from mysql.connector import pooling
import ollama
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from punjab_policy_knowledge import retrieve_policy_context

# ---------------------------------------------------------------------------
# Load .env from the same directory as this file (no extra dependency needed)
# ---------------------------------------------------------------------------
def _load_env(env_path: Path) -> None:
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())
    except FileNotFoundError:
        pass

_load_env(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "app.log"),
    ],
)
log = logging.getLogger("farmer_ai")

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
DB_HOST     = os.environ.get("DB_HOST", "localhost")
DB_USER     = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME     = os.environ.get("DB_NAME", "farmer_ai")
OLLAMA_MODEL   = os.environ.get("OLLAMA_MODEL", "gemma3:1b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "30"))

MODEL_PATH     = Path(__file__).parent / "models" / "trained_farmer_model.h5"
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_TYPES  = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory, 15 req/min per IP)
# ---------------------------------------------------------------------------
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_RPM = 15

def _check_rate_limit(ip: str) -> bool:
    now = time.monotonic()
    window = _rate_store[ip] = [t for t in _rate_store[ip] if now - t < 60]
    if len(window) >= RATE_LIMIT_RPM:
        return False
    window.append(now)
    return True

# ---------------------------------------------------------------------------
# Database — initialise schema then create connection pool
# ---------------------------------------------------------------------------
def _init_db() -> None:
    conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD)
    cur  = conn.cursor()
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cur.execute(f"USE `{DB_NAME}`")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INT          AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL
        )
    """)
    # Widen existing password column in case it was created narrow
    cur.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id         INT       AUTO_INCREMENT PRIMARY KEY,
            user_id    INT,
            user_query TEXT,
            ai_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id           INT          AUTO_INCREMENT PRIMARY KEY,
            name         VARCHAR(100),
            mobile       VARCHAR(20),
            category     VARCHAR(50),
            rating       TINYINT,
            feedback     TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    log.info("Database schema ready.")

_db_pool: Optional[pooling.MySQLConnectionPool] = None

def _create_pool() -> None:
    global _db_pool
    _db_pool = pooling.MySQLConnectionPool(
        pool_name="farmer_pool",
        pool_size=5,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
    )
    log.info("DB connection pool created.")

def get_db():
    return _db_pool.get_connection()

# ---------------------------------------------------------------------------
# ML model
# ---------------------------------------------------------------------------
CLASSES = [
    'Apple_scab', 'Apple_black_rot', 'Apple_cedar_apple_rust', 'Apple_healthy',
    'Background_without_leaves', 'Blueberry_healthy', 'Cherry_powdery_mildew',
    'Cherry_healthy', 'Corn_gray_leaf_spot', 'Corn_common_rust',
    'Corn_northern_leaf_blight', 'Corn_healthy', 'Grape_black_rot',
    'Grape_black_measles', 'Grape_leaf_blight', 'Grape_healthy',
    'Orange_haunglongbing', 'Peach_bacterial_spot', 'Peach_healthy',
    'Pepper_bacterial_spot', 'Pepper_healthy', 'Potato_early_blight',
    'Potato_healthy', 'Potato_late_blight', 'Raspberry_healthy',
    'Soybean_healthy', 'Squash_powdery_mildew', 'Strawberry_healthy',
    'Strawberry_leaf_scorch', 'Tomato_bacterial_spot', 'Tomato_early_blight',
    'Tomato_healthy', 'Tomato_late_blight', 'Tomato_leaf_mold',
    'Tomato_septoria_leaf_spot', 'Tomato_spider_mites_two-spotted_spider_mite',
    'Tomato_target_spot', 'Tomato_mosaic_virus', 'Tomato_yellow_leaf_curl_virus',
]

def _load_model():
    preprocess_input = keras.applications.mobilenet_v2.preprocess_input
    base = keras.applications.MobileNetV2(
        input_shape=(224, 224, 3), include_top=False, weights='imagenet'
    )
    base.trainable = False
    m = models.Sequential([
        layers.Input(shape=(224, 224, 3)),
        layers.Lambda(preprocess_input),
        base,
        layers.GlobalAveragePooling2D(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.3),
        layers.Dense(len(CLASSES), activation='softmax'),
    ])
    if MODEL_PATH.exists():
        m.load_weights(str(MODEL_PATH))
        log.info("Model weights loaded from %s", MODEL_PATH)
    else:
        log.warning("Model weights not found at %s — image diagnosis disabled.", MODEL_PATH)
    return m

# ---------------------------------------------------------------------------
# App startup
# ---------------------------------------------------------------------------
try:
    _init_db()
    _create_pool()
except Exception:
    log.exception("Failed to initialise database. Check DB_USER/DB_PASSWORD in .env")

MODEL = _load_model()
OLLAMA_CLIENT = ollama.Client(host="http://127.0.0.1:11434", timeout=OLLAMA_TIMEOUT)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Farmer Query Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # open for local file:// frontend; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt   = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"sha256${salt}${digest}"

def verify_password(password: str, stored: str) -> bool:
    if not stored.startswith("sha256$"):
        return False
    parts = stored.split("$", 2)
    if len(parts) != 3:
        return False
    _, salt, digest = parts
    check = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return secrets.compare_digest(check, digest)

# ---------------------------------------------------------------------------
# Weather helper
# ---------------------------------------------------------------------------
def get_weather_context(lat: Optional[float], lon: Optional[float]) -> str:
    if lat is None or lon is None:
        return "Weather context unavailable."
    try:
        params = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        })
        url = f"https://api.open-meteo.com/v1/forecast?{params}"
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        c = data.get("current", {})
        return (
            f"Temperature {c.get('temperature_2m')}°C, "
            f"humidity {c.get('relative_humidity_2m')}%, "
            f"precipitation {c.get('precipitation')} mm, "
            f"wind {c.get('wind_speed_10m')} km/h."
        )
    except Exception:
        log.warning("Weather fetch failed.", exc_info=True)
        return "Weather context unavailable."

# ---------------------------------------------------------------------------
# Fallback advice (when Ollama is unreachable)
# ---------------------------------------------------------------------------
def build_fallback_advice(query: str, policy_hits: list, weather: str, language: str) -> str:
    policy_text = "; ".join(f"{p['title']}: {p['content']}" for p in policy_hits[:2]) or "No direct policy match."
    base = (
        f"Advisory for your query: {query}. "
        f"Relevant schemes: {policy_text}. "
        f"Weather: {weather}. "
        "For paddy in summer prefer controlled irrigation (drip/sprinkler where feasible), "
        "avoid excess urea, and follow Soil Health Card recommendations."
    )
    if language == "hi":
        return (
            "त्वरित सलाह: संतुलित सिंचाई अपनाएं, अत्यधिक यूरिया से बचें, "
            "Soil Health Card की सिफारिशें मानें। "
            f"मौसम: {weather}"
        )
    if language == "pa":
        return (
            "ਤੁਰੰਤ ਸਲਾਹ: ਸੰਤੁਲਿਤ ਸਿੰਚਾਈ ਕਰੋ, ਵਾਧੂ ਯੂਰੀਆ ਤੋਂ ਬਚੋ, "
            "Soil Health Card ਦੀ ਸਿਫ਼ਾਰਸ਼ ਮੰਨੋ। "
            f"ਮੌਸਮ: {weather}"
        )
    return base

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

class SignupRequest(BaseModel):
    username: str
    password: str

class FeedbackRequest(BaseModel):
    name:     str
    mobile:   str
    category: str
    rating:   int
    feedback: str

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/signup")
async def signup(request: SignupRequest):
    username = request.username.strip()
    password = request.password.strip()
    if len(username) < 3:
        raise HTTPException(400, "Username must be at least 3 characters.")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    db  = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            raise HTTPException(409, "Username already exists.")
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, hash_password(password)),
        )
        db.commit()
        log.info("New user registered: %s", username)
        return {"success": True, "message": "Account created successfully."}
    finally:
        cur.close()
        db.close()

@app.post("/login")
async def login(request: LoginRequest):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, username, password FROM users WHERE username=%s",
            (request.username.strip(),),
        )
        user = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(401, "Invalid username or password.")

    log.info("User logged in: %s", user["username"])
    return {"success": True, "message": "Login successful.", "user_id": user["id"]}

# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------
@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    if not 1 <= request.rating <= 5:
        raise HTTPException(400, "Rating must be between 1 and 5.")
    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO feedback (name, mobile, category, rating, feedback) "
            "VALUES (%s, %s, %s, %s, %s)",
            (request.name, request.mobile, request.category, request.rating, request.feedback),
        )
        db.commit()
        log.info("Feedback received from %s (rating=%d)", request.name, request.rating)
        return {"success": True, "message": "Thank you for your feedback!"}
    finally:
        cur.close()
        db.close()

# ---------------------------------------------------------------------------
# Main advisory endpoint
# ---------------------------------------------------------------------------
@app.post("/ask")
async def ask_farmer_bot(
    request: Request,
    user_id:           Optional[int]   = Form(None),
    query:             Optional[str]   = Form(None),
    file:              UploadFile      = File(None),
    language:          str             = Form("en"),
    crop_type:         Optional[str]   = Form(None),
    season:            Optional[str]   = Form(None),
    land_size:         Optional[str]   = Form(None),
    irrigation_type:   Optional[str]   = Form(None),
    groundwater_stress: Optional[bool] = Form(None),
    msp_dependency:    Optional[bool]  = Form(None),
    latitude:          Optional[float] = Form(None),
    longitude:         Optional[float] = Form(None),
):
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    try:
        diagnosis  = ""
        user_input = (query or "").strip() or "Provide general agricultural advice."

        # --- Image diagnosis ---
        if file and file.filename:
            content_type = file.content_type or ""
            if content_type not in ALLOWED_TYPES:
                raise HTTPException(400, f"Unsupported file type '{content_type}'. Upload JPEG, PNG, or WebP.")
            img_bytes = await file.read()
            if len(img_bytes) > MAX_FILE_BYTES:
                raise HTTPException(400, "Image must be smaller than 5 MB.")
            try:
                img       = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((224, 224))
                img_array = np.expand_dims(np.array(img, dtype="float32"), axis=0)
                preds     = MODEL.predict(img_array, verbose=0)
                diagnosis = CLASSES[int(np.argmax(preds))]
                user_input = f"The plant is diagnosed with {diagnosis}. {user_input}"
                log.info("Image diagnosed: %s", diagnosis)
            except HTTPException:
                raise
            except Exception:
                log.exception("Image inference failed.")
                raise HTTPException(500, "Could not process the uploaded image.")

        # --- Context assembly ---
        policy_hits = retrieve_policy_context(user_input)
        policy_block = "\n".join(
            f"- {p['title']}: {p['content']} (Source: {p['source']})" for p in policy_hits
        ) or "- No direct policy match found."

        weather = get_weather_context(latitude, longitude)
        profile = (
            f"crop_type={crop_type or 'unknown'}, season={season or 'unknown'}, "
            f"land_size={land_size or 'unknown'}, irrigation={irrigation_type or 'unknown'}, "
            f"groundwater_stress={groundwater_stress}, msp_dependency={msp_dependency}"
        )

        language = (language or "en").lower()
        lang_instruction = {
            "hi": (
                "CRITICAL: You MUST write your ENTIRE response in Hindi using ONLY Devanagari script. "
                "Every word must be in Devanagari letters (e.g. यह, के, लिए, मिट्टी, फसल, सिंचाई). "
                "Do NOT use Roman/English letters for any Hindi word. Do NOT transliterate. "
                "ध्यान दें: पूरा उत्तर केवल देवनागरी लिपि में लिखें।"
            ),
            "pa": (
                "CRITICAL: You MUST write your ENTIRE response in Punjabi using ONLY Gurmukhi script. "
                "Every word must be in Gurmukhi letters (e.g. ਇਹ, ਦੇ, ਲਈ, ਮਿੱਟੀ, ਫ਼ਸਲ, ਸਿੰਚਾਈ). "
                "Do NOT use Roman/English letters for any Punjabi word. Do NOT transliterate. "
                "ਧਿਆਨ ਦਿਓ: ਪੂਰਾ ਜਵਾਬ ਕੇਵਲ ਗੁਰਮੁਖੀ ਲਿਪੀ ਵਿੱਚ ਲਿਖੋ।"
            ),
        }.get(language, "Respond in simple English only.")

        # --- LLM call ---
        try:
            llm_response = OLLAMA_CLIENT.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"{lang_instruction}\n\n"
                            "You are a professional agronomist advising Punjab farmers. "
                            "Use the Punjab policy context and weather data when relevant. "
                            "Give concise, practical steps in under 150 words. "
                            "Do not mix languages or scripts in a single response."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Farmer query: {user_input}\n"
                            f"Farmer profile: {profile}\n"
                            f"Weather: {weather}\n"
                            f"Punjab policy snippets:\n{policy_block}"
                        ),
                    },
                ],
            )
            # ollama>=0.2 returns a ChatResponse object, not a plain dict
            ai_msg = llm_response.message.content
            log.info("Ollama response received (%d chars).", len(ai_msg))
        except Exception:
            log.warning("Ollama unavailable — using fallback advice.", exc_info=True)
            ai_msg = build_fallback_advice(user_input, policy_hits, weather, language)

        # --- Persist to chat history (non-fatal) ---
        try:
            db  = get_db()
            cur = db.cursor()
            try:
                cur.execute(
                    "INSERT INTO chat_history (user_id, user_query, ai_response) VALUES (%s, %s, %s)",
                    (user_id, query or f"[Image scan: {diagnosis}]", ai_msg),
                )
                db.commit()
            finally:
                cur.close()
                db.close()
        except Exception:
            log.warning("Failed to persist chat history.", exc_info=True)

        return {
            "response":  ai_msg,
            "detected":  diagnosis if (file and file.filename) else None,
            "language":  language,
            "weather":   weather,
            "policies":  [{"title": p["title"], "source": p["source"]} for p in policy_hits],
        }

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Unhandled error in /ask")
        raise HTTPException(500, str(e))
