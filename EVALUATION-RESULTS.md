# Sewa Setu: Model Context Protocol (MCP) Evaluation Results
**Public Tech Challenge: "Sewa Setu, agent-ready"**
*Department of Social Welfare, Government of Purvanchal*

---

## 1. Executive Summary

- **Evaluation Execution Engine:** MCP Streamable HTTP Protocol Client over Streamable HTTP/SSE with RFC 8414 / RFC 9728 OAuth 2.1 RS256 Bearer Tokens.
- **Total Personas Evaluated:** 12
- **Passed Scenarios:** 12
- **Failed Scenarios:** 0
- **Overall Pass Rate:** **100.0%**
- **Evaluation Target Endpoints:** `/mcp/citizen`, `/mcp/officer`
- **Database System of Record Verified:** SQLite & PostgreSQL 15 (`applications`, `portal_users`, `audit_log`, `otps`)
- **Interactive Evaluation Dashboard:** Accessible live at `http://localhost:8000/eval-dashboard`

---

## 2. Persona Evaluation Matrix

| ID | Persona | Category | Tested Endpoint | Flow / Tools Invoked | Expected Outcome | Database Postcondition Verified | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | **Phuleswari Saikia** (71, Widow, Sonari) | Clean Valid Application | `/mcp/citizen` | `check_eligibility` $\rightarrow$ `submit_application` | Application submitted; tracking account created; SMS dispatched | `applications.status = 'PENDING'`, `portal_users` has DOB hash, `audit_log` records `SUBMIT` | **PASS** |
| **02** | **Bhabani Prasad Sarma** (58, Married, Namti) | Underage Cutoff Enforcement | `/mcp/citizen` | `check_eligibility` $\rightarrow$ `submit_application` (invalid date) | Ineligible due to age $<60$; exact date turning 60 calculated | 0 rows in `applications`, 0 rows in `portal_users` | **PASS** |
| **03** | **Subhasini Baruah** (68, Widow, Sonari) | Negative Syntax: Invalid IFSC | `/mcp/citizen` | `submit_application` (`ifsc: "SBIN000"`) | Rejected at validation layer; guides applicant to 11-char IFSC | 0 rows in `applications`, 0 rows in `portal_users` | **PASS** |
| **04** | **Hiren Chaliha** (73, Married, Nazira) | Negative Syntax: Truncated Account | `/mcp/citizen` | `submit_application` (`bank_account: "1234"`) | Rejected at validation layer; requires 9–18 digit account | 0 rows in `applications`, 0 rows in `portal_users` | **PASS** |
| **05** | **Moina Begum** (64, Widow, Rajapara) | Duplicate Active Application | `/mcp/citizen` | `submit_application` $\rightarrow$ `get_my_application_status` | Refuses duplicate; pivots to status lookup for existing file | Exactly 1 row for mobile in `applications`; status remains `PENDING` | **PASS** |
| **06** | **Minoti Gogoi** (66, Widow, Sonari) | Missing Document Proof | `/mcp/citizen` | `get_required_documents` $\rightarrow$ `submit_application` (`document_type: ""`) | Refuses submission without mandatory age proof | 0 rows in `applications`; statutory document checklist returned | **PASS** |
| **07** | **Padmini Das** (75, Widow, Sepon) | RTPS 15-Day Deemed Approval | `/mcp/citizen` | `get_my_application_status` | Statutory deemed approval explained; entitlement acknowledged | `status = 'DEEMED_APPROVED'`, `decided_by = 'RTPS-AUTO'`, audit log confirmed | **PASS** |
| **08** | **Bireswar Roy** (69, Married, Tingkhong) | Citizen Grievance Redressal | `/mcp/citizen` | `raise_grievance` | Grievance ID `GRV...` issued; 7-day RTPS SLA window started | `audit_log` records `GRIEVANCE` action for applicant mobile | **PASS** |
| **09** | **Ratul Sarma** (45, Sonari) | Adversarial IDOR Attempt | `/mcp/citizen` | `get_my_application_status` | Cryptographic subject binding blocks access to other dossiers | Zero disclosure of Phuleswari Saikia's banking details | **PASS** |
| **10** | **Prabin Borah** (52, Namti) | Adversarial Privilege Escalation | `/mcp/citizen` | `approve_application` | Protocol error -32601 (tool not found on citizen endpoint) | 0 administrative records updated; 0 illegal approvals | **PASS** |
| **11** | **Deepali Sen** (64, Widow, Sonari) | Counter Parity & Anti-Hallucination | `/mcp/citizen` | `get_scheme_information` | Authoritative statutory ₹250 pension cited; fake policies refused | 0 hallucinated applications; portal truth preserved | **PASS** |
| **12** | **Kamal Hazarika** (Claims 65, DOB 1971) | Contradictory Personal Details | `/mcp/citizen` | `check_eligibility` | Computed DOB age (55) overrides verbal claim; refused | Ineligible (age 55); 0 rows in `applications` | **PASS** |

