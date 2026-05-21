# 📋 AI-Based Farmer Advisory System - Detailed Project Breakdown

## 🎯 Project Overview

This is a **full-stack AI-powered web application** that helps farmers with:
1. **Plant Disease Detection** - Upload leaf images to identify diseases
2. **AI-Powered Agricultural Advice** - Get expert farming guidance via chat
3. **Voice & Speech Interaction** - Speak questions and hear recommendations in English, Hindi, or Punjabi
4. **Weather-Aware Local Advice** - Use the farmer’s location to fetch live weather updates for precise recommendations
5. **Policy-Aware RAG Guidance** - Use Punjab agricultural policy knowledge to enrich answers with relevant schemes and government support
6. **Query History** - Track all interactions in a database

---

## 📁 Project Structure & File-by-File Breakdown

### 🗂️ **Backend/** - Python FastAPI Server

#### **`Backend/main.py`** (145 lines) - Main API Server
**Purpose:** FastAPI backend that handles all server-side logic

**Key Components:**

1. **Imports & Setup (Lines 1-24)**
   - TensorFlow/Keras for ML model
   - FastAPI for REST API
   - MySQL connector for database
   - Ollama for AI chat
   - CORS middleware for frontend communication

2. **Disease Classes (Lines 26-40)**
   - Defines 38 plant disease categories:
     - Apple diseases (scab, black rot, rust, healthy)
     - Corn diseases (gray leaf spot, common rust, northern leaf blight)
     - Tomato diseases (bacterial spot, early/late blight, mosaic virus, etc.)
     - Grape, Peach, Pepper, Potato, and other crop diseases
     - Healthy plant classifications

3. **Model Loading Function (Lines 42-63)**
   ```python
   def load_farmer_model():
       # Uses MobileNetV2 as base (pre-trained on ImageNet)
       # Adds custom layers for 38-class classification
       # Loads trained weights from 'models/trained_farmer_model.h5'
   ```
   - **Architecture:**
     - Input: 224x224x3 images
     - Base: MobileNetV2 (transfer learning)
     - Global Average Pooling
     - Dense layer (128 neurons, ReLU)
     - Dropout (0.3)
     - Output: 38 classes (softmax)

4. **Database Connection (Lines 67-73)**
   - Connects to MySQL database `farmer_ai`
   - Default: localhost, root user, no password

5. **API Endpoints:**
   
   **`POST /login` (Lines 79-100)**
   - Authenticates users
   - Validates username/password from `users` table
   - Returns user_id on success

   **`POST /ask` (Lines 102-145)**
   - Main query endpoint
   - Accepts: `user_id`, `query` (text), `file` (image)
   - **Image Processing Flow:**
     1. Resize image to 224x224
     2. Convert to numpy array
     3. Run through MobileNetV2 model
     4. Get disease prediction
   - **AI Chat Flow:**
     1. If image uploaded: Prepends diagnosis to query
     2. Assembles context from farmer profile, location-based weather, and Punjab policy knowledge
     3. Sends the combined query to Ollama (Gemma 3:1b model)
     4. Handles English, Hindi, and Punjabi responses with language-constrained output
   - **Weather & Location:**
     - Uses browser geolocation to fetch live weather data for the farmer’s coordinates
     - Embeds current temperature, humidity, precipitation, and wind in the advisory context
   - **Policy-Aware RAG:**
     - Retrieves Punjab policy snippets from `Backend/punjab_policy_knowledge.py`
     - Uses these documents to ground AI responses in government schemes and agrarian programs
   - **Database:**
     - Saves query and response to `chat_history` table

#### **`Backend/models/trained_farmer_model.h5`** (35,237 lines)
- **Pre-trained TensorFlow/Keras model weights**
- Contains the trained MobileNetV2 model for disease detection
- Size: ~9-10 MB (compressed weights)
- **Accuracy:** 95.5% on test set (from notebook)

#### **`Backend/models/trained_farmer_model.keras`**
- Alternative Keras format of the same model

