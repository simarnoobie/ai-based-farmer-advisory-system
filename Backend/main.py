import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import io
import json
import logging
import time
import urllib.parse
import urllib.request
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models  # type: ignore
import mysql.connector
from mysql.connector import pooling
import ollama
from fastapi import Depends, FastAPI, Header, UploadFile, File, Form, HTTPException, Request
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

JWT_SECRET       = os.environ.get("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM    = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
_origins_raw     = os.environ.get("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS  = [o.strip() for o in _origins_raw.split(",")]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
S3_BUCKET    = os.environ.get("S3_BUCKET", "")
S3_MODEL_KEY = os.environ.get("S3_MODEL_KEY", "models/trained_farmer_model.h5")
REDIS_URL    = os.environ.get("REDIS_URL", "")

MODEL_PATH     = Path(__file__).parent / "models" / "trained_farmer_model.h5"
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_TYPES  = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# ---------------------------------------------------------------------------
# Rate limiting — Redis-backed when available, in-memory fallback
# ---------------------------------------------------------------------------
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_RPM = 15

_redis_client = None
if REDIS_URL:
    try:
        import redis as _redis_lib
        _redis_client = _redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        log.info("Redis connected — using Redis rate limiting.")
    except Exception:
        log.warning("Redis unavailable — falling back to in-memory rate limiting.")
        _redis_client = None

def _check_rate_limit(ip: str) -> bool:
    if _redis_client:
        key = f"rl:{ip}"
        pipe = _redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        count, _ = pipe.execute()
        return int(count) <= RATE_LIMIT_RPM
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

def _ensure_model_weights() -> None:
    if MODEL_PATH.exists():
        return
    if not S3_BUCKET:
        log.warning("Model weights not found locally and S3_BUCKET is not configured.")
        return
    try:
        import boto3
        log.info("Downloading model from s3://%s/%s ...", S3_BUCKET, S3_MODEL_KEY)
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        boto3.client("s3").download_file(S3_BUCKET, S3_MODEL_KEY, str(MODEL_PATH))
        log.info("Model downloaded from S3 successfully.")
    except Exception:
        log.exception("S3 model download failed — image diagnosis may be unavailable.")

def _load_model():
    _ensure_model_weights()
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

_groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq as _GroqClient
        _groq_client = _GroqClient(api_key=GROQ_API_KEY)
        log.info("Groq client initialized (model: %s).", GROQ_MODEL)
    except ImportError:
        log.warning("groq package not installed; Ollama will be used.")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AI Farmer Query Support")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AI Farmer Query Support"}

# ---------------------------------------------------------------------------
# Password helpers (bcrypt)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored.encode())
    except Exception:
        return False

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": username,
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[int]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = decode_token(authorization.split(" ", 1)[1])
        return payload.get("user_id")
    except Exception:
        return None

async def require_user(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required.")
    try:
        payload = decode_token(authorization.split(" ", 1)[1])
        uid = payload.get("user_id")
        if uid is None:
            raise HTTPException(401, "Invalid token.")
        return uid
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired. Please log in again.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token.")

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
    scheme_names = ", ".join(p["title"] for p in policy_hits[:2]) if policy_hits else None
    scheme_note  = f"Relevant schemes: {scheme_names}. " if scheme_names else ""
    weather_note = f"Current weather: {weather} " if "unavailable" not in weather else ""
    if language == "hi":
        return (
            f"आपके सवाल के लिए सलाह: {scheme_note}{weather_note}\n"
            "संतुलित सिंचाई अपनाएं, अत्यधिक यूरिया से बचें और Soil Health Card की सिफारिशें मानें। "
            "अपने स्थानीय कृषि विशेषज्ञ से भी संपर्क करें।"
        )
    if language == "pa":
        return (
            f"ਤੁਹਾਡੇ ਸਵਾਲ ਦੀ ਸਲਾਹ: {scheme_note}{weather_note}\n"
            "ਸੰਤੁਲਿਤ ਸਿੰਚਾਈ ਕਰੋ, ਵਾਧੂ ਯੂਰੀਆ ਤੋਂ ਬਚੋ ਅਤੇ Soil Health Card ਦੀ ਸਿਫ਼ਾਰਸ਼ ਮੰਨੋ।"
        )
    return (
        f"{scheme_note}{weather_note}\n"
        "Based on best practices for Punjab farming: use balanced irrigation (drip/sprinkler preferred), "
        "avoid excess urea, follow your Soil Health Card recommendations, and consult your local agronomist "
        "for field-specific advice."
    )

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
    return {
        "success":  True,
        "message":  "Login successful.",
        "user_id":  user["id"],
        "token":    create_token(user["id"], user["username"]),
    }

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
# Chat history endpoint (JWT-protected — users can only see their own history)
# ---------------------------------------------------------------------------
@app.get("/history")
async def get_chat_history(
    limit: int = 20,
    user_id: int = Depends(require_user),
):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT user_query, ai_response, created_at "
            "FROM chat_history WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (user_id, min(limit, 100)),
        )
        rows = cur.fetchall()
        return {"history": rows, "count": len(rows)}
    finally:
        cur.close()
        db.close()

# ---------------------------------------------------------------------------
# Feedback summary endpoint
# ---------------------------------------------------------------------------
@app.get("/feedback/summary")
async def feedback_summary():
    db  = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT COUNT(*) AS total, AVG(rating) AS avg_rating FROM feedback")
        overview = cur.fetchone()
        cur.execute(
            "SELECT rating, COUNT(*) AS count FROM feedback "
            "GROUP BY rating ORDER BY rating"
        )
        distribution = cur.fetchall()
        cur.execute(
            "SELECT category, COUNT(*) AS count, AVG(rating) AS avg_rating "
            "FROM feedback GROUP BY category ORDER BY count DESC"
        )
        by_category = cur.fetchall()
        return {
            "total":          overview["total"],
            "average_rating": round(float(overview["avg_rating"] or 0), 2),
            "distribution":   distribution,
            "by_category":    by_category,
        }
    finally:
        cur.close()
        db.close()

# ---------------------------------------------------------------------------
# Main advisory endpoint
# ---------------------------------------------------------------------------
@app.post("/ask")
async def ask_farmer_bot(
    request: Request,
    user_id:           Optional[int]   = Depends(get_optional_user),
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

    # Greeting shortcut — skip LLM for simple greetings
    _GREETINGS = {"hi", "hello", "hey", "hii", "helo", "howdy", "yo",
                  "namaste", "namaskar", "sat sri akal", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "नमस्ते"}
    _raw_q = (query or "").strip().lower().rstrip("!.,?")
    if _raw_q in _GREETINGS and not (file and file.filename):
        _greet = {
            "hi": "नमस्ते! 🌾 मैं आपका AI कृषि सहायक हूं। आज मैं आपकी क्या मदद कर सकता हूं? फसल रोग, सिंचाई, सरकारी योजनाएं या मौसम आधारित सलाह के बारे में पूछें।",
            "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! 🌾 ਮੈਂ ਤੁਹਾਡਾ AI ਖੇਤੀਬਾੜੀ ਸਹਾਇਕ ਹਾਂ। ਅੱਜ ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?",
        }.get((language or "en").lower(),
              "Hello! 👋 I'm your AI Farming Assistant. How can I help you today? "
              "Ask me about crop diseases, irrigation, government schemes, MSP rates, "
              "or upload a leaf photo for instant disease diagnosis.")
        return {
            "response": _greet, "detected": None, "confidence": None,
            "top3": None, "language": language or "en",
            "weather": None, "policies": [],
        }

    try:
        diagnosis  = ""
        confidence = 0.0
        top3: list = []
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
                preds_arr = MODEL.predict(img_array, verbose=0)[0]
                top_idx   = np.argsort(preds_arr)[::-1][:3]
                diagnosis  = CLASSES[int(top_idx[0])]
                confidence = float(preds_arr[top_idx[0]])
                top3 = [
                    {"class": CLASSES[int(i)], "confidence": round(float(preds_arr[i]), 3)}
                    for i in top_idx
                ]
                user_input = f"The plant is diagnosed with {diagnosis} (confidence: {confidence:.0%}). {user_input}"
                log.info("Image diagnosed: %s (%.0f%%)", diagnosis, confidence * 100)
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
        _messages = [
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
        ]
        try:
            if _groq_client:
                completion = _groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=_messages,
                    max_tokens=300,
                )
                ai_msg = completion.choices[0].message.content
                log.info("Groq response received (%d chars).", len(ai_msg))
            else:
                llm_response = OLLAMA_CLIENT.chat(model=OLLAMA_MODEL, messages=_messages)
                ai_msg = llm_response.message.content
                log.info("Ollama response received (%d chars).", len(ai_msg))
        except Exception:
            log.warning("LLM unavailable — using fallback advice.", exc_info=True)
            ai_msg = build_fallback_advice(user_input, policy_hits, weather, language)

        # --- Persist to chat history (non-fatal) ---
        try:
            db  = get_db()
            cur = db.cursor()
            try:
                # Verify user_id exists locally (JWT may come from a different DB instance)
                safe_uid = None
                if user_id is not None:
                    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                    safe_uid = user_id if cur.fetchone() else None
                cur.execute(
                    "INSERT INTO chat_history (user_id, user_query, ai_response) VALUES (%s, %s, %s)",
                    (safe_uid, query or f"[Image scan: {diagnosis}]", ai_msg),
                )
                db.commit()
            finally:
                cur.close()
                db.close()
        except Exception:
            log.warning("Failed to persist chat history.", exc_info=True)

        has_image = bool(file and file.filename)
        return {
            "response":   ai_msg,
            "detected":   diagnosis   if has_image else None,
            "confidence": round(confidence, 3) if has_image else None,
            "top3":       top3        if has_image else None,
            "language":   language,
            "weather":    weather,
            "policies":   [{"title": p["title"], "source": p["source"]} for p in policy_hits],
        }

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Unhandled error in /ask")
        raise HTTPException(500, str(e))
