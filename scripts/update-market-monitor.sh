#!/usr/bin/env bash
set -euo pipefail

# Synchronize the local market_monitor_docker folder to the remote Pi
# and restart the service via docker compose. Adjust REMOTE_HOST or
# TARGET_DIR via environment variables if needed.

REMOTE_HOST="gilko@10.1.1.85"
TARGET_DIR="${TARGET_DIR:-/opt/market_monitor}"
TARGET_OWNER="${TARGET_OWNER:-gilko:gilko}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$PROJECT_ROOT/market_monitor_docker"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "market_monitor_docker directory not found at $SOURCE_DIR" >&2
  exit 1
fi

echo "[1/4] Ensuring remote directory exists..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" \
  "sudo mkdir -p '$TARGET_DIR' && sudo chown -R '$TARGET_OWNER' '$TARGET_DIR'"

echo "[2/4] Synchronizing project files to $REMOTE_HOST:$TARGET_DIR ..."
rsync -avz \
  --exclude '.git/' \
  --exclude '.DS_Store' \
  --exclude '__pycache__/' \
  --exclude 'app/data/dashboard.json' \
  "$SOURCE_DIR/" "$REMOTE_HOST:$TARGET_DIR/"

echo "[3/4] Rebuilding and restarting container..."
ssh "$REMOTE_HOST" "cd '$TARGET_DIR' && docker compose up -d --build"

echo "[4/4] Checking container status..."
ssh "$REMOTE_HOST" "cd '$TARGET_DIR' && docker compose ps"

echo "Market monitor web updated and restarted successfully."
