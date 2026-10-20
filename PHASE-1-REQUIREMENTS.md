# Phase 1: Requirements & Architecture Specification

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Evaluation Reference:** `DIRECTOR-NOTE.mp3`, `BRIEF.md`, and Handout Codebase

---

## 1. Executive Summary & Problem Context

As a **Build for Bharat Fellow (AI Track)** appointed to the fictional Department of Social Welfare in the Government of Purvanchal, the core assignment is to help the IAS Officer (Director of Social Welfare) **re-imagine the state's Old Age Pension scheme in an agentic world**.

Senior citizens in Purvanchal encounter deep physical and digital exclusion:
- They often travel miles to rural Common Service Centres (CSCs) or block headquarters only to be misled by intermediaries who charge arbitrary commission fees or misenter critical bank details.
- When schemes operate with tight statutory deadlines under the **Purvanchal Right to Public Services (RTPS) Act** (15 calendar days), block welfare officers face immense application backlogs and risk granting automatic "deemed approvals" to unverified or fraudulent claims.

The IAS Officer's mandate is to introduce **Model Context Protocol (MCP)** endpoints so that autonomous AI assistants—acting on behalf of elderly citizens or block officers—can directly discover, query, and transact with the portal while preserving the portal and its relational database as the **uncompromised single system of record**.

---

## 2. Existing Portal Features (The Baseline System of Record)

The handout provides a functional monolithic web application running on **Flask 2.2**, **PostgreSQL 15** (pre-loaded with a production snapshot of ~100,000 applications), and a **simulated telecom SMS gateway**:

1. **Citizen Application Flow (`/apply`):**
   - 4-step progressive web form: Mobile number $\rightarrow$ OTP verification $\rightarrow$ Personal & Bank details $\rightarrow$ Age-proof document upload $\rightarrow$ Preview & Declaration $\rightarrow$ Application Number generation (`SSP26...`).
2. **Statutory Business Invariants Enforced at Submission (`validate_application`):**
   - **Age Threshold:** Applicant must be $\ge 60$ years of age on date of submission.
   - **Active Window:** The scheme submission window must be open (prior to `SCHEME_DEADLINE`).
   - **Single Active Application Rule:** A mobile number may hold at most one active application (`PENDING`, `APPROVED`, or `DEEMED_APPROVED`).
   - **Re-application Rights:** Applications in `WITHDRAWN` or `REJECTED` states immediately free the citizen's mobile number to apply afresh.
3. **Statutory 15-Day RTPS Deemed Approval:**
   - Handled by a nightly cron job (`scripts/deemed_approval.py`) in the `scheduler` container at 02:00 daily.
   - Any application pending past 15 days is automatically marked `status = 'DEEMED_APPROVED'`, `decided_by = 'RTPS-AUTO'`, and recorded in `audit_log`.
4. **Citizen Status Portal (`/status`):**
   - Citizens authenticate using their 10-digit mobile number and their Date of Birth in `DDMMYYYY` format (hashed using SHA-256 in `portal_users`).
   - Allows citizens to view application status, download stamped acknowledgment receipts, and voluntarily withdraw pending applications.
5. **Departmental Administration (`/admin`):**
   - Officer dashboard displaying summary counts by status, block breakdown, and an overdue SLA breach warning banner.
   - Queue filtering (`/admin/applications`) and individual case dossiers (`/admin/application/<id>`).
   - Action workflows for approving or rejecting applications with mandatory remarks recorded in `audit_log`.
6. **Built-in OAuth 2.1 Authorization Server:**
   - RFC 8414 Discovery (`/.well-known/oauth-authorization-server`).
   - Dynamic client registration (`/oauth/register`) and PKCE S256 code flows (`/oauth/authorize`, `/oauth/token`).
   - RS256 JWT access tokens verified via JWKS (`/.well-known/jwks.json`).
   - Hard session lifetimes (2 hours for citizens on shared kiosks; 8 hours for officers).
   - Program tokens for unattended automation (`/admin/tokens`).

---

## 3. The IAS Officer's Vision & Requested Changes

From the 3-minute audio briefing (`DIRECTOR-NOTE.mp3`) and `BRIEF.md`, the IAS Officer demands four architectural evolutions:

1. **Dual MCP Endpoints over Streamable HTTP:**
   - Create two independent, role-separated Model Context Protocol endpoints:
     - **Citizen MCP:** Accessible to applicants and citizen-facing assistants (`/mcp/citizen`).
     - **Block Officer MCP:** Accessible only to authorized government staff (`/mcp/officer`).
   - **Zero Tool Leakage:** A citizen assistant must never discover, see, or call administrative tools (such as `approve_application` or `list_pending_applications`).