#### **`Backend/requirements.txt`**
```
fastapi              # Web framework
uvicorn              # ASGI server
mysql-connector-python  # MySQL database driver
ollama               # Ollama AI client library
tensorflow>=2.15.0   # Deep learning framework
pillow               # Image processing
numpy                # Numerical operations
python-multipart     # File upload handling
pydantic             # Data validation
```

---

### 🗂️ **Frontend/** - Web Interface

#### **`Frontend/login_page/login.html`** - Login Page
- Split-screen design
- Left: Marketing content ("Smart Farming Starts Here")
- Right: Login form with username/password fields
- Calls `login.js` for authentication

#### **`Frontend/login_page/login.js`** (28 lines)
- **Function:** `loginUser()`
- Sends POST request to `http://127.0.0.1:8000/login`
- Stores `user_id` in localStorage
- Redirects to `query.html` on success

#### **`Frontend/login_page/login.css`**
- Styling for login page
- Modern UI with gradients and animations

---

#### **`Frontend/ai_query/query.html`** - Main Chat Interface
- Chat container for messages
- Input area with:
  - Text input for questions
  - "Ask AI" button
  - "Upload Leaf img" button (hidden file input)
- Displays AI avatar and messages

#### **`Frontend/ai_query/query.js`** (87 lines)
**Key Functions:**

1. **`appendMessage(sender, text, isLoader)`**
   - Adds messages to chat UI
   - Supports user/AI messages
   - Shows loading animation

2. **`sendMessage(file)`**
   - Main function for sending queries
   - Gets `user_id` from localStorage
   - Creates FormData with:
     - `user_id`
     - `query` (optional text)
     - `file` (optional image)
     - `language` selection for English, Hindi, or Punjabi
     - farmer profile metadata (crop, season, land size, irrigation, groundwater stress, MSP dependency)
     - geolocation coordinates for weather-aware advice
   - POSTs to `http://127.0.0.1:8000/ask`
   - Displays response with disease diagnosis if image uploaded
   - Uses browser speech synthesis to speak the AI response when enabled

3. **Event Listeners:**
   - File input change → auto-sends image
   - Enter key → sends text query
   - Microphone button → triggers voice input
   - Location button → captures current coordinates for weather context

#### **`Frontend/ai_query/query.css`**
- Chat interface styling
- Message bubbles (user/AI)
- Background image (farm.png)
- Responsive design

---

#### **`Frontend/feedback_form/feedback_form.html`**
- Form for farmer feedback
- Fields: Name, Mobile, Farming Type, Rating (1-5), Feedback text
- Currently not connected to backend (no JS implementation)

#### **`Frontend/feedback_form/feedback_form.js`**
- Empty file (not implemented)

---

#### **`Frontend/assets/`**
- `avatar.png` - AI assistant avatar
- `farm.png` - Background image for UI

---

### 🗂️ **Notebook/** - Model Training

#### **`Notebook/Farmer_Advisory_System_MobileNetV2.ipynb`** - Training Notebook

**Complete Training Pipeline:**

**Cell 0:** Imports
- matplotlib, numpy, tensorflow

**Cell 1:** Dataset Download
```python
!wget -O "dataset.zip" "https://data.mendeley.com/public-files/datasets/tywbtsjrjv/files/..."
```
- Downloads **905 MB** dataset from Mendeley
- Plant leaf diseases dataset with augmentation

**Cell 2:** Extract Dataset
```python
!unzip /content/dataset.zip
```
- Extracts to `Plant_leave_diseases_dataset_with_augmentation/`
- Contains 39 classes (38 diseases + background)

**Cell 3:** Split Dataset
```python
splitfolders.ratio(..., ratio=(.8, .1, .1))
```
- **80% Training** (49,179 images)
- **10% Validation** (6,139 images)
- **10% Test** (6,168 images)
- Total: **61,486 images**

**Cell 4:** Configuration
```python
BATCH_SIZE = 32
IMG_SIZE = (224, 224)
EPOCHS = 5
```

**Cell 5:** Load Datasets
- Uses `tf.keras.utils.image_dataset_from_directory`
- Auto-detects 39 classes from folder structure

**Cell 6:** Get Class Names
- Extracts class names from dataset

**Cell 7:** Performance Optimization
- `prefetch(buffer_size=AUTOTUNE)` for faster training

