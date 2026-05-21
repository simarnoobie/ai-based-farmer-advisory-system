#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# ec2-setup.sh  –  Bootstrap an Amazon Linux 2023 EC2 instance for this project
#
# Run once on a fresh instance:
#   chmod +x ec2-setup.sh && sudo ./ec2-setup.sh
#
# What it does:
#   1. Installs Docker + Docker Compose plugin
#   2. Adds the ec2-user to the docker group (no sudo needed after re-login)
#   3. Copies the project from GitHub (or you can scp it yourself)
#   4. Creates the project-root .env from environment variables you set below
#   5. Pulls & starts all containers in detached mode
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── EDIT THESE BEFORE RUNNING ─────────────────────────────────────────────────
REPO_URL="https://github.com/simarnoobie/ai-based-farmer-advisory-system.git"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-CHANGE_ME}"
JWT_SECRET="${JWT_SECRET:-CHANGE_ME}"
GROQ_API_KEY="${GROQ_API_KEY:-}"        # leave blank to use Ollama (local only)
GROQ_MODEL="${GROQ_MODEL:-llama3-8b-8192}"
S3_BUCKET="${S3_BUCKET:-}"              # leave blank if not using S3 for model
S3_MODEL_KEY="${S3_MODEL_KEY:-models/trained_farmer_model.h5}"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> 1/5  Updating system packages"
dnf update -y -q

echo "==> 2/5  Installing Docker"
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

echo "==> 3/5  Installing Docker Compose plugin"
COMPOSE_VERSION="v2.27.0"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "==> 4/5  Cloning repository"
APP_DIR="/home/ec2-user/farmer-ai"
if [ -d "$APP_DIR" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R ec2-user:ec2-user "$APP_DIR"

echo "==> 5/5  Writing .env and starting containers"
cat > "$APP_DIR/.env" <<EOF
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
JWT_SECRET=${JWT_SECRET}
GROQ_API_KEY=${GROQ_API_KEY}
GROQ_MODEL=${GROQ_MODEL}
S3_BUCKET=${S3_BUCKET}
S3_MODEL_KEY=${S3_MODEL_KEY}
# Backend URL exposed to the browser — set to your EC2 public IP or domain
BACKEND_URL=http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000
# Allow requests from anywhere in dev; tighten in production
ALLOWED_ORIGINS=*
EOF

cd "$APP_DIR"
docker compose pull --quiet
docker compose up -d --build

echo ""
echo "✅  All containers are up."
echo "   Frontend : http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "   Backend  : http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo ""
echo "NOTE: Log out and log back in for the docker group to take effect (so you"
echo "      can run 'docker ...' without sudo as ec2-user)."
