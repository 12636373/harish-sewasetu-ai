# Wasmer Edge Web Hosting & Deployment Guide

> **Sewa Setu — Agent-Ready Welfare Service**  
> **Platform Target:** Wasmer Edge (`https://wasmer.io/new?intent=web-hosting`)

---

## 1. Overview

This document guides you through deploying the **Sewa Setu Portal & Dual MCP Servers** to **Wasmer Edge** using Wasmer's web-hosting platform at [`https://wasmer.io/new?intent=web-hosting`](https://wasmer.io/new?intent=web-hosting).

The repository includes native Wasmer Edge configuration files:
* [`wasmer.toml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/wasmer.toml): Package manifest and WebAssembly/WASI runtime definition.
* [`app.yaml`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/app.yaml): Wasmer Edge application configuration, routing, and environment parameters.
* [`main.py`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/main.py): Root entrypoint dynamically binding to `$PORT` (default 8080).
* [`wsgi.py`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/wsgi.py): Standard WSGI application object for Wasmer Edge and Anybuild.
* [`requirements.txt`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/requirements.txt): Root package manifest for build-time dependency resolution.

---

## 2. Troubleshooting Wasmer Edge "Error 500: Application Error"

If you encounter the Wasmer Edge screen displaying:
```
Error 500
500 Internal Server Error - An unknown error occurred.
[Your browser: Working] -> [Wasmer Edge: Working] -> [Application: Error]
```

### Why this happens:
1. **Missing Root Entrypoint:** Wasmer Edge expects `main.py`, `wsgi.py`, or `requirements.txt` at the repository root.
2. **Gunicorn Incompatibility with WASI:** Gunicorn relies on UNIX `os.fork()` and signals, which are not supported in WebAssembly/WASI runtimes.
3. **Database Connection Lockup:** If the application tries to connect to a PostgreSQL database that is either unconfigured or unreachable from the edge network, the startup process times out or crashes.

### How it is fixed in this release:
1. **Root `main.py` & `wsgi.py`:** Directly launches the Flask server on `0.0.0.0:$PORT` without process forking.
2. **Standard `wasmer/python` Dependency:** `wasmer.toml` uses official `"wasmer/python" = ">=3.12"` with WASI command `script`.
3. **Transparent Database Fallback (`app/db_compat.py`):**
   * If `POSTGRES_HOST`, `DATABASE_URL`, or Wasmer Managed Postgres (`DB_HOST`) is reachable, it uses PostgreSQL.
   * If PostgreSQL is not configured, offline, or running in an edge sandbox, it automatically uses an integrated SQLite database initialized with the full schema and seeded records. The app never crashes with a 500 error!

---

## 3. Step-by-Step Deployment on Wasmer

### Method A: Web Interface Upload / GitHub Import (Recommended)

1. Open **[`https://wasmer.io/new?intent=web-hosting`](https://wasmer.io/new?intent=web-hosting)** in your browser.
2. Sign in to your Wasmer account (or sign up via GitHub).
3. **Choose Deployment Source:**
   * **Option 1 (GitHub Import):** Select **"Import Git Repository"** and choose your private repository `sewasetu-assistant`.
   * **Option 2 (Direct ZIP Upload):** Select **"Upload Archive"** and drag-and-drop the pre-packaged archive:  
     `C:\Users\haris\OneDrive\Desktop\CODE\sewasetu-assistant.zip` (contains all fixes, root entrypoints, and full `.git` history).
4. **Configure Environment Variables:**
   Under **Settings $\rightarrow$ Environment Variables**, configure:
   ```env
   PUBLIC_BASE_URL=https://<your-app-name>.wasmer.app
   PORT=8080
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=PurvanchalGov2026!Secure
   SECRET_KEY=b4a92c3d1e0f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b
   USE_SQLITE=1
   ```
   *(If connecting to an external cloud PostgreSQL like Neon, Supabase, or AWS RDS, set `USE_SQLITE=0` and add `POSTGRES_HOST`, `POSTGRES_PASSWORD`, etc.)*
5. Click **"Deploy Application"**.
6. Wasmer Edge packages the project and boots the server at:
   `https://<your-app-name>.wasmer.app`

---

## 4. Post-Deployment Verification on Wasmer Edge

Once live on `https://<your-app-name>.wasmer.app`, verify all endpoints:

1. **Portal Web UI:**  
   `https://<your-app-name>.wasmer.app/`
2. **Evaluation Dashboard:**  
   `https://<your-app-name>.wasmer.app/eval-dashboard`
3. **Citizen MCP Endpoint:**  
   `https://<your-app-name>.wasmer.app/mcp/citizen`
4. **Officer MCP Endpoint:**  
   `https://<your-app-name>.wasmer.app/mcp/officer`
5. **RFC 9728 Protected Resource Discovery:**  
   `https://<your-app-name>.wasmer.app/.well-known/oauth-protected-resource`
6. **RFC 8414 Authorization Server Discovery:**  
   `https://<your-app-name>.wasmer.app/.well-known/oauth-authorization-server`
7. **Operational Health Check:**  
   `https://<your-app-name>.wasmer.app/health`
