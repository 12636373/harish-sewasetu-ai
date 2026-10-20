# Phase 6: Administrator MCP Server Implementation & Security Report

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Deliverable:** Secure Administrator MCP Server with Cryptographic Scope Enforcement

---

## 1. Executive Summary

Phase 6 delivered a dedicated, cryptographically isolated **Administrator Model Context Protocol (MCP) Server** hosted at `/mcp/officer`. In public welfare administration, granting an AI agent administrative power requires stringent safeguards: **separating two endpoint URLs is never sufficient by itself to establish a secure permission boundary**. 

The backend strictly enforces role-based access control (RBAC), verifies the officer's authenticated identity via RS256 JWT signatures, validates every requested state transition against statutory welfare invariants, protects sensitive citizen records from unauthorized extraction, and maintains an immutable audit trail for every sensitive administrative action.

---

## 2. Security Architecture & Permission Boundaries

### 2.1 The Two-Layer Security Boundary

```
[ Incoming Request to /mcp/officer ]
                │
         (1. Physical Endpoint Partitioning)
                ▼
   Is tool in OFFICER_TOOLS? ── NO ──> JSON-RPC -32601 ("Method not found")
                │ YES
         (2. Cryptographic Scope Enforcement)
                ▼
   Verify Authorization: Bearer <RS256 JWT>
   • Public Key Verification (JWKS)
   • Audience & Expiry Validation
   • Scope Check: claims["role"] == "officer" OR "officer" in claims["scope"]
                │
        ┌───────┴───────┐
        ▼               ▼
      [ PASS ]       [ FAIL ]
        │               │
        │               ├─ Missing Token: HTTP 401 (WWW-Authenticate: Bearer ...)
        │               └─ Citizen Token: HTTP 403 (insufficient_scope)
        ▼
   (3. Statutory Business Logic & State Machine Validation)
        │
        ├─ Is application in PENDING status?
        ├─ Is mandatory justification note provided?
        ├─ Does officer remarks explain documentation defect/approval?
        └─ Update applications table + Insert into audit_log + Send citizen SMS
```

* **Physical Partitioning:** The tools catalog at `/mcp/officer` only exposes administrative tools (`tools/list`). Citizen tools (`submit_application`, `raise_grievance`, etc.) are partitioned on `/mcp/citizen`.
* **Zero Trust Token Validation:** Even if an external agent knows the URL `/mcp/officer`, sending a citizen token (or unauthenticated request) is rejected with **HTTP 403 Forbidden** (`insufficient_scope`).
* **Self-Approval Prevention:** A citizen assistant can never invoke an administrative tool to approve their own application.

---

## 3. Discovered Staff Tools & Schema Specifications

The Administrator MCP server exposes **10 staff tools** covering the complete welfare case management lifecycle:

| Tool Name | Category | Purpose & Administrative Invariant |
| :--- | :---: | :--- |
| `get_officer_dashboard` | Analytics | Live summary of pending, approved, deemed approved, and rejected cases; block breakdown; and SLA breach alerts. |
| `get_welfare_analytics` | Analytics | Official alias for `get_officer_dashboard`. |
| `list_pending_applications` | Queue | Queue retrieval filtered by block and urgency (`all`, `approaching_sla` [10+ days], `overdue` [>15 days]). |
| `get_application_queue` | Queue | Official alias for `list_pending_applications`. |
| `get_application_details` | Dossier | Full case file inspection: personal details, bank verification, doc status, audit history, and compliance checks. |
| `verify_documents` | Verification | Records formal verification outcome (`VERIFIED_VALID`, `DEFECT_BLURRY`, etc.) with mandatory remarks in `audit_log`. |
| `approve_application` | Decision | Approves a `PENDING` case, records officer remarks in `audit_log`, transitions state to `APPROVED`, and dispatches DBT SMS. |
| `reject_application` | Decision | Rejects an ineligible case with mandatory justification, logs `REJECTED` in `audit_log`, sends SMS, and unblocks mobile. |
| `update_application_status`| Decision | Dispatches to `approve_application` or `reject_application` based on requested transition. |
| `search_applications` | Inquiries | Queries cases across blocks and statuses by mobile number, application number, or applicant name. |

### Complete JSON Schema Sample: `verify_documents`

```json
{
  "name": "verify_documents",
  "description": "Record a formal document verification outcome for an application. Verifies age proof validity or records specific documentation defects in the audit trail before decision-making.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "application_id": { "type": "integer", "description": "Internal database ID of application" },
      "application_no": { "type": "string", "description": "Application number (e.g. 'SSP26123456')" },
      "verification_status": {
        "type": "string",
        "enum": ["VERIFIED_VALID", "DEFECT_BLURRY", "DEFECT_NAME_MISMATCH", "DEFECT_AGE_UNDER_60", "DEFECT_INCOMPLETE"],
        "description": "Document verification outcome"
      },
      "document_type_verified": {
        "type": "string",
        "description": "Type of supporting document inspected (e.g. 'Voter ID', 'Aadhaar Card', 'Birth Certificate', 'Jan Dhan Passbook')"
      },
      "officer_remarks": {
        "type": "string",
        "description": "Detailed remarks regarding document legibility, date verification, and identity matching"
      }
    },
    "required": ["verification_status", "document_type_verified", "officer_remarks"]
  }
}
```

