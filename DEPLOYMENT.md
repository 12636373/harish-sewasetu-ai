# Sewa Setu — Production Deployment & Operations Guide

> **Department of Social Welfare, Government of Purvanchal**  
> *Build for Bharat Fellowship — Agent-Ready Welfare Service*

This document provides complete instructions for deploying, securing, and maintaining the Sewa Setu portal, its dual Model Context Protocol (MCP) servers, and the live evaluation framework in a production cloud environment.

---

## 1. Architecture Overview

```
                      Internet / Citizens / Agents / Evaluators
                                         │
                         ┌───────────────┴───────────────┐
                         │   Port 80 / 443 (HTTPS)       │
                         │   (Optional Caddy Proxy)      │
                         └───────────────┬───────────────┘
                                         │
                                   Port 8000
                                         │
                ┌────────────────────────┴────────────────────────┐
                │             Gunicorn App Container              │
                │  - Citizen Portal UI & API                      │
                │  - Block Officer Admin Dashboard                │
                │  - OAuth 2.1 RFC 8414 Authorization Server      │
                │  - RFC 9728 Protected Resource Metadata         │
                │  - Citizen MCP Server (/mcp/citizen)            │
                │  - Officer MCP Server (/mcp/officer)            │
                │  - Evaluation Dashboard (/eval-dashboard)       │
                │  - Operational Health Check (/health)           │
                └───────────────┬─────────────────┬───────────────┘
                                │                 │
        ┌───────────────────────┴──────┐   ┌──────┴──────────────────────┐
        │     PostgreSQL 15 Container  │   │  SMS Gateway (Port 8025)    │
        │  - 100,000+ Seed Records     │   │  - Simulated Telecom        │
        │  - Full Audit Trail          │   │  - OTP & Status Deliveries  │
        │  - Statutory RTPS State      │   └─────────────────────────────┘
        └───────────────┬──────────────┘
                        │
        ┌───────────────┴──────────────┐
        │      Scheduler Container     │
        │  - 15-day Deemed Approval    │
        │  - Nightly Cron Job (02:00)  │
        └──────────────────────────────┘
```

---

## 2. Server Requirements

- **Operating System:** Ubuntu 22.04 LTS / Debian 12 / AlmaLinux 9 / any Linux VM
- **Memory:** Minimum 2 GB RAM (4 GB recommended for handling the 100k application seed dataset efficiently)
- **Disk:** 10 GB free disk space
- **Software:** Docker Engine 24+ and Docker Compose v2+

---

## 3. Quick Start (Single Command Deployment)

On your server or local terminal, execute:

```bash
# Clone the private repository
git clone https://github.com/<your-username>/sewasetu-assistant.git
cd sewasetu-assistant

# Run the automated deployment script
chmod +x deploy.sh
./deploy.sh
```

The script will automatically:
1. Create a production `.env` from `.env.example` with cryptographically strong admin passwords and session secrets.
2. Build the Docker container images.
3. Start the PostgreSQL database, SMS gateway, Gunicorn application, and RTPS scheduler.
4. Wait for database readiness and verify the `/health` endpoint.
5. Print all active endpoint URLs and admin credentials.

---

## 4. Cloud Deployment (Step-by-Step for AWS / DigitalOcean / Hetzner / GCP)

### Step 4.1: Provision VM & Firewall Rules
Ensure inbound traffic is allowed on:
- **Port 22:** SSH Management
- **Port 80:** HTTP (Web / Let's Encrypt challenge)
- **Port 443:** HTTPS (Production SSL)
- **Port 8000:** Direct Application Port (if not using Caddy SSL reverse proxy)

### Step 4.2: Configure `.env`
Copy the example configuration:
```bash
cp .env.example .env
```

Open `.env` in your editor and configure:
```ini
# Public URL stamped into OAuth tokens, JWKS, and RFC 9728 discovery
PUBLIC_BASE_URL=https://sewasetu.yourdomain.com

# Departmental Officer Login Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=A_VERY_SECURE_PASSWORD_HERE

# Flask Session Security Key
SECRET_KEY=94b7f8c2e6481023a8bc76543210feac1948576201a3b4c5d6e7f8a9b0c1d2e3

# PostgreSQL Database Credentials
POSTGRES_DB=sewasetu
POSTGRES_USER=sewasetu
POSTGRES_PASSWORD=strong_db_password_here

# Automatic SSL Domain & Email (if deploying with Caddy)
DOMAIN_NAME=sewasetu.yourdomain.com
ACME_EMAIL=your-email@example.com
```

### Step 4.3: Deploying with Automatic HTTPS (Recommended)
We include a production Caddy container configuration (`docker-compose.prod.yml` and `Caddyfile`) that automatically obtains and renews zero-configuration Let's Encrypt SSL certificates:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Your service is now live on `https://sewasetu.yourdomain.com` with valid TLS certificates!

### Step 4.4: Deploying without a Domain (IP Address on Port 8000)
If deploying directly on a public server IP (e.g. `http://54.210.12.34:8000`):
1. In `.env`, set `PUBLIC_BASE_URL=http://54.210.12.34:8000`
2. Start the stack:
   ```bash
   docker compose up -d --build
   ```

---

## 5. Verification & Health Monitoring

### 5.1 Operational Health Check
Verify the stack status:
```bash
curl -i http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "total_applications": 100000
  },
  "sms_gateway": {
    "connected": true
  },
  "scheme": {
    "window_open": true,
    "deadline": "2026-12-31 23:59:00"
  },
  "timestamp": "2026-10-20T22:25:00.123456+05:30"
}
```

### 5.2 Live Evaluation Dashboard
Visit `/eval-dashboard` in your browser or run the test suite programmatically:
```bash
curl -X POST http://localhost:8000/api/evals/run
```
All 7 live database invariant personas will be evaluated, returning a 100% pass rate.

### 5.3 MCP Endpoints
- Citizen MCP: `http://localhost:8000/mcp/citizen`
- Officer MCP: `http://localhost:8000/mcp/officer`
- OAuth Protected Resource Metadata: `http://localhost:8000/.well-known/oauth-protected-resource`
- OAuth Authorization Server Metadata: `http://localhost:8000/.well-known/oauth-authorization-server`

---

## 6. Real Client Connectivity (Claude Code)

To connect Claude Code or an agentic assistant to Sewa Setu:

### For Citizens:
Add to your Claude Code MCP configuration (`mcpServers` in configuration or via CLI):
```bash
claude mcp add sewasetu-citizen --transport http https://sewasetu.yourdomain.com/mcp/citizen
```
*Note: Include your citizen Bearer token in the request header or authenticate via OAuth 2.1 PKCE authorization code flow.*

### For Block Officers:
```bash
claude mcp add sewasetu-officer --transport http https://sewasetu.yourdomain.com/mcp/officer
```
*Note: Block officers use program tokens generated at `/admin/tokens` or bearer tokens issued during departmental sign-in.*

---

## 7. Operations & Maintenance

| Operation | Command |
| :--- | :--- |
| **View Live Logs** | `docker compose logs -f app` |
| **View Database Logs** | `docker compose logs -f db` |
| **View Scheduler Logs** | `docker compose logs -f scheduler` |
| **Restart Stack** | `docker compose restart` |
| **Update Code & Rebuild** | `git pull && docker compose up -d --build` |
| **Trigger Deemed Approvals Manually** | `docker compose exec scheduler python /app/scripts/deemed_approval.py` |
| **Backup PostgreSQL DB** | `docker compose exec db pg_dump -U sewasetu sewasetu > backup.sql` |
| **Stop Stack** | `docker compose down` |