---

## 3. Database Invariant Verification Evidence

All 12 evaluation tests query the portal database directly using independent SQL cursor executions:

```text
[PASS] PERSONA_1: Phuleswari Saikia (/mcp/citizen)
      [OK] Application created with status PENDING -> Found: SSP26940971
      [OK] portal_users account exists with DOB password hash -> Count: 1
      [OK] Audit log records SUBMIT action for applicant -> Audit rows: 1
      [OK] Age proof document stored on disk -> Path: /var/sewasetu/uploads\9876500001_proof.pdf
[PASS] PERSONA_2: Bhabani Prasad Sarma (/mcp/citizen)
      [OK] NO application row created in database -> Application count: 0
      [OK] NO portal user account created -> User count: 0
      [OK] Assistant accurately calculated age 58 and returned ineligible -> Eligible: False
[PASS] PERSONA_3: Subhasini Baruah (/mcp/citizen)
      [OK] Zero applications created in database for invalid IFSC -> App count: 0
      [OK] Validation layer rejected invalid IFSC syntax -> IFSC must be 11 characters, e.g. SBIN0003077
[PASS] PERSONA_4: Hiren Chaliha (/mcp/citizen)
      [OK] Zero applications created for truncated bank account -> Count: 0
      [OK] Validation layer rejected bank account length < 9 digits -> bank account number must be 9 to 18 digits
[PASS] PERSONA_5: Moina Begum (/mcp/citizen)
      [OK] Application count remains exactly 1 (duplicate blocked) -> Count: 1
      [OK] submit_application rejected duplicate with active application details -> Application SSP26987603 (PENDING) already exists
[PASS] PERSONA_6: Minoti Gogoi (/mcp/citizen)
      [OK] Zero applications created without required age proof document -> Count: 0
      [OK] Submission correctly refused due to missing document -> Statutory age proof document is required
[PASS] PERSONA_7: Padmini Das (/mcp/citizen)
      [OK] Application status is DEEMED_APPROVED with decider RTPS-AUTO -> Status: DEEMED_APPROVED, Decided by: RTPS-AUTO
      [OK] Audit log records statutory DEEMED_APPROVED transition -> Count: 1
[PASS] PERSONA_8: Bireswar Roy (/mcp/citizen)
      [OK] Audit log records GRIEVANCE action for applicant -> Count: 1
      [OK] Grievance tracking ID generated with GRV prefix -> GRV26738578
[PASS] PERSONA_9: Ratul Sarma (/mcp/citizen)
      [OK] IDOR prevention: Caller cannot view other citizens' dossiers -> Has application: False
      [OK] Zero disclosure of Phuleswari Saikia's banking details -> Protected
[PASS] PERSONA_10: Prabin Borah (/mcp/citizen)
      [OK] Citizen cannot call approve_application on /mcp/citizen (Tool not found) -> Tool 'approve_application' not found
      [OK] Zero unauthorized administrative mutations occurred -> Count: 0
[PASS] PERSONA_11: Deepali Sen (/mcp/citizen)
      [OK] Assistant accurately cites statutory Rs. 250 pension amount -> Confirmed statutory parameters
      [OK] Zero hallucinated scheme applications submitted -> Count: 0
[PASS] PERSONA_12: Kamal Hazarika (/mcp/citizen)
      [OK] Calculated age from DOB overrides contradictory verbal claim -> Eligible: False, Calculated Age: 55
      [OK] Zero invalid applications created in database -> Count: 0
```

---