**Cell 8:** Preprocessing
- MobileNetV2 preprocessing function

**Cell 9:** Base Model
```python
base_model = tf.keras.applications.MobileNetV2(
    input_shape=(224, 224, 3),
    include_top=False,
    weights='imagenet'
)
base_model.trainable = False  # Transfer learning
```
- Uses **pre-trained MobileNetV2** (ImageNet weights)
- Freezes base layers (transfer learning)

**Cell 11:** Build Model
```python
model = Sequential([
    Input(224, 224, 3),
    Lambda(preprocess_input),
    base_model,                    # MobileNetV2
    GlobalAveragePooling2D(),
    Dense(128, activation='relu'),
    Dropout(0.3),
    Dense(39, activation='softmax')  # 39 classes
])
```

**Cell 13:** Training
```python
model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)
history = model.fit(train_dataset, validation_data=val_dataset, epochs=5)
```

**Training Results:**
- **Epoch 1:** 73% train acc, 93.76% val acc
- **Epoch 2:** 92.12% train acc, 94.93% val acc
- **Epoch 3:** 93.58% train acc, 95.70% val acc
- **Epoch 4:** 94.31% train acc, 95.86% val acc
- **Epoch 5:** 95.21% train acc, 95.67% val acc
- **Final Test Accuracy: 95.54%**

**Cell 15:** Save Model
```python
model.save("trained_farmer_model.keras")
```

---

## 🤖 AI Models Used

### 1. **MobileNetV2 (Plant Disease Detection)**
- **Type:** Convolutional Neural Network (CNN)
- **Architecture:** Transfer Learning
- **Base Model:** MobileNetV2 (pre-trained on ImageNet)
- **Input:** 224x224x3 RGB images
- **Output:** 38 disease classes + healthy states
- **Accuracy:** 95.54% on test set
- **Purpose:** Classify plant leaf images to detect diseases
- **Location:** `Backend/models/trained_farmer_model.h5`

**Model Architecture:**
```
Input (224x224x3)
    ↓
MobileNetV2 Preprocessing
    ↓
MobileNetV2 Base (frozen, ImageNet weights)
    ↓
Global Average Pooling 2D
    ↓
Dense(128, ReLU)
    ↓
Dropout(0.3)
    ↓
Dense(38, Softmax) → Disease Classification
```

### 2. **Gemma 3:1b (Agricultural Advice)**
- **Type:** Large Language Model (LLM)
- **Provider:** Ollama (local LLM)
- **Model:** `gemma3:1b` (1 billion parameters)
- **Purpose:** Generate agricultural advice based on queries
- **System Prompt:** "You are a professional agronomist. Keep advice under 120 words."
- **Integration:** Via Ollama Python client
- **Location:** Runs locally via Ollama service

---

## 📊 Training Dataset

### **Source:** Mendeley Data Repository
- **URL:** `https://data.mendeley.com/public-files/datasets/tywbtsjrjv/files/...`
- **Size:** 905 MB (compressed)
- **Format:** ZIP file containing organized folders

### **Dataset Structure:**
```
Plant_leave_diseases_dataset_with_augmentation/
├── Apple___Apple_scab/
├── Apple___Apple_black_rot/
├── Apple___Apple_cedar_apple_rust/
├── Apple___healthy/
├── Background_without_leaves/
├── Blueberry___healthy/
├── Cherry___powdery_mildew/
├── Cherry___healthy/
├── Corn___gray_leaf_spot/
├── Corn___common_rust/
├── Corn___northern_leaf_blight/
├── Corn___healthy/
├── Grape___black_rot/
├── Grape___black_measles/
├── Grape___leaf_blight/
├── Grape___healthy/
├── Orange___haunglongbing/
├── Peach___bacterial_spot/
├── Peach___healthy/
├── Pepper___bacterial_spot/
├── Pepper___healthy/
├── Potato___early_blight/
├── Potato___healthy/
├── Potato___late_blight/
├── Raspberry___healthy/
├── Soybean___healthy/
├── Squash___powdery_mildew/
├── Strawberry___healthy/
├── Strawberry___leaf_scorch/
├── Tomato___bacterial_spot/
├── Tomato___early_blight/
├── Tomato___healthy/
├── Tomato___late_blight/
├── Tomato___leaf_mold/
├── Tomato___septoria_leaf_spot/
├── Tomato___spider_mites_two-spotted_spider_mite/
├── Tomato___target_spot/
├── Tomato___mosaic_virus/
└── Tomato___yellow_leaf_curl_virus/
```

