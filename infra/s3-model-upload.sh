#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# s3-model-upload.sh  –  Upload the trained Keras model weights to S3
#
# Run from your local machine (where the .h5 file lives) ONCE before deploying.
# The backend container downloads this file on startup via _ensure_model_weights().
#
# Prerequisites:
#   - AWS CLI installed and configured (aws configure)
#   - The S3 bucket must already exist
#
# Usage:
#   chmod +x s3-model-upload.sh
#   S3_BUCKET=my-bucket-name ./s3-model-upload.sh
#   # or set S3_BUCKET in your shell and just run: ./s3-model-upload.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── CONFIG ────────────────────────────────────────────────────────────────────
S3_BUCKET="${S3_BUCKET:-}"
S3_MODEL_KEY="${S3_MODEL_KEY:-models/trained_farmer_model.h5}"
LOCAL_MODEL_PATH="${LOCAL_MODEL_PATH:-Backend/models/trained_farmer_model.h5}"
# ─────────────────────────────────────────────────────────────────────────────

if [ -z "$S3_BUCKET" ]; then
  echo "ERROR: S3_BUCKET is not set."
  echo "  Export it first:  export S3_BUCKET=your-bucket-name"
  exit 1
fi

if [ ! -f "$LOCAL_MODEL_PATH" ]; then
  echo "ERROR: Model file not found at: $LOCAL_MODEL_PATH"
  echo "  Set LOCAL_MODEL_PATH to the correct path and retry."
  exit 1
fi

echo "==> Uploading model weights to S3"
echo "    Source : $LOCAL_MODEL_PATH"
echo "    Dest   : s3://${S3_BUCKET}/${S3_MODEL_KEY}"

aws s3 cp "$LOCAL_MODEL_PATH" "s3://${S3_BUCKET}/${S3_MODEL_KEY}" \
  --storage-class STANDARD_IA

echo ""
echo "✅  Upload complete."
echo ""
echo "Add these to your .env (or GitHub Secrets for CI/CD):"
echo "    S3_BUCKET=${S3_BUCKET}"
echo "    S3_MODEL_KEY=${S3_MODEL_KEY}"
echo ""
echo "The backend container will download the model on startup automatically."
