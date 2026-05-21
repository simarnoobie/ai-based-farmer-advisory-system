# ── Stage 1: dependency install (cached layer) ─────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# Install system deps needed to build some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt


# ── Stage 2: final runtime image ───────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source (exclude venv, cache, model, logs via .dockerignore)
COPY . .

# Create models directory — model weights are either mounted or pulled from S3
RUN mkdir -p models

EXPOSE 8000

# Run as non-root for basic container hardening
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
