#!/usr/bin/env bash
set -euo pipefail

# Synchronize the local market_monitor_docker folder to the remote Pi
# and restart the service via docker compose. Includes AI API key management.

REMOTE_HOST="gilko@10.1.1.85"
TARGET_DIR="${TARGET_DIR:-/opt/market_monitor}"
TARGET_OWNER="${TARGET_OWNER:-gilko:gilko}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$PROJECT_ROOT/market_monitor_docker"
ENV_FILE="$SOURCE_DIR/.env"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() { echo -e "${BLUE}ℹ${NC} $1"; }
echo_success() { echo -e "${GREEN}✓${NC} $1"; }
echo_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
echo_error() { echo -e "${RED}✗${NC} $1"; }

if [ ! -d "$SOURCE_DIR" ]; then
  echo_error "market_monitor_docker directory not found at $SOURCE_DIR"
  exit 1
fi

# Check if .env exists locally
if [ ! -f "$ENV_FILE" ]; then
  echo_warning ".env file not found at $ENV_FILE"
  echo_info "Creating from .env.example..."
  if [ -f "$SOURCE_DIR/.env.example" ]; then
    cp "$SOURCE_DIR/.env.example" "$ENV_FILE"
    echo_warning "Please edit $ENV_FILE and add your API keys before proceeding."
    exit 1
  else
    echo_error ".env.example not found. Cannot create .env file."
    exit 1
  fi
fi

# Validate AI configuration
echo_info "Validating AI configuration..."
source "$ENV_FILE"

if [ -z "${AI_PROVIDER:-}" ]; then
  echo_warning "AI_PROVIDER not set in .env, defaulting to 'openai'"
  AI_PROVIDER="openai"
fi

case "$AI_PROVIDER" in
  openai)
    if [ -z "${OPENAI_API_KEY:-}" ]; then
      echo_error "OPENAI_API_KEY not set in .env but AI_PROVIDER=openai"
      echo_info "Please add your OpenAI API key to $ENV_FILE"
      exit 1
    fi
    echo_success "OpenAI API key configured"
    ;;
  anthropic)
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
      echo_error "ANTHROPIC_API_KEY not set in .env but AI_PROVIDER=anthropic"
      echo_info "Please add your Anthropic API key to $ENV_FILE"
      exit 1
    fi
    echo_success "Anthropic API key configured"
    ;;
  none)
    echo_warning "AI analysis disabled (AI_PROVIDER=none)"
    ;;
  *)
    echo_error "Invalid AI_PROVIDER: $AI_PROVIDER (must be: openai, anthropic, or none)"
    exit 1
    ;;
esac

echo ""
echo_info "[1/5] Ensuring remote directory exists..."
ssh -o StrictHostKeyChecking=no "$REMOTE_HOST" \
  "sudo mkdir -p '$TARGET_DIR' && sudo chown -R '$TARGET_OWNER' '$TARGET_DIR'"
echo_success "Remote directory ready"

echo ""
echo_info "[2/5] Backing up remote .env file (if exists)..."
ssh "$REMOTE_HOST" \
  "if [ -f '$TARGET_DIR/.env' ]; then cp '$TARGET_DIR/.env' '$TARGET_DIR/.env.backup'; echo 'Backup created'; else echo 'No existing .env to backup'; fi"

echo ""
echo_info "[3/5] Synchronizing project files to $REMOTE_HOST:$TARGET_DIR..."
rsync -avz --progress \
  --exclude '.git/' \
  --exclude '.DS_Store' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'app/data/dashboard.json' \
  --exclude '.env.backup' \
  "$SOURCE_DIR/" "$REMOTE_HOST:$TARGET_DIR/"
echo_success "Files synchronized"

echo ""
echo_info "[4/5] Rebuilding and restarting container..."
ssh "$REMOTE_HOST" "cd '$TARGET_DIR' && docker compose down && docker compose up -d --build"
echo_success "Container rebuilt and started"

echo ""
echo_info "[5/5] Checking container status..."
ssh "$REMOTE_HOST" "cd '$TARGET_DIR' && docker compose ps && docker compose logs --tail=20"

echo ""
echo_success "Market monitor updated and restarted successfully!"
echo_info "Access dashboard at: http://10.1.1.85:8090"
echo_info "View logs: ssh $REMOTE_HOST 'cd $TARGET_DIR && docker compose logs -f'"