---

## 4. Connection to Existing Business Logic & Backend Invariants

Every administrative operation executes against authoritative backend routines and live database transactions:

### 4.1 Queue Retrieval with Automated Compliance Checks
When an officer inspects an application via `get_application_details`, the backend runs automated compliance checks:
* **Age Calculation:** Computes exact age against `now_ist()`: `age >= 60`.
* **Bank Format Verification:** Validates account digit length (`\d{9,18}`) and IFSC structure (`[A-Z]{4}0[A-Z0-9]{6}`).
* **Document Presence:** Confirms disk presence of uploaded proof in `/var/sewasetu/uploads/`.
* **RTPS SLA Clock:** Computes days pending and warns if case is approaching or exceeding the statutory 15-day SLA.

### 4.2 Document Verification Recording (`verify_documents`)
* Verifies case exists and is in `PENDING` status.
* Records `DOC_VERIFIED` or `DOC_DEFECT` in `audit_log` with `actor = admin:<officer_user>`.
* Does not permit verification updates on already decided cases.

### 4.3 Authorized Status Decisions (`approve_application` & `reject_application`)
* Enforces statutory state machine: `WHERE id = %s AND status = 'PENDING'`. Attempting to decide a case that is already `APPROVED`, `REJECTED`, or `WITHDRAWN` returns an explicit error without altering database state.
* **Mandatory Justification:** Empty or whitespace remarks are rejected (`"error": "An officer approval note/remark is required for official accountability."`).
* **SMS Gateway Integration:** Automatically notifies applicant via SMS of approval or specific rejection grounds.
* **Mobile Unblocking:** Upon rejection, the mobile number is immediately freed so the citizen can obtain fresh documents and re-apply.

---

## 5. Security & Permission Enforcement Verification

### 5.1 Test: Unauthenticated Access Blocked
```bash
curl -X POST http://localhost:8000/mcp/officer -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```
* **Result:** `HTTP 401 Unauthorized` with `WWW-Authenticate: Bearer resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource", scope="officer"`

### 5.2 Test: Cross-Role Citizen Token Denied on Admin MCP
```bash
curl -X POST http://localhost:8000/mcp/officer -H "Content-Type: application/json" -H "Authorization: Bearer <citizen_token>" -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}'
```
* **Result:** `HTTP 403 Forbidden` (`{"error": "insufficient_scope", "error_description": "Token has role 'citizen', but endpoint requires 'officer'."}`)

### 5.3 Test: Citizen Calling Admin Tool on Citizen MCP
```bash
curl -X POST http://localhost:8000/mcp/citizen -H "Content-Type: application/json" -H "Authorization: Bearer <citizen_token>" -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "approve_application", "arguments": {"application_id": 1}}}'
```
* **Result:** JSON-RPC error `-32601`: `"Tool 'approve_application' not found on this MCP endpoint."`

---

## 6. End-to-End Multi-Turn Workflow Execution

The independent test client (`verify_mcp_independent.py`) verified the complete multi-agent workflow:

```
[ Step A: Citizen ] -> Submits application -> SSP26243400 (Status: PENDING)
                              │
[ Step B: Citizen ] -> Inquires status -> Verified PENDING (15 days remaining in SLA)
                              │
[ Step C: Officer ] -> Discovers queue & inspects dossier -> Compliance checks passed
                              │
[ Step C2: Officer] -> Calls verify_documents -> Logged DOC_VERIFIED in audit_log
                              │
[ Step D: Officer ] -> Calls approve_application -> Logged APPROVED in audit_log & dispatched SMS
                              │
[ Step E: Citizen ] -> Inquires status again -> Verified APPROVED (Decided by: admin)
```

**Verification Outcome:** `100% PASSED` across all 8 protocol verification steps.

---

## 7. Deliverables Checklist

- [x] **Separate Officer MCP Endpoint:** Implemented at `/mcp/officer` over Streamable HTTP and SSE.
- [x] **10 Staff Tools:** `get_officer_dashboard`, `list_pending_applications`, `get_application_details`, `verify_documents`, `approve_application`, `reject_application`, `search_applications`, `get_application_queue`, `get_welfare_analytics`, `update_application_status`.
- [x] **Backend Integration:** Directly connected to PostgreSQL applications and audit tables.
- [x] **Scope Enforcement:** RS256 Bearer tokens require `role = "officer"`; citizen tokens rejected with HTTP 403.
- [x] **State Machine Validation:** Only `PENDING` cases can be verified, approved, or rejected.
- [x] **Audit Trail Integrity:** Officer user and mandatory justification recorded in `audit_log`.
- [x] **Independent Client:** Verified 100% via `verify_mcp_independent.py`.