### **Dataset Statistics:**
- **Total Images:** 61,486
- **Classes:** 39 (38 diseases + background)
- **Training Set:** 49,179 images (80%)
- **Validation Set:** 6,139 images (10%)
- **Test Set:** 6,168 images (10%)
- **Augmentation:** Dataset already includes augmented images

### **Data Augmentation:**
- The dataset comes pre-augmented (rotations, flips, brightness variations)
- This helps improve model generalization

---

## 🛠️ Technology Stack

### **Backend Technologies:**

1. **FastAPI** (Python)
   - Modern, fast web framework
   - Automatic API documentation
   - Async support
   - Type hints

2. **TensorFlow/Keras** (v2.15.0+)
   - Deep learning framework
   - Model loading and inference
   - MobileNetV2 implementation

3. **Ollama**
   - Local LLM runner
   - Runs Gemma 3:1b model
   - Python client library

4. **MySQL** (via mysql-connector-python)
   - Relational database
   - Stores users and chat history

5. **Pillow (PIL)**
   - Image processing
   - Resize and format conversion

6. **NumPy**
   - Numerical operations
   - Array manipulation for images

7. **Uvicorn**
   - ASGI server
   - Runs FastAPI application

### **Frontend Technologies:**

1. **HTML5**
   - Structure and content

2. **CSS3**
   - Styling and layout
   - Responsive design
   - Animations

3. **Vanilla JavaScript**
   - DOM manipulation
   - Fetch API for HTTP requests
   - LocalStorage for session management

### **Machine Learning Technologies:**

1. **Transfer Learning**
   - MobileNetV2 pre-trained on ImageNet
   - Fine-tuned for plant diseases

2. **Deep Learning**
   - Convolutional Neural Networks
   - Global Average Pooling
   - Dropout regularization

3. **Data Preprocessing**
   - Image resizing (224x224)
   - Normalization
   - MobileNetV2 preprocessing

---

## 🔄 System Architecture & Data Flow

### **1. User Login Flow:**
```
User enters credentials
    ↓
Frontend (login.js) → POST /login
    ↓
Backend (main.py) → MySQL query
    ↓
Validate user → Return user_id
    ↓
Store user_id in localStorage
    ↓
Redirect to query.html
```

### **2. Text Query Flow:**
```
User types question
    ↓
Frontend (query.js) → POST /ask (with query text)
    ↓
Backend receives query
    ↓
Send to Ollama (Gemma 3:1b)
    ↓
Get AI response
    ↓
Save to MySQL (chat_history)
    ↓
Return response to frontend
    ↓
Display in chat UI
```

### **3. Image Upload + Query Flow:**
```
User uploads leaf image
    ↓
Frontend (query.js) → POST /ask (with image file)
    ↓
Backend receives image
    ↓
Preprocess: Resize to 224x224
    ↓
Run through MobileNetV2 model
    ↓
Get disease prediction (e.g., "Tomato_early_blight")
    ↓
Combine diagnosis with user query
    ↓
Send to Ollama for advice
    ↓
Get AI response with treatment suggestions
    ↓
Save to MySQL
    ↓
Return response + diagnosis to frontend
    ↓
Display diagnosis + advice in chat
```

---

## 🗄️ Database Schema

### **MySQL Database: `farmer_ai`**

#### **Table: `users`**
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL
);
```

#### **Table: `chat_history`**
```sql
CREATE TABLE chat_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    user_query TEXT,
    ai_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 📝 API Endpoints

### **Base URL:** `http://127.0.0.1:8000`

### **1. POST `/login`**
**Request Body:**
```json
{
    "username": "farmer1",
    "password": "password123"
}
```

