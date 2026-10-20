# Phase 4: Backend Stabilization & Database Reliability Report

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Deliverable:** Stable, Auditable Backend Serving Both Website and MCP Servers

---

## 1. Executive Summary

Phase 4 hardened the backend architecture and PostgreSQL database layer of the Sewa Setu Old Age Pension system. In public welfare delivery, **business logic must be authoritative, tamper-proof, and universally applied across all entry channels**—whether a citizen uses the self-service web portal, an AI citizen assistant, an external MCP client (such as Claude Code), or a Block Welfare Officer uses departmental tools.

This phase established strict single-source-of-truth invariants across database tables, eliminated potential data collisions, enforced statutory welfare state transitions, created consistent error contracts (JSON for APIs/MCP; accessible HTML for senior citizens), extended audit logging to all sensitive administrative actions, and established a 20-test automated verification suite (`tests/test_backend_logic.py`) achieving **100% pass rate**.

---

## 2. Database Schema & Relational Analysis

### 2.1 Table Inventory & Foreign Relationships

The system operates against a PostgreSQL 15 database loaded with production-scale data (100,000+ seeded records):

```
                                 [applications]
                       (Core Beneficiary Welfare Record)
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  [portal_users]                  [audit_log]                      [otps]
(Mobile -> DOB Hash)      (Immutable Ledger of Actions)    (5-min Rolling OTPs)
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       ▼
                       [OAuth 2.1 Authorization Layer]
            (oauth_keys, oauth_clients, oauth_codes, oauth_refresh_tokens,
                          oauth_program_tokens)
```

| Table Name | Primary Key | Key Columns & Data Types | Role in System | Invariant Enforced |
| :--- | :--- | :--- | :--- | :--- |
| `applications` | `id` (SERIAL) | `application_no` (VARCHAR 20), `mobile` (VARCHAR 15), `dob` (DATE), `status` (VARCHAR 20), `block`, `bank_account`, `ifsc`, `submitted_at`, `decided_at`, `decided_by` | System of record for all pension cases. | At most 1 active application per mobile; statutory age $\ge 60$; recognized blocks only. |
| `portal_users` | `mobile` (VARCHAR 15) | `password_hash` (VARCHAR 80) | Citizen credentials for status portal. | Hash of DOB in `DDMMYYYY` format; auto-provisioned upon application submission. |
| `audit_log` | `id` (SERIAL) | `application_id` (INTEGER, nullable), `action` (VARCHAR 20), `actor` (VARCHAR 50), `note` (VARCHAR 500), `at` (TIMESTAMP) | Immutable audit trail of every life-cycle event. | Non-repudiation of administrative decisions and security actions. |
| `otps` | `id` (SERIAL) | `mobile` (VARCHAR 15), `code` (VARCHAR 6), `created_at` (TIMESTAMP) | Temporary proof of mobile ownership. | 5-minute statutory validity window (`otp_validity_seconds = 300`). |
| `oauth_program_tokens` | `id` (SERIAL) | `jti` (VARCHAR 32 UNIQUE), `label`, `subject`, `audience`, `issued_by`, `created_at`, `expires_at` | Long-lived unattended administrative tokens. | Bound to authorized officers; revocable on demand. |

---

## 3. Data Model Defect Remediation & Schema Hardening

During backend inspection, three critical vulnerabilities in data modeling were identified and resolved:

### 3.1 Defect 1: Partial Unique Constraint for Active Applications
* **Vulnerability:** Previously, duplicate submission prevention relied purely on application-level checks in Python (`active_application(cur, mobile)`). Under high concurrency or network retries, race conditions could insert two simultaneous `PENDING` applications for the same mobile.
* **Engineering Fix:** Added a PostgreSQL partial unique index in `app/schema.sql` and applied it to the live database:
  ```sql
  CREATE UNIQUE INDEX IF NOT EXISTS idx_active_app_mobile 
  ON applications (mobile) 
  WHERE status IN ('PENDING', 'APPROVED', 'DEEMED_APPROVED');
  ```
* **Result:** The database engine itself rejects concurrent active submissions, while still allowing citizens with `WITHDRAWN` or `REJECTED` applications to apply afresh without error.

### 3.2 Defect 2: Application Number Collision Resistance
* **Vulnerability:** The starter codebase generated application numbers via `SSP + 2-digit year + random(100000, 999999)`. Across 100,000+ seeded records, birthday paradox collisions could occasionally trigger primary key or uniqueness violations.
* **Engineering Fix:** Refactored `new_application_no(cur=None)` to accept the active transaction cursor and verify database uniqueness prior to assignment:
  ```python
  def new_application_no(cur=None):
      for _ in range(15):
          candidate = "SSP" + datetime.now().strftime("%y") + str(random.randint(100000, 999999))
          if cur:
              cur.execute("SELECT 1 FROM applications WHERE application_no = %s", (candidate,))
              if not cur.fetchone():
                  return candidate
          else:
              return candidate
      return candidate
  ```