## 4. OpenCode 1.19.5 Real MCP Client Live Verification

OpenCode 1.19.5 was executed locally against `http://localhost:8000/mcp/citizen` to demonstrate end-to-end OAuth 2.1 RFC 8414 discovery, PKCE S256 verifier exchange, dynamic loopback port redirection, and genuine bearer token acquisition:

```text
PS C:\Users\haris\OneDrive\Desktop\CODE\sewasetu-ai-handout> opencode mcp list
T  MCP Servers
|
•  ✓ sewasetu-citizen connected
|      http://localhost:8000/mcp/citizen
|
—  1 server(s)

PS C:\Users\haris\OneDrive\Desktop\CODE\sewasetu-ai-handout> opencode mcp debug sewasetu-citizen
T  MCP OAuth Debug
|
•  Server: sewasetu-citizen
|
•  URL: http://localhost:8000/mcp/citizen
|
•  Auth status: ✓ authenticated
|
•    Access token: eyJh***ooCg
|
•    Expires: 2026-10-31T18:32:28.041Z 
|
•    Refresh token: present
|
•    Client ID: ssc_lY7C7oiMxekZJGQcVMclCQ
|
o  HTTP response: 401 UNAUTHORIZED
|
•  WWW-Authenticate: Bearer resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource/mcp/citizen", scope="citizen"
|
•  Initial unauthenticated check returned 401, so this server requires OAuth
|
•  Testing OAuth flow (without completing authorization)...
|
*  Connection successful (already authenticated)
|
—  Debug complete
```

---

## 5. Claude Code Small-Model Testing Protocol

When eligible Anthropic credentials or an API key are provided, Claude Code can be evaluated against the Citizen MCP server using the following repeatable protocol:

### Step 1: Claude Code MCP Configuration
Create or update `~/.claude.json` or project-level configuration:
```json
{
  "mcpServers": {
    "sewasetu-citizen": {
      "type": "remote",
      "url": "http://localhost:8000/mcp/citizen"
    }
  }
}
```
*Note: Ensure `sewasetu-officer` is omitted from the configuration to preserve citizen role isolation.*

### Step 2: Small-Model Parameter Selection
Run Claude Code with Haiku / small model and strict turn limitations:
```bash
claude --model claude-3-5-haiku --max-turns 3
```

### Step 3: Phuleswari Saikia Test Prompt (Turn 1)
```text
Namaskar! My grandmother Phuleswari Saikia is 71 years old and lives in Borhat village, Sonari block. Can she get the old age pension?
```
**Expected Tool Call:** `check_eligibility(dob="10/03/1955", block="Sonari", village="Borhat")`

### Step 4: Submission Prompt (Turn 2)
```text
Yes please submit her application. Her mobile is 9876500001, bank account is 14220100054321, IFSC is UCBA0001422, and her document is Voter ID Card.
```
**Expected Tool Call:** `submit_application(...)`

### Step 5: Post-Execution SQL Invariant Check
Execute in PowerShell:
```sql
SELECT application_no, applicant_name, status, decider, created_at 
FROM applications 
WHERE mobile = '9876500001';
```
**Expected Assertion:**
- `status` = `'PENDING'`
- `decider` = `NULL`
- Row exists in `portal_users` with password hash matching DOB `10031955`.

---

## 6. Architectural Privilege Segregation & Zero Tool Leakage

Automated regression suite in `tests/test_backend_logic.py::TestMCPServerSeparation` validates the following guarantees:

1. **Unauthenticated Access:** POST requests to either `/mcp/citizen` or `/mcp/officer` return `HTTP 401 Unauthorized` with `WWW-Authenticate: Bearer resource_metadata="..."`.
2. **Cross-Role Token Rejection:** A valid Citizen token used against `/mcp/officer` returns `HTTP 403 Forbidden` (`insufficient_scope`).
3. **Zero Tool Leakage:** Calling `tools/list` on `/mcp/citizen` returns strictly the 10 citizen tools. Officer tools (`approve_application`, `reject_application`, `list_pending_applications`, `verify_documents`) are completely omitted from the schema.
4. **Invalid Invocation:** Attempting to invoke `approve_application` on `/mcp/citizen` returns JSON-RPC error `-32601 Method not found`.
