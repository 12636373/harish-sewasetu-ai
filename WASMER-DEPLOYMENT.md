# Wasmer Edge Web Hosting & Deployment Guide

> **Sewa Setu — Agent-Ready Welfare Service**  
> **Platform Target:** Wasmer Edge (`https://wasmer.io/new?intent=web-hosting`)

---

## 1. Overview

This document guides you through deploying the **Sewa Setu Portal & Dual MCP Servers** to **Wasmer Edge** using Wasmer's web-hosting platform at [`https://wasmer.io/new?intent=web-hosting`](https://wasmer.io/new?intent=web-hosting).

The repository includes native Wasmer Edge configuration files:
* [`wasmer.toml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/wasmer.toml): Package manifest and WebAssembly/WASI runtime definition.
* [`app.yaml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/app.yaml): Wasmer Edge application configuration, routing, and environment parameters.

---

## 2. Deployment Methods on Wasmer

### Method A: Web Interface Upload / GitHub Import (Recommended)

1. Open **[`https://wasmer.io/new?intent=web-hosting`](https://wasmer.io/new?intent=web-hosting)** in your browser.
2. Sign in to your Wasmer account (or sign up via GitHub).
3. **Choose Deployment Source:**
   * **Option 1 (GitHub Import):** Select **"Import Git Repository"** and choose your private repository `sewasetu-assistant`.
   * **Option 2 (Direct ZIP Upload):** Select **"Upload Archive"** and drag-and-drop the pre-packaged archive:  
     `C:\Users\haris\OneDrive\Desktop\CODE\sewasetu-assistant.zip` (26.35 MB, full `.git` history preserved).
4. **Configure Environment Variables:**
   Under **Settings $\rightarrow$ Environment Variables**, configure:
   ```env
   PUBLIC_BASE_URL=https://<your-app-name>.wasmer.app
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=<generate_a_secure_password>
   SECRET_KEY=<generate_random_hex_secret>
   POSTGRES_HOST=<your_cloud_postgres_host>
   POSTGRES_PORT=5432
   POSTGRES_DB=sewasetu
   POSTGRES_USER=sewasetu
   POSTGRES_PASSWORD=<your_db_password>
   ```
5. Click **"Deploy Application"**.
6. Wasmer Edge will package the project and issue a live public HTTPS URL:
   `https://<your-app-name>.wasmer.app`

---

### Method B: Deploying via Wasmer CLI

If you have the Wasmer CLI installed on your machine:

```bash
# 1. Install Wasmer CLI (if not already installed)
# On Linux/macOS:
curl https://get.wasmer.io -sSfL | sh

# On Windows (PowerShell):
iwr -useb https://get.wasmer.io | iex

# 2. Authenticate CLI with your Wasmer account
wasmer login

# 3. Deploy from the repository root
cd sewasetu-ai-handout
wasmer deploy
```

The CLI reads [`wasmer.toml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/wasmer.toml) and [`app.yaml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/app.yaml), bundles the package, and provisions the edge deployment.

---

## 3. Database Architecture & Persistence on Edge

In public welfare systems, transactional integrity and relational constraints are paramount:
* **The Application Layer (Gunicorn, Flask, dual MCP servers):** Runs globally at the edge on Wasmer Edge, serving static assets, AI tool calls, and web requests with ultra-low latency.
* **The PostgreSQL Database (100,000+ seeded records):**
  * When deploying to Wasmer Edge, point `POSTGRES_HOST` to a managed cloud PostgreSQL instance (such as **Neon Serverless Postgres**, **Supabase**, **Aiven**, or an **AWS RDS / EC2 PostgreSQL instance**).
  * Load [`seed/seed.sql`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/seed/seed.sql) into your database once:
    ```bash
    psql -h <cloud_db_host> -U sewasetu -d sewasetu -f app/schema.sql
    psql -h <cloud_db_host> -U sewasetu -d sewasetu -f seed/seed.sql
    ```
* **Alternatively (All-in-One Cloud VPS):**
  If you prefer running the entire 4-container stack (PostgreSQL + Gunicorn + Caddy + Cron Scheduler) on a single self-contained server with zero external dependencies, use the automated `./deploy.sh` script on any cloud VM (AWS EC2, DigitalOcean, Hetzner) as described in [`DEPLOYMENT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DEPLOYMENT.md).

---

## 4. Post-Deployment Verification on Wasmer Edge

Once live on `https://<your-app-name>.wasmer.app`, verify all endpoints:

1. **Portal Web UI:**  
   `https://<your-app-name>.wasmer.app/`
2. **Citizen MCP Endpoint:**  
   `https://<your-app-name>.wasmer.app/mcp/citizen`
3. **Officer MCP Endpoint:**  
   `https://<your-app-name>.wasmer.app/mcp/officer`
4. **RFC 9728 Protected Resource Discovery:**  
   `https://<your-app-name>.wasmer.app/.well-known/oauth-protected-resource`
5. **RFC 8414 Authorization Server Discovery:**  
   `https://<your-app-name>.wasmer.app/.well-known/oauth-authorization-server`
6. **Evaluation Dashboard:**  
   `https://<your-app-name>.wasmer.app/eval-dashboard`
7. **Operational Health Check:**  
   `https://<your-app-name>.wasmer.app/health`

Run the independent verification suite against the Wasmer URL:
```bash
python verify_mcp_independent.py --base-url https://<your-app-name>.wasmer.app
```
Expected result: **100% PASSED (8/8 Checks Succeeded)**.