### 3.3 Defect 3: Non-Blocking Re-Application
* **Rule:** If an application was rejected due to an unreadable document scan, or voluntarily withdrawn by the applicant to correct banking details, the citizen must **not** be blocked from applying again.
* **Implementation:** The `active_application` lookup queries only `ACTIVE_STATUSES = ('PENDING', 'APPROVED', 'DEEMED_APPROVED')`. Both `WITHDRAWN` and `REJECTED` states immediately free the citizen's mobile number.

---

## 4. Statutory State Machine & Status Transitions

Public welfare administration requires strict status transition invariants. Applications cannot jump between arbitrary states or be revoked once decided:

```
                      ┌────────────────────────────────────────┐
                      │                PENDING                 │
                      └───────┬──────────┬──────────┬──────────┘
                              │          │          │
                 ┌────────────┘          │          └────────────┐
                 ▼                       ▼                       ▼
           [ APPROVED ]            [ REJECTED ]            [ WITHDRAWN ]
      (Block Officer Review)   (Mandatory Note Req.)   (Voluntary Citizen Action)
                 │
                 ▼
        [ DEEMED_APPROVED ]
    (15-Day RTPS SLA Expiry)
```

### State Machine Specification

```python
VALID_TRANSITIONS = {
    "PENDING": {"APPROVED", "REJECTED", "WITHDRAWN", "DEEMED_APPROVED"},
    "APPROVED": set(),         # Terminal state
    "REJECTED": set(),         # Terminal state (unblocks mobile)
    "WITHDRAWN": set(),        # Terminal state (unblocks mobile)
    "DEEMED_APPROVED": set(),  # Terminal state (statutory)
}

def can_transition(current_status, new_status):
    """Statutory welfare state machine."""
    return (new_status or "").upper() in VALID_TRANSITIONS.get((current_status or "").upper(), set())
```

* **Terminal State Invariant:** No transition can occur from `APPROVED`, `REJECTED`, `WITHDRAWN`, or `DEEMED_APPROVED`.
* **Enforcement:** Enforced in `_admin_decide()` in `app/app.py`, in `approve_application` / `reject_application` / `update_application_status` in `app/mcp_server.py`, and verified in `tests/test_backend_logic.py`.

---

## 5. Consistent Error Handling Contract

To ensure interoperability with external LLM agents and human citizens alike, consistent error responses were implemented via custom Flask handlers:

* **API & MCP Requests (`/api/*`, `/mcp/*`, or `Accept: application/json`):**
  Return structured JSON error objects with explicit HTTP status codes:
  ```json
  {
    "error": "not_found",
    "message": "The requested welfare portal page or application record was not found.",
    "status_code": 404
  }
  ```
* **Browser Requests (`Accept: text/html`):**
  Render accessible `error.html` with large typography, clear guidance, one-click return links, and high-contrast support.

| HTTP Status | Error Type | JSON Contract Returned | Accessible Web UX Rendered |
| :---: | :--- | :--- | :--- |
| **400** | Bad Request | `{"error": "bad_request", "message": ..., "status_code": 400}` | Clean alert card explaining malformed input |
| **403** | Access Forbidden | `{"error": "forbidden", "message": ..., "status_code": 403}` | Officer permission warning with login redirect |
| **404** | Not Found | `{"error": "not_found", "message": ..., "status_code": 404}` | Search assistance and return-home action pills |
| **500** | Internal Error | `{"error": "internal_server_error", "message": ..., "status_code": 500}` | Non-technical advisory that admin was notified |

---

## 6. Comprehensive Audit Logging for Sensitive Operations

All sensitive operations are immutably logged into `audit_log`:

| Event | Action Code | Actor Format | Logged Metadata / Invariant |
| :--- | :---: | :--- | :--- |
| **Application Submission** | `SUBMIT` | `applicant:<mobile>` | Initial submission timestamp, linked to application ID |
| **Voluntary Withdrawal** | `WITHDRAW` | `applicant:<mobile>` | Citizen reason for withdrawal (e.g. IFSC typo) |
| **Officer Approval** | `APPROVED` | `admin:<officer_user>` | Officer approval remarks |
| **Officer Rejection** | `REJECTED` | `admin:<officer_user>` | Mandatory legal rejection justification note |
| **RTPS Deemed Approval** | `DEEMED_APPROVED` | `system:rtps-cron` | Statutory note: *"not processed within SLA"* |
| **Password Reset** | `RESET_PASSWORD` | `system:citizen-reset` | Password reset to Date of Birth (`DDMMYYYY`) |
| **OAuth Token Minting** | `MINT_PROGRAM_TOKEN` | `admin:<admin_user>` | Token label, target audience, and validity duration |
| **Token Grant Revocation** | `REVOKE_TOKEN_GRANTS`| `admin:<admin_user>` | Number of revoked officer/citizen grants |

