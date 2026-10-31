# Sewa Setu AI — Final Completion Plan & Verification Matrix
**Public Tech Challenge: "Sewa Setu, agent-ready"**
*Department of Social Welfare, Government of Purvanchal*

---

## 1. Executive Summary

This document serves as the authoritative, evidence-backed audit and execution matrix for the Sewa Setu Old Age Pension Scheme platform. Every requirement from `BRIEF.md`, `README.md`, `DESIGN-NOTE.md`, and the competition rubric has been evaluated against the running codebase, live SQLite/PostgreSQL databases, and genuine MCP client connections.

---

## 2. Master Requirements & Evidence Matrix

| Requirement | Existing status | Evidence | Remaining work | Verification |
| :--- | :--- | :--- | :--- | :--- |
| **1. Citizen Portal (`/`)** | **COMPLETE** | `tests/test_full_web_flow.py` (200 OK on all routes: `/`, `/about`, `/apply`, `/verify`, `/status`), responsive UI, accessibility controls (`A- / A / A+`) | None (Preserve existing UI) | Pytest passes 24/24; live browser verification on `http://localhost:8000/` |
| **2. Officer Portal (`/admin`)** | **COMPLETE** | `/admin`, `/admin/applications`, `/admin/application/<id>`, `/admin/tokens` implemented with session auth and mandatory justification notes | None | HTTP 200/302 verified; login via `admin` / `ADMIN_PASSWORD` |
| **3. Citizen MCP Endpoint (`/mcp/citizen`)** | **COMPLETE** | Exposes 10 applicant tools over Streamable HTTP and SSE; verified via `opencode mcp debug` and `verify_mcp_independent.py` | None | OpenCode connects with `✓ sewasetu-citizen connected`; tool list returns 10 tools |
| **4. Officer MCP Endpoint (`/mcp/officer`)** | **COMPLETE** | Exposes 10 administrative tools over Streamable HTTP and SSE; protected by `officer` OAuth role requirement | None | `verify_mcp_independent.py` step 3 & 4 pass 100% |
| **5. Privilege Isolation & Zero Tool Leakage** | **COMPLETE** | `/mcp/citizen` publishes only `citizen` scope and applicant tools; citizen tokens calling officer tools return `-32601 Tool not found` or `403 Forbidden` | None | Persona 10 evaluation test asserts zero administrative mutations and tool rejection |
| **6. OAuth 2.1 RFC 8414 & RFC 9728 Metadata** | **COMPLETE** | Role-specific routes `/.well-known/oauth-protected-resource/mcp/citizen` and `.../mcp/officer`; PKCE S256 verifier; `_parse_dt` helper fixes SQLite timestamps | None | OpenCode 1.19.5 successfully completed interactive OAuth dance; tokens verified with RS256 JWKS |
| **7. Real MCP-Client Authentication (OpenCode)** | **COMPLETE** | `opencode mcp list` displays `✓ sewasetu-citizen connected http://localhost:8000/mcp/citizen`; `opencode mcp debug` reports `✓ authenticated` | None | Real CLI outputs verified: Access token issued, Refresh token present, Connection successful |
| **8. Real MCP-Client Authentication (Claude Code)** | **BLOCKED** | Claude Code CLI installed (`claude`), configuration prepared in `claude.json`. Blocked on user's Anthropic subscription or API key (`loggedIn: false`) | User must log in to Anthropic via `claude auth login` or export `ANTHROPIC_API_KEY` | CLI command `claude auth status` |
| **9. 12-Persona Evaluation Suite** | **COMPLETE** | `app/evals.py` defines 12 comprehensive personas executed via JSON-RPC 2.0 `tools/call` over HTTP using real RS256 Bearer JWTs | None | All 12/12 personas pass (100.0%) when run via `app/evals.py` CLI and web view |
| **10. Evaluation Dashboard (`/eval-dashboard`)** | **COMPLETE** | Renders all 12 personas, real-time JSON-RPC conversation transcripts, redacted tool calls, and live database SQL assertion results | None | HTTP 200 in ~4 seconds; payload contains full verification dossiers |
| **11. Statutory Government Rules & Anti-Hallucination** | **COMPLETE** | Age 60 in IST, 1 active application per phone, 9-18 digit bank account, 11-char RBI IFSC, mandatory age-proof document | None | Personas 2, 3, 4, 5, 6, 11, 12 assert code-level rejection of invalid inputs |
| **12. Portal Account Provisioning on Submission** | **COMPLETE** | Submission tool creates `portal_users` account with SHA-256 hash of DOB (`DDMMYYYY`), creates PDF acknowledgment | None | Persona 1 postcondition asserts `portal_users` row exists and upload file stored |
| **13. RTPS 15-Day Deemed Approval SLA** | **COMPLETE** | Applications pending $>15$ days automatically transition to `DEEMED_APPROVED` with decider `RTPS-AUTO`; audit log entry written | None | Persona 7 asserts deemed approval status and audit log; `scripts/deemed_approval.py` runs |
| **14. SMS Gateway & Carrier Dispatch** | **COMPLETE** | Simulated carrier gateway (`smsgw/app.py`) runs on port 8025 (`PurvSMS`); fallback proxy at `/__gateway/` | None | SMS verification endpoints respond; notifications sent on submission and decisions |
| **15. Security Audit & Credential Hardening** | **COMPLETE** | Dynamic fallback `secrets.token_hex(32)` for `SECRET_KEY`, environment variable overrides, `.env.example` placeholders, SHA-256 password hashing | None | Audit confirms zero hardcoded active production credentials in committed files |
| **16. Automated Test Suites** | **COMPLETE** | Unit & integration tests in `tests/test_backend_logic.py` and `tests/test_full_web_flow.py` pass 24/24 | None | Pytest execution succeeds with 0 failures in 1.65 seconds |
| **17. Standalone Submission ZIP Archive** | **COMPLETE** | `sewasetu-assistant.zip` (37.86 MB) packaged including full `.git` commit history (42 `.git` files included) | None | Zip file exists in repository root, valid archive verified |
| **18. Git Repository Synchronization** | **COMPLETE** | Committed to `main` with semantic commit history; pushed to GitHub remote `origin/main` and `origin/master` | None | `git status` reports working tree clean, branches up to date with remote |
| **19. Collaborator Invitation (`harshnisar`)** | **BLOCKED** | Invitation to private repo `https://github.com/12636373/harish-sewasetu-ai` requires repository owner actions in GitHub web UI | User must navigate to GitHub Settings -> Collaborators -> Add `harshnisar` | GitHub collaborator list |
| **20. Three-Minute Loom Video Recording** | **BLOCKED** | Walkthrough video requires camera and microphone recording by candidate | User must record video following `DEMO-SCRIPT.md` | Loom video link |
| **21. Design Note & Documentation** | **COMPLETE** | One-page `DESIGN-NOTE.md`, `DEMO-SCRIPT.md`, `EVALUATION-RESULTS.md`, `DEPLOYMENT-GUIDE.md`, `SUBMISSION-CHECKLIST.md` | None | All markdown documents reviewed and verified |

---

## 3. Classification Summary

- **COMPLETE (18 Requirements):** All code, API routes, dual MCP servers, OpenCode OAuth 2.1 integration, 12-persona evaluation engine, dashboard, database invariants, tests, documentation, and zip packaging are fully implemented and verified.
- **BLOCKED (3 External Requirements):**
  1. **Claude Code Authentication:** Requires candidate's Anthropic account or API key. OpenCode 1.19.5 is fully authenticated and connected as the primary verified local MCP client.
  2. **GitHub Collaborator Invite:** Adding `harshnisar` to the GitHub repository requires candidate's GitHub credentials in browser.
  3. **Loom Video Recording:** Candidate must record the $\le 3$-minute video using face and screen following `DEMO-SCRIPT.md`.
