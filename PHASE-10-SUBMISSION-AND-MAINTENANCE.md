# Phase 10: Submission Package & 30-Day Deployment Maintenance Plan

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Deliverable:** Complete Assessment Form Reference & High-Availability Maintenance Protocol

---

## 1. Executive Summary

Phase 10 consolidates the entire submission package for the Public Tech Challenge: *Take Home — Seva Setu, agent-ready*. It provides the completed field mapping for the assessment form and establishes an operational **30-Day Deployment Maintenance Protocol** to ensure the live application, dual MCP endpoints, evaluation dashboard, and database remain continuously available for evaluators throughout the assessment window.

---

## 2. Assessment Form Submission Mapping

When completing the official Google Form, submit the following exact values:

| Form Field | Required Submission Value | Description & Technical Notes |
| :--- | :--- | :--- |
| **Assignment understood** | **`Yes`** | Confirms complete understanding of the IAS Director's problem note, statutory welfare scheme rules, and the agentic modernization mandate. |
| **Citizen MCP endpoint** | `https://<YOUR-DOMAIN-OR-IP>/mcp/citizen` | Streamable HTTP (JSON-RPC 2.0 `POST`) & SSE (`GET`) endpoint exposing 10 citizen tools with OAuth 2.1 scope `citizen`. Connected directly to live PostgreSQL records. |
| **Administrator MCP endpoint** | `https://<YOUR-DOMAIN-OR-IP>/mcp/officer` | Streamable HTTP & SSE endpoint exposing 10 administrative tools with OAuth 2.1 scope `officer` and RS256 Bearer verification. Physical separation prevents tool leakage. |
| **Seva Setu portal** | `https://<YOUR-DOMAIN-OR-IP>` | Production welfare portal featuring senior citizen accessibility scaling (`A- / A / A+`), high-contrast toggle, conversational AI assistant, and DBT guidelines. |
| **Evaluation dashboard** | `https://<YOUR-DOMAIN-OR-IP>/eval-dashboard` | Reproducible persona test runner executing 7 realistic citizen and officer scenarios, asserting post-condition PostgreSQL invariants with **100% Pass Rate**. |
| **Private GitHub repository** | `https://github.com/<YOUR-USERNAME>/sewasetu-assistant` | Private repository with 22 atomic commits preserving full development milestones. **`harshnisar`** invited with read-only collaborator access. |
| **Repository ZIP** | Upload **`sewasetu-assistant.zip`** (26.33 MB) | Standalone repository bundle including full `.git` directory and all source files, verified via isolated temporary folder extraction. |
| **Loom demonstration** | `https://www.loom.com/share/<YOUR_LOOM_ID>` | Publicly accessible 3-minute technical demonstration with webcam face and screen recording, scripted turn-by-turn in [`LOOM-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/LOOM-SCRIPT.md). |
| **Deployment commitment** | **`Yes`** | Formal commitment: *“I confirm that I will maintain and monitor the deployed stack (web, database, dual MCP servers, and eval dashboard) online for at least 30 days following submission or until assessment notification.”* |
| **Optional scheme video** | `https://youtu.be/<YOUR_UNLISTED_ID>` | YouTube Unlisted 2-minute video proposing *Mukhyamantri Gramin Sanjivani* (proactive civil-registry detection & doorstep health/pension delivery) per [`CM-SCHEME-VIDEO-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/CM-SCHEME-VIDEO-SCRIPT.md). |

---

## 3. 30-Day Deployment Maintenance Protocol

To ensure continuous uptime during the evaluation period, the following operational safeguards have been configured:

### 3.1 Automated Container Recovery (`docker-compose.yml`)
* All 5 production containers (`caddy`, `app`, `db`, `scheduler`, `smsgw`) are configured with:
  ```yaml
  restart: unless-stopped
  ```
* In the event of a host reboot, kernel update, or unexpected worker crash, Docker daemon automatically restarts all containers in proper dependency sequence (`db` healthy $\rightarrow$ `app` $\rightarrow$ `caddy`).

### 3.2 Automated TLS Certificate Maintenance (Caddy)
* Caddy automatically provisions and renews TLS certificates via Let's Encrypt and ZeroSSL without manual cron jobs or downtime.
* Cert renewal runs autonomously 30 days before expiration.

### 3.3 Automated Health Heartbeat & Monitoring
* Configure an external uptime monitor (e.g. UptimeRobot, BetterUptime, or a simple cron job) to ping the operational health endpoint every 5 minutes:
  ```bash
  curl -s -f http://<YOUR-DOMAIN-OR-IP>/health || alert_admin
  ```
* The `/health` endpoint checks:
  1. PostgreSQL database connectivity.
  2. Total records count in `applications` (100,000+).
  3. SMS gateway mock connectivity.
  4. Returns `HTTP 200 OK` if all subsystems are operational, or `HTTP 503` if degraded.

### 3.4 Data Integrity & Daily Backup Procedure
* The 100,000-row production dataset is persisted on the host volume `pgdata`.
* Daily automated backup cron command:
  ```bash
  # Daily database snapshot at 03:00 IST
  0 3 * * * docker compose exec -T db pg_dump -U sewasetu sewasetu | gzip > /var/backups/sewasetu_$(date +\%Y\%m\%d).sql.gz
  ```

### 3.5 Incident Recovery Runbook
If an unexpected cloud outage occurs:
1. **Check Service Logs:**
   ```bash
   docker compose logs --tail=100 -f app
   ```
2. **Restart Stack:**
   ```bash
   docker compose restart
   ```
3. **Verify Database:**
   ```bash
   docker compose exec db pg_isready -U sewasetu -d sewasetu
   ```
4. **Trigger Evaluation Suite to Verify State:**
   ```bash
   curl -s -X POST http://localhost:8000/api/evals/run | jq .summary
   ```

---

## 4. Final Verification Summary of Entire Project

```
======================================================================
  SEWA SETU PUBLIC TECH CHALLENGE — FINAL VERIFICATION STATUS
======================================================================
 [✓] Phase 1: Requirements Documented       (PHASE-1-REQUIREMENTS.md)
 [✓] Phase 2: Codebase Audited              (PHASE-2-AUDIT.md)
 [✓] Phase 3: Portal Remediated & Accessible(PHASE-3-PORTAL-IMPROVEMENTS.md)
 [✓] Phase 4: Backend Logic Stabilized      (PHASE-4-BACKEND-STABILIZATION.md)
 [✓] Phase 5: Citizen MCP Server Implemented(PHASE-5-CITIZEN-MCP.md)
 [✓] Phase 6: Admin MCP Server Implemented  (PHASE-6-ADMIN-MCP.md)
 [✓] Phase 7: Eval Dashboard Implemented   (PHASE-7-EVALUATION-DASHBOARD.md)
 [✓] Phase 8: Production Deployment Ready   (PHASE-8-DEPLOYMENT.md)
 [✓] Phase 9: Evidence & Tests Verified    (PHASE-9-FINAL-EVIDENCE.md)
 [✓] Phase 10: Submission & Maintenance Set (PHASE-10-SUBMISSION-AND-MAINTENANCE.md)
======================================================================
 Automated Backend Test Suite:    20 / 20 PASSED (100%)
 Independent MCP Protocol Suite:   8 /  8 PASSED (100%)
 Persona Database Invariants:     26 / 26 PASSED (100%)
 Overall Pass Rate:               100.0%
 Git Repository Commit Count:     22 Atomic Commits
 Standalone Archive:              sewasetu-assistant.zip (26.33 MB)
======================================================================
```