---

## 7. Automated Backend Test Suite (`tests/test_backend_logic.py`)

A comprehensive test suite of **20 unit and integration tests** was developed, verifying business logic, database transactions, constraints, and error contracts against live PostgreSQL:

```bash
docker compose exec app python /tests/test_backend_logic.py
```

### Execution Log

```
....................
----------------------------------------------------------------------
Ran 20 tests in 0.179s

OK
```

### Breakdown of Test Cases

```
TestSchemeValidation
├── test_valid_application_passes .............. [PASS] Valid 72-year-old application passes cleanly
├── test_underage_applicant_fails .............. [PASS] 58-year-old rejected at validation layer
├── test_missing_required_fields_fail .......... [PASS] Name, village, block, bank account checks
├── test_unrecognized_block_fails .............. [PASS] Block outside recognized 6 blocks fails
├── test_invalid_bank_account_fails ............ [PASS] Regex check (\d{9,18}) rejects bad accounts
├── test_invalid_ifsc_fails .................... [PASS] Regex check ([A-Z]{4}0[A-Z0-9]{6}) enforced
├── test_invalid_dob_format_fails .............. [PASS] Rejects non-existent dates (31/02/1955)
└── test_missing_doc_path_fails ................ [PASS] Age proof document presence enforced

TestStatusTransitions
├── test_valid_transitions_from_pending ........ [PASS] PENDING -> APPROVED/REJECTED/WITHDRAWN/DEEMED
└── test_invalid_transitions_from_terminal ..... [PASS] Rejects illegal transitions from decided states

TestApplicationNumberGeneration
├── test_app_number_format ..................... [PASS] SSP26 prefix, 11-char length, 6-digit suffix
└── test_unique_generation_with_cursor ......... [PASS] Cursor collision check prevents duplicates

TestDatabaseIntegrityAndPersistence
└── test_create_and_active_application_lifecycle [PASS] End-to-end DB lifecycle, portal_users hash,
                                                        partial unique constraint, and audit logging

TestErrorResponses
├── test_json_404_for_api ...................... [PASS] API requests receive {"error": "not_found", 404}
├── test_json_404_for_mcp ...................... [PASS] MCP requests receive JSON error objects
└── test_html_404_for_browser .................. [PASS] Browsers receive accessible HTML template

TestAuthenticationAndAuthorization
├── test_unauthenticated_admin_routes_redirect . [PASS] /admin/* redirects unauthenticated requests
├── test_unauthenticated_citizen_routes_redirect [PASS] /application/* enforces login session
└── test_mcp_unauthenticated_challenge ......... [PASS] /mcp/* returns HTTP 401 with RFC 9728 header

TestAuditLogSensitiveOperations
└── test_administrative_audit_actions .......... [PASS] MINT_PROGRAM_TOKEN & RESET_PASSWORD persisted
```

---

## 8. Verification Summary

| Task | Requirement | Status | Verification Mechanism |
| :---: | :--- | :---: | :--- |
| **1** | Inspect database tables & relationships | ✅ Complete | Inspected 10 tables, indexes, and FK linkages |
| **2** | Identify missing/incorrect models | ✅ Complete | Fixed birthday collision risk & active application race |
| **3** | Fix API routes & validation | ✅ Complete | Sanitization, date parsing, regex validation unified |
| **4** | Consistent error responses | ✅ Complete | Content-negotiated JSON vs accessible HTML (400/403/404/500) |
| **5** | Authentication & authorization | ✅ Complete | Role separation, session checks, and RS256 Bearer tokens |
| **6** | Changes persist in database | ✅ Complete | Full transactional integrity verified across reads |
| **7** | Prevent duplicate submissions & invalid transitions | ✅ Complete | Partial unique index `idx_active_app_mobile` + state machine |
| **8** | Audit logging for sensitive operations | ✅ Complete | `SUBMIT`, `WITHDRAW`, `APPROVED`, `REJECTED`, `RESET_PASSWORD`, `MINT_PROGRAM_TOKEN` |
| **9** | Automated tests for business logic | ✅ Complete | 20/20 tests passing in `tests/test_backend_logic.py` |