2. **Strict Cryptographic & Protocol Interoperability:**
   - Support standard MCP streamable transports (JSON-RPC 2.0 over HTTP POST and SSE `GET`).
   - Integrate with the portal’s OAuth 2.1 authorization server using **RFC 9728 Protected Resource Metadata** (`/.well-known/oauth-protected-resource`).
   - Must be verified with a **real external MCP client (Claude Code)** running a small model with limited turns.
3. **Persona-Driven Invariant Evaluations (`/eval-dashboard`):**
   - Do not rely on synthetic LLM-grading or cosmetic analytics.
   - Author authentic, specific citizen dossiers (names, ages, villages, colloquial speech patterns, and specific administrative objectives).
   - Play these personas against the live assistant through the MCP endpoints.
   - **Post-Condition Database Invariants:** Directly verify that the PostgreSQL database reflects the exact required invariants after every multi-turn conversation.
   - Surface all personas, conversation transcripts, and live DB assertions on a public web page at `/eval-dashboard`.
4. **Authentic Public Interest Engineering Judgment:**
   - Avoid generic AI boilerplate. Solutions must reflect real public policy trade-offs (e.g. why 2-hour hard session caps protect shared village kiosks, why rejections must unblock applicants, and how statutory RTPS deemed approval prevents bureaucratic denial of benefits).

---

## 4. Mandatory Requirements & Assessment Expectations

| Category | Requirement | Evaluator Assessment Method |
| :--- | :--- | :--- |
| **MCP Citizen Server** | Public Streamable HTTP endpoint at `/mcp/citizen` exposing citizen tools (`check_eligibility`, `get_scheme_information`, `get_my_application_status`, `submit_application`, `withdraw_application`, `download_acknowledgment`). | Evaluators connect Claude Code directly using a citizen Bearer token and execute applicant workflows. |
| **MCP Officer Server** | Public Streamable HTTP endpoint at `/mcp/officer` exposing officer tools (`get_officer_dashboard`, `list_pending_applications`, `get_application_details`, `approve_application`, `reject_application`, `search_applications`). | Evaluators connect Claude Code using departmental credentials and process pending queues. |
| **Privilege Separation** | Physical endpoint segregation and RS256 role/scope checks. | Evaluators attempt cross-role invocations (e.g. Citizen token calling `/mcp/officer` or approving an application) and verify `403 Forbidden` / tool non-existence. |
| **OAuth 2.1 & RFC 9728** | Expose `/.well-known/oauth-protected-resource` and validate RS256 Bearer tokens against JWKS. | Evaluators check automated discovery and Bearer token challenges (`401 Unauthorized` with `resource_metadata`). |
| **Evaluation Suite** | Minimum 7 authentic citizen personas covering clean applications, underage rejection, duplicate checks, voluntary withdrawal, multi-agent approval, constructive rejection, and 15-day RTPS deemed approval. | Evaluators visit `/eval-dashboard`, trigger live re-runs, and compare student pass rates against their own test suite. |
| **Live Database Assertions**| Assertions must query live PostgreSQL records (`applications`, `portal_users`, `audit_log`) rather than using mocked responses. | Code review of `evals.py` and live DB verification. |
| **One-Page Design Note** | `DESIGN-NOTE.md` covering the **3 decisions that mattered most** and the **1 decision to change with more time**. | Evaluator manual review of engineering judgment. |
| **3-Minute Loom Walkthrough**| 3-minute video (face and screen) explaining achievements, MCP architecture, personas, and lessons learned. | Review of submitted video link against `LOOM-SCRIPT.md`. |
| **Public Uptime** | Portal, MCP endpoints, and dashboard hosted publicly on a VM up to ~30 days. | Automated periodic evaluator health pings. |

---

## 5. Architectural Restrictions & Constraints

1. **System of Record Integrity:**  
   The existing Flask portal and PostgreSQL 15 database **must remain the authoritative system of record**. The MCP servers are an interface layer, not a replacement database.
2. **Database Schema & SLA Rules:**  
   Existing core constraints (`applications`, `audit_log`, `portal_users`, `otps`, `oauth_*`) and statutory rules (60-year minimum age, 15-day SLA, single-active application) must not be weakened or bypassed.
3. **Transport & Protocol Compliance:**  
   Must implement standard Model Context Protocol over Streamable HTTP (JSON-RPC 2.0 `POST` with `initialize`, `ping`, `tools/list`, `tools/call` and SSE `GET`).