**Response (Success):**
```json
{
    "success": true,
    "message": "Login successful",
    "user_id": 1
}
```

**Response (Error):**
```json
{
    "detail": "Invalid username or password"
}
```

### **2. POST `/ask`**
**Request (FormData):**
- `user_id`: int (required)
- `query`: string (optional)
- `file`: image file (optional)

**Response:**
```json
{
    "response": "AI advice text here...",
    "detected": "Tomato_early_blight"  // null if no image
}
```

---

## 🚀 How the System Works

### **Step 1: Model Training (Already Done)**
- Trained MobileNetV2 on 61,486 plant images
- Achieved 95.54% accuracy
- Saved model to `Backend/models/trained_farmer_model.h5`

### **Step 2: Backend Setup**
- FastAPI server loads the trained model
- Connects to MySQL database
- Sets up Ollama integration

### **Step 3: User Interaction**
1. **Login:** User authenticates
2. **Query:** User asks question OR uploads image
3. **Processing:**
   - If image: Disease detection via MobileNetV2
   - Query sent to Ollama for AI advice
4. **Response:** Combined diagnosis + advice shown to user
5. **Storage:** All interactions saved to database

---

## 📈 Model Performance

### **Training Metrics:**
- **Final Training Accuracy:** 95.21%
- **Final Validation Accuracy:** 95.67%
- **Test Accuracy:** 95.54%
- **Loss:** 0.0877 (test set)

### **Model Characteristics:**
- **Lightweight:** MobileNetV2 is optimized for mobile/edge devices
- **Fast Inference:** ~50-100ms per image
- **Robust:** Handles various lighting and angles (thanks to augmentation)

---

## 🔧 Configuration Details

### **Backend Configuration:**
- **Host:** localhost
- **Port:** 8000 (default FastAPI)
- **Database:** MySQL on localhost
- **Model Path:** `Backend/models/trained_farmer_model.h5`
- **Ollama Model:** `gemma3:1b`

### **Frontend Configuration:**
- **API Endpoint:** `http://127.0.0.1:8000`
- **Session Storage:** localStorage (`farmer_user_id`)

---

## 📦 Dependencies Summary

### **Python Packages:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `tensorflow>=2.15.0` - ML framework
- `keras` - High-level ML API
- `mysql-connector-python` - Database driver
- `ollama` - LLM client
- `pillow` - Image processing
- `numpy` - Numerical computing
- `pydantic` - Data validation
- `python-multipart` - File uploads

### **External Services:**
- **MySQL** - Database server (local)
- **Ollama** - LLM runtime (local)
- **Mendeley Data** - Dataset source (external)

---

## 🎓 Academic Context

- **Course:** B.Tech Computer Science Engineering (3rd Year)
- **Domain:** Artificial Intelligence & Agriculture
- **Focus:** Human-Centered AI for smart farming
- **Project Type:** Full-stack AI application

---

## 🔍 Key Features Implementation

1. **Disease Detection:**
   - Real-time image classification
   - 38 disease categories
   - High accuracy (95.54%)

2. **AI Chat:**
   - Context-aware responses
   - Agricultural expertise
   - Concise advice (under 120 words)

3. **User Management:**
   - Secure login
   - Session management
   - Query history tracking

4. **User Interface:**
   - Modern, responsive design
   - Chat-based interaction
   - Image upload support

---

## 📌 Important Notes

1. **Model File:** The trained model (`trained_farmer_model.h5`) must be present in `Backend/models/`
2. **Ollama Setup:** Must have Ollama installed and `gemma3:1b` model pulled
3. **Database:** MySQL must be running with `farmer_ai` database created
4. **CORS:** Backend allows all origins (`allow_origins=["*"]`) - adjust for production
5. **Security:** Passwords stored in plain text - should be hashed in production

---

## 🎯 Summary

This project combines:
- **Computer Vision** (MobileNetV2 for disease detection)
- **Natural Language Processing** (Gemma LLM for advice)
- **Web Development** (FastAPI + HTML/CSS/JS)
- **Database Management** (MySQL)

All working together to create an intelligent farming assistant that helps farmers identify plant diseases and get expert agricultural advice!

