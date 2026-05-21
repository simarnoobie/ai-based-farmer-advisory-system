# AI-Based Farmer Advisory System

## Overview
The **AI-Based Farmer Advisory System** is a web application designed to provide intelligent support to farmers. It leverages **Artificial Intelligence** to answer queries related to crops, soil, fertilizers, and plant diseases, helping farmers make informed decisions for better yield and crop health.

This system extends human-centered AI with:
- **Voice-enabled interaction** using browser speech recognition and speech synthesis
- **Location-based weather awareness** for precise local advisory
- **Multilingual support** in English, हिंदी, and ਪੰਜਾਬੀ
- **RAG-style policy guidance** using Punjab agricultural scheme knowledge

This system demonstrates the application of **Human-Centered AI** in agriculture, combining AI-powered recommendations with an easy-to-use web interface.

---

## Features
- **AI-Powered Query Assistance:** Provides accurate and context-aware answers to farmers’ questions.  
- **Voice Input & Speech Output:** Farmers can speak questions and hear answers in English, Hindi, or Punjabi.  
- **Local Language Support:** Supports English, हिंदी, and ਪੰਜਾਬੀ across the UI and AI responses.  
- **Weather-Aware Advice:** Uses the user’s location to fetch live weather data and tailor recommendations.  
- **Policy-Aware RAG Advisory:** Enriches responses with Punjab agricultural policy and scheme context.  
- **Crop, Soil & Fertilizer Guidance:** Offers expert advice on crop selection, soil health, and fertilizer usage.  
- **Plant Disease Diagnosis:** Suggests potential treatments and preventive measures for common plant diseases.  
- **Interactive Web Interface:** Easy-to-use frontend for submitting queries, uploading leaf images, and receiving AI responses.  
- **Scalable Architecture:** Built with FastAPI backend, allowing integration with other services or AI models.  

---

## How to Use
- Click the microphone button to ask questions by voice.
- Use the location tool to enable weather-aware, local advisory.
- Select English, हिंदी, or ਪੰਜਾਬੀ for responses.
- Upload a leaf image to receive plant disease diagnosis and treatment suggestions.

---

## Tech Stack
- **Frontend:** HTML, CSS, JavaScript  
- **Backend:** FastAPI (Python)  
- **AI Model:** Llama 3.2 (via Ollama)  
- **Database:** MySQL  
- **Development Tools:** VS Code, Git, GitHub  
- **Platform:** Web Application  

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ai-based-farmer-advisory-system.git
   cd ai-based-farmer-advisory-system
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r Backend/requirements.txt
   ```

3. **Run the FastAPI server:**
   ```bash
   cd Backend
   uvicorn main:app --reload
   ```

4. **Access the frontend:**
   Open `Frontend/ai_query/query.html` in your browser.
---

## Academic Context
- **Course:** B.Tech Computer Science Engineering (3rd Year)

- **Domain:** Artificial Intelligence & Agriculture

- **Project Focus:** Human-Centered AI for smart farming assistance

---
