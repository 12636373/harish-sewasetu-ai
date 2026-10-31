# Sewa Setu: Cloud & VM Production Deployment Guide
**Public Tech Challenge: "Sewa Setu, agent-ready"**
*Department of Social Welfare, Government of Purvanchal*

---

## 1. Quick Start Production Deployment (Docker Compose)

### Prerequisites
- Linux VM (Ubuntu 22.04 LTS / Debian 12 / RHEL 9) or Docker Desktop.
- 2 GB RAM minimum, 10 GB disk space.
- Inbound ports: `80` (HTTP), `443` (HTTPS/optional), `8000` (Portal & MCP), `8025` (SMS Gateway console).

### Step-by-Step Deployment

1. **Clone the private repository:**
   ```bash
   git clone https://github.com/12636373/harish-sewasetu-ai.git sewasetu-assistant
   cd sewasetu-assistant
   ```

2. **Configure production environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   - Set `PUBLIC_BASE_URL` to your VM's public domain or IP (e.g. `http://198.51.100.24:8000`).
   - Set a strong `SECRET_KEY` (generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`).
   - Set a secure `ADMIN_PASSWORD`.

3. **Start the production stack:**
   ```bash
   docker compose up --build -d
   ```

4. **Verify container health:**
   ```bash
   docker compose ps
   curl -s http://localhost:8000/health | jq .
   ```

5. **Run automated MCP verification suite:**
   ```bash
   docker compose exec web python verify_mcp_independent.py
   ```

---

## 2. Service Endpoints Directory

| Service | Internal Port | Host / Public URL | Description |
| :--- | :--- | :--- | :--- |
| **Citizen Portal** | 8000 | `http://<VM-IP>:8000/` | Public welfare application portal |
| **Citizen MCP** | 8000 | `http://<VM-IP>:8000/mcp/citizen` | Streamable HTTP endpoint (10 citizen tools) |
| **Officer MCP** | 8000 | `http://<VM-IP>:8000/mcp/officer` | Streamable HTTP endpoint (10 officer tools) |
| **Eval Dashboard**| 8000 | `http://<VM-IP>:8000/eval-dashboard` | 12-persona live database evaluation evidence |
| **Admin Portal** | 8000 | `http://<VM-IP>:8000/admin` | Departmental officer adjudication portal |
| **SMS Gateway** | 8025 | `http://<VM-IP>:8025/` | PurvSMS simulated telecom console |
| **Health Check** | 8000 | `http://<VM-IP>:8000/health` | Service, database, and SMS health monitor |

---

## 3. Maintenance, Restart & Disaster Recovery Runbooks

### Service Restarts
```bash
# Restart entire stack
docker compose restart

# Restart only web application without database downtime
docker compose restart web
```

### Database Backup & Restore
```bash
# Snapshot PostgreSQL database
docker compose exec db pg_dump -U sewasetu sewasetu > backup_$(date +%Y%m%d).sql

# Restore from snapshot
cat backup_YYYYMMDD.sql | docker compose exec -T db psql -U sewasetu sewasetu
```

### Nightly RTPS Deemed Approval Cron
The scheduled container runs automatically at `02:00 IST` daily:
```bash
# Trigger manual RTPS deemed approval scan
docker compose exec web python /app/scripts/deemed_approval.py
```