4. **Authentication & Token Privacy:**  
   - Secret tokens, API keys, or database credentials must **never be embedded in frontend JavaScript, public repos, or LLM chat logs**.
   - Citizen assistant must never output raw Date of Birth passwords.
   - Authentication must use Bearer tokens (OAuth 2.1 RFC 8414 / RFC 9728).
5. **Git Repository Hygiene:**  
   - Submission must be a **private GitHub repository** named `sewasetu-assistant` with `harshnisar` invited as a read-only collaborator.
   - **Full commit history must be retained across all development phases (do NOT squash commits).**
   - Standalone ZIP archive of the repository including `.git` must be submitted.

---

## 6. Comprehensive Requirements Traceability Checklist

### A. Citizen Experience & Web Portal
- [x] Responsive, minimalist web portal with clean typography (Inter) and clear contrast.
- [x] Senior Citizen Accessibility Bar: Font scaling (`A- / A / A+`) and High-Contrast mode.
- [x] Large touch targets ($\ge 44\text{px}$) and focus indicators for tremor accessibility.
- [x] Grounded Conversational AI Assistant (`/assistant`) querying live PostgreSQL records without hallucination.
- [x] Prompt injection defenses and credential extraction guards.
- [x] Zero password disclosures in chat responses.
- [x] Status Portal (`/status`) accessible via Mobile + DOB password (`DDMMYYYY`).

### B. Citizen MCP Server (`/mcp/citizen`)
- [x] Streamable HTTP endpoint implemented at `/mcp/citizen` (JSON-RPC 2.0 & SSE).
- [x] Exposes applicant-scoped tools: `get_scheme_information`, `check_eligibility`, `get_my_application_status`, `submit_application`, `withdraw_application`, `download_acknowledgment`.
- [x] Supports tool aliases: `list_schemes`, `get_required_documents`, `get_application_status`.
- [x] Validates RS256 Bearer tokens against portal JWKS (`scope: citizen`).
- [x] Data isolation: Queries scoped strictly to authenticated `sub: citizen:<mobile>`.
- [x] Administrative tools strictly excluded from citizen schema.

### C. Administrator MCP Server (`/mcp/officer`)
- [x] Streamable HTTP endpoint implemented at `/mcp/officer` (JSON-RPC 2.0 & SSE).
- [x] Exposes officer tools: `get_officer_dashboard`, `list_pending_applications`, `get_application_details`, `approve_application`, `reject_application`, `search_applications`.
- [x] Supports tool aliases: `get_application_queue`, `get_welfare_analytics`, `update_application_status`.
- [x] Validates RS256 Bearer tokens (`scope: officer`).
- [x] Mandatory officer verification notes enforced on approval.
- [x] Mandatory defect reasons enforced on rejection; unblocks applicant mobile number.
- [x] Cross-role rejection: Citizen tokens denied with `403 Forbidden` (`insufficient_scope`).

### D. Standards & Operational Protocols
- [x] RFC 9728 Protected Resource Metadata at `/.well-known/oauth-protected-resource`.
- [x] RFC 8414 Authorization Server Metadata at `/.well-known/oauth-authorization-server`.
- [x] Operational health check at `/health` reporting DB connection and row counts.
- [x] Production security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- [x] Automated container restart policies and database readiness health checks in `docker-compose.yml`.
- [x] Automated HTTPS reverse-proxy configuration via `Caddyfile` and `docker-compose.prod.yml`.

### E. Evaluation Framework (`/eval-dashboard`)
- [x] 7 authentic citizen & officer personas with full demographic and colloquial dossiers.
- [x] 100% live pass rate verified across multi-turn tool conversations.
- [x] Live assertions against PostgreSQL (`applications`, `portal_users`, `audit_log`).
- [x] Positive and negative tests (underage block, duplicate block, missing inputs, privilege denial).
- [x] Interactive live re-run trigger via `POST /api/evals/run`.
- [x] Independent external test client verification script (`verify_mcp_independent.py`) passing all 8 checks.

### F. Deliverables & Submission Readiness
- [x] Design Note completed: [`DESIGN-NOTE.md`](DESIGN-NOTE.md) (3 critical decisions + 1 future decision).
- [x] Loom Walkthrough script completed: [`LOOM-SCRIPT.md`](LOOM-SCRIPT.md) (3-minute timed cues).
- [x] Deployment guide completed: [`DEPLOYMENT.md`](DEPLOYMENT.md) & deployment scripts (`deploy.sh`, `deploy.ps1`).
- [x] Submission reference sheet completed: [`SUBMISSION.md`](SUBMISSION.md).
- [x] Full Git commit history preserved (13 atomic commits on `master`, unsquashed).
- [x] Standalone submission archive updated: `sewasetu-assistant.zip` (28.05 MB, `.git` included).
