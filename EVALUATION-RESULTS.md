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
      [OK] Application created with status PENDING -> Found: SSP26398153
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
      [OK] Grievance tracking ID generated with GRV prefix -> GRV26543447
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
