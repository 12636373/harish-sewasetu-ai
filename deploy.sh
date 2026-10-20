#!/usr/bin/env bash
# ==============================================================================
# Sewa Setu — Production Deployment Script (Linux / macOS)
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "  Sewa Setu — Old Age Pension Portal & MCP Deployment"
echo "  Department of Social Welfare, Government of Purvanchal"
echo "=========================================================="

# 1. Check Docker & Docker Compose
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: 'docker compose' (v2) is required."
    exit 1
fi

# 2. Setup .env file
if [ ! -f .env ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
    
    # Generate secure random admin password & secret key
    RANDOM_PASS=$(openssl rand -hex 10 2>/dev/null || head /dev/urandom | tr -dc A-Za-z0-9 | head -c 16)
    RANDOM_SECRET=$(openssl rand -hex 32 2>/dev/null || head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32)
    sed -i "s/ADMIN_PASSWORD=change-me-to-a-secure-password/ADMIN_PASSWORD=${RANDOM_PASS}/" .env
    sed -i "s/SECRET_KEY=generate_random_secret_key_here/SECRET_KEY=${RANDOM_SECRET}/" .env
    echo "[*] Generated secure credentials in .env"
fi

# Source .env for reporting
set -a
# shellcheck disable=SC1091
source .env
set +a

# 3. Build & Launch Containers
echo "[*] Building container images..."
docker compose build

echo "[*] Starting production stack in background..."
docker compose up -d

# 4. Wait for Health Check
echo "[*] Waiting for services to become healthy..."
MAX_ATTEMPTS=30
ATTEMPT=0
HEALTH_URL="http://127.0.0.1:8000/health"

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[+] Portal and services are healthy!"
        break
    fi
    echo "    Waiting for DB initialization and app startup (Attempt $ATTEMPT/$MAX_ATTEMPTS)..."
    sleep 3
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "[-] Warning: Health check did not return 200 within timeout."
    echo "    Check logs with: docker compose logs -f"
    exit 1
fi

# 5. Print Deployment Summary
BASE=${PUBLIC_BASE_URL:-http://localhost:8000}
echo ""
echo "=========================================================="
echo "  DEPLOYMENT SUCCESSFUL"
echo "=========================================================="
echo "  Portal URL:               $BASE"
echo "  Officer Login (Admin):    $BASE/admin"
echo "  Username:                 $ADMIN_USERNAME"
echo "  Password:                 $ADMIN_PASSWORD"
echo "  Eval Dashboard:           $BASE/eval-dashboard"
echo "  Citizen MCP Endpoint:     $BASE/mcp/citizen"
echo "  Officer MCP Endpoint:     $BASE/mcp/officer"
echo "  Resource Metadata:        $BASE/.well-known/oauth-protected-resource"
echo "  Authorization Server:     $BASE/.well-known/oauth-authorization-server"
echo "  Health Check:             $BASE/health"
echo "=========================================================="
echo "To view live logs:           docker compose logs -f"
echo "To restart stack:            docker compose restart"
echo "To stop stack:               docker compose down"
echo "=========================================================="
