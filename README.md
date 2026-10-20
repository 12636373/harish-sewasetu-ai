# Sewa Setu — Agent-Ready Old Age Pension Portal

> **Department of Social Welfare, Government of Purvanchal**  
> *Build for Bharat Fellowship — AI Track*

Sewa Setu is the official Old Age Pension Portal for the Government of Purvanchal, re-imagined for an agentic world. It delivers a modern, accessible web portal for citizens and departmental officers alongside **two strictly segregated Model Context Protocol (MCP) servers** over streamable HTTP, RFC 9728 Protected Resource discovery, and a live persona-driven evaluation framework.

---

## 1. Quick Start & Local Run

To launch the full production stack (Gunicorn web app, PostgreSQL 15 with 100k records, SMS gateway, and RTPS nightly scheduler):

```bash
# On Linux / macOS:
./deploy.sh

# On Windows:
.\deploy.ps1

# Or directly with Docker Compose:
docker compose up -d --build
```

### Key Endpoints
- **Public Portal:** [http://localhost:8000](http://localhost:8000)
- **Citizen Status Portal:** [http://localhost:8000/status](http://localhost:8000/status) *(Mobile + DoB in DDMMYYYY)*
- **Departmental Officer Login:** [http://localhost:8000/admin](http://localhost:8000/admin) *(User `admin`, Password from `.env` or `ADMIN_PASSWORD`)*
- **Evaluation Dashboard:** [http://localhost:8000/eval-dashboard](http://localhost:8000/eval-dashboard)
- **Citizen MCP Server:** [http://localhost:8000/mcp/citizen](http://localhost:8000/mcp/citizen)
- **Officer MCP Server:** [http://localhost:8000/mcp/officer](http://localhost:8000/mcp/officer)
- **Operational Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
- **SMS Gateway Console:** [http://localhost:8000/__gateway/](http://localhost:8000/__gateway/)

---

## 2. Architecture & Design Highlights

### Physical MCP Separation
- **Citizen Endpoint (`/mcp/citizen`):** Exposes applicant-scoped tools (`get_scheme_information`, `check_eligibility`, `get_my_application_status`, `submit_application`, `withdraw_application`, `download_acknowledgment`). An applicant's assistant **never sees officer tools**.
- **Block Officer Endpoint (`/mcp/officer`):** Exposes departmental administrative tools (`get_officer_dashboard`, `list_pending_applications`, `get_application_details`, `approve_application`, `reject_application`, `search_applications`).
- **Strict Role-Based Authorization:** Validates RS256 Bearer tokens against the portal's JWKS. Cross-role calls fail immediately with `403 Forbidden` (`insufficient_scope`).

### OAuth 2.1 & Discovery Specifications
- **RFC 8414 Authorization Server Discovery:** `/.well-known/oauth-authorization-server`
- **RFC 9728 Protected Resource Metadata:** `/.well-known/oauth-protected-resource`
- **RFC 8707 Resource Indicators:** Tokens carry `aud` matching the canonical URL and explicit scopes (`citizen` or `officer`).
- **RFC 7009 Token Revocation:** `/oauth/revoke`
- **Session Lifetimes:** Hard session ceiling (2h for citizens on shared kiosks; 8h for officers) with rotating refresh tokens that never extend past the session cap.

### Live PostgreSQL Invariant Evaluations (`/eval-dashboard`)
Rather than relying on synthetic LLM-grading, our evaluation framework runs **7 distinct citizen and officer personas** against live multi-turn tool conversations and asserts post-condition invariants directly in the PostgreSQL database:
1. **Rameswar Barman (64):** Clean first-time pension application submitted with verified age proof.
2. **Minati Das (58):** Underage applicant blocked by the 60-year statutory threshold; zero database records created.
3. **Bhaben Kalita (68):** Existing active applicant discovers existing pending submission; prevents duplicate entry.
4. **Anowara Khatun (66):** Re-application after voluntary withdrawal; portal allows new submission once prior state is non-active.
5. **Prabhat Sarma (72) & Officer:** End-to-end multi-agent flow where applicant submits and block officer verifies and approves.
6. **Tarun Gogoi (65) & Officer:** Officer rejection with audit trail and applicant unblocking for re-application.
7. **Statutory RTPS Deemed Approval:** Automatically verifies that applications pending past the 15-day SLA transition to `DEEMED_APPROVED` by `RTPS-AUTO`.

---

## 3. Real Client Interoperability (Claude Code)

To connect Claude Code or any MCP client:

```bash
# Connect to Citizen MCP
claude mcp add sewasetu-citizen --transport http https://<YOUR-DOMAIN>/mcp/citizen

# Connect to Officer MCP
claude mcp add sewasetu-officer --transport http https://<YOUR-DOMAIN>/mcp/officer
```

---

## 4. Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step instructions on deploying to cloud VMs (AWS EC2, DigitalOcean, Hetzner, etc.), configuring environment variables, setting up automatic Let's Encrypt SSL with Caddy, and monitoring logs.

---

## 5. Submission Artifacts

- **Design Note:** [DESIGN-NOTE.md](DESIGN-NOTE.md)
- **Loom Walkthrough Script:** [LOOM-SCRIPT.md](LOOM-SCRIPT.md)
- **Submission Form Reference:** [SUBMISSION.md](SUBMISSION.md)
