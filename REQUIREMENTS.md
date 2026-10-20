# Sewa Setu — Requirements & Architecture Specification

> **Department of Social Welfare, Government of Purvanchal**  
> *Build for Bharat Fellowship — AI Track*

---

## 1. Problems Faced by Senior Citizens

1. **Digital Exclusion & Physical Hardship:**  
   Elderly applicants (60+ years), often frail or with limited digital literacy, must physically travel long distances to Common Service Centres (CSCs) or block offices multiple times just to inquire, submit documents, or check status.
2. **Kiosk Intermediary Exploitation & Errors:**  
   Unscrupulous agents or kiosk operators frequently charge unauthorized "service fees", misspell names in Assamese/Bangla, or misenter crucial bank account / IFSC numbers, causing subsequent pension disbursement failures.
3. **Complex Eligibility & Document Rules:**  
   Seniors often do not understand statutory criteria (age thresholds, territorial block restrictions, document file formats/size caps), leading to unexpected rejections without clear explanations.
4. **Lack of Transparent Status & Communication:**  
   Once a paper or web form is submitted, applicants face an information vacuum. They do not know whether their application is under review, blocked by a document defect, or delayed by office backlogs.
5. **Shared Device / Kiosk Privacy Risks:**  
   Elderly citizens rely on family smartphones or public village computers where lingering active sessions and exposed OTPs compromise their personal privacy.

---

## 2. Problems Faced by Government Administrators

1. **Overwhelming Application Backlogs:**  
   During scheme submission windows, block welfare officers are flooded with thousands of applications, creating massive administrative bottlenecks.
2. **Statutory RTPS SLA Pressure:**  
   Under the Purvanchal Right to Public Services (RTPS) Act, officers must process each application within 15 days. Exceeding this SLA triggers automatic statutory deemed approval, heightening the risk of approving fraudulent or ineligible cases if triage is poor.
3. **Tedious Manual Document Verification:**  
   Officers spend hours deciphering low-resolution scans, blurry voter ID photocopies, and handwritten Jan Dhan passbooks, cross-referencing names and dates of birth manually.
4. **High Influx of Ineligible & Duplicate Submissions:**  
   Repeated submissions from the same applicant or underage applicants crowd the queue, diverting officer attention from genuine, vulnerable beneficiaries.
5. **Lack of Intelligent Batch Triage & Analytics:**  
   Traditional legacy portals offer basic table lists without automated risk-scoring, intelligent search, or semantic summaries to prioritize urgent cases.

---

## 3. Existing Features That Must Be Retained

1. **Single System of Record:**  
   The centralized PostgreSQL relational database (with 100,000+ baseline records) remains the absolute source of truth for all applications, citizen accounts, and audit trails.
2. **Statutory Eligibility Rules:**  
   - Statutory age requirement ($\ge 60$ years calculated from Date of Birth).
   - Application window enforcement (respecting the scheme deadline).
   - Single active application constraint: A mobile number cannot have more than one active application (`PENDING`, `APPROVED`, `DEEMED_APPROVED`) simultaneously.
3. **Re-Application Rights:**  
   Applications in `WITHDRAWN` or `REJECTED` states immediately unblock the citizen's mobile number, preserving their statutory right to apply afresh.
4. **Complete Audit Trail:**  
   Every state change (`SUBMIT`, `APPROVE`, `REJECT`, `WITHDRAW`, `DEEMED_APPROVED`) must be immutably recorded with actor identity, timestamp, and justification notes.
5. **15-Day Statutory Deemed Approval:**  
   The automated nightly cron job (`scripts/deemed_approval.py`) guaranteeing that any application pending past 15 days is transitioned to `DEEMED_APPROVED` by `RTPS-AUTO`.
6. **Citizen Status Portal & SMS Dispatch:**  
   - Direct citizen lookup at `/status` using Mobile + DOB password (DDMMYYYY).
   - Automated telecom SMS alerts for application acknowledgments and decision outcomes.

---

## 4. Missing or Broken Features (Identified & Resolved)

| Feature / Issue | Initial State in Handout | Resolved Production State |
| :--- | :--- | :--- |
| **Agentic Interface** | Pure web form with no machine-readable agent API. | Two Model Context Protocol (MCP) servers over streamable HTTP / SSE. |
| **Role Partitioning** | No separation; risking administrative tool leakage to citizens. | **Physical endpoint segregation:** `/mcp/citizen` vs `/mcp/officer`. |
| **OAuth 2.1 Discovery** | Missing RFC 9728 Protected Resource Metadata. | Full compliance: `/.well-known/oauth-protected-resource` & RFC 8414. |
| **PDF Unicode Crash** | `FPDFException: Character "—" outside range for helveticaB`. | Sanitized Unicode typography to ASCII-safe hyphen streams. |
| **Operational Health API** | No health check for container orchestration / cloud monitors. | Added `/health` reporting DB connectivity, SMS gateway, and SLA windows. |
| **Automated Evaluations** | No testing framework for agentic workflows or DB invariants. | 7-persona live evaluation harness with live DB invariant asserts at `/eval-dashboard`. |

---

## 5. Tasks an AI Agent Should Be Able to Complete

### A. Citizen AI Assistant (`/mcp/citizen`)
1. **Explain Scheme Rules:** Provide clear information on pension benefits, documentation needs, and eligibility criteria in simple, conversational language.
2. **Verify Eligibility:** Validate DOB against the 60-year rule, verify territorial block coverage, and check if an active application already exists.
3. **Submit Pension Applications:** Ingest applicant details (name, bank account, IFSC, address, DOB), generate compliant digital age-proof certificates, and register the application in the portal.
4. **Track Status & Explain RTPS SLA:** Retrieve real-time application status, explain days remaining under the 15-day statutory SLA, and provide status portal login credentials.
5. **Withdraw Applications:** Allow citizens to voluntarily withdraw a flawed pending application so they can correct mistakes and submit a clean one.
6. **Download Acknowledgment:** Generate and retrieve the official stamped acknowledgment slip for applicant records.

### B. Block Officer AI Assistant (`/mcp/officer`)
1. **Summarize Workload:** Report pending queue statistics, SLA breach warnings, and approval rates across administrative blocks.
2. **Filter & Search Queue:** Filter pending applications by block, submission date, or age; search by name, phone, or application ID.
3. **Inspect Application Dossiers:** Pull complete applicant records, including bank IFSC details, audit trails, and age-proof documents.
4. **Approve Applications:** Verify compliance, record approval decisions, issue officer remarks, and trigger applicant SMS alerts.
5. **Reject Applications with Guidance:** Record structured rejections with specific, actionable feedback (e.g., blurry voter ID) and immediately unblock the applicant's phone for re-application.

---

## 6. Security and Privacy Requirements

1. **Physical Endpoint Segregation:**  
   Applicant assistants connect to `/mcp/citizen`; block officers connect to `/mcp/officer`. A citizen's assistant cannot discover or invoke administrative tools.
2. **Cryptographic Token Verification (RS256):**  
   Every MCP request must supply a valid Bearer token signed with the portal's RS256 private key and verified against the public JWKS (`/.well-known/jwks.json`).
3. **Role & Audience Binding (RFC 8707):**  
   Tokens must explicitly carry `scope: citizen` or `scope: officer` and match the canonical resource audience (`aud`). Cross-role invocations immediately trigger `403 Forbidden` (`insufficient_scope`).
4. **Hard Session Ceilings:**  
   - Citizens: Maximum 2 hours from initial consent (preventing token misuse on shared kiosk terminals).
   - Officers: Maximum 8 hours (standard working shift). Refresh tokens rotate but cannot extend past the absolute session ceiling.
5. **No Credential Exposure to LLMs:**  
   Citizen passwords (DOB) and officer credentials are never passed through LLM prompt contexts. User authentication is handled strictly out-of-band via OAuth 2.1 PKCE flows.
6. **Input Sanitization & Data Protection:**  
   Strict character-level sanitization preserving Assamese/Bangla Unicode strings while guarding against SQL injection and cross-site scripting (XSS). Production security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`).

---

## 7. Required Evaluation Scenarios — Is This Completed in the Project?

**YES — Fully Completed & Operational (100.0% Pass Rate: 7/7 Scenarios Passed).**

The evaluation suite runs live against the actual 100,000-row PostgreSQL database and is publicly inspectable at `/eval-dashboard` (and triggered programmatically via `POST /api/evals/run`):

| # | Persona & Scenario | Tested Role | Verified Live Database Invariants | Status |
| :-: | :--- | :--- | :--- | :---: |
| **1** | **Phuleswari Saikia (71, Widow)**<br>*Clean first-time application* | Citizen | Row created in `applications`; status `PENDING`; `portal_users` account created with DOB hash; audit trail records `SUBMIT`; age proof stored on disk. | **PASSED** |
| **2** | **Minati Das (58, Tea Estate Worker)**<br>*Underage statutory block* | Citizen | Zero rows inserted in `applications`; zero portal accounts created; assistant calculates age 58 and explains statutory 60-year cutoff date (14/06/2028). | **PASSED** |
| **3** | **Bhaben Kalita (68, Farmer)**<br>*Duplicate active application check* | Citizen | Duplicate insert prevented; returns existing application `SSP26781203`; no second row created; status tracking instructions provided. | **PASSED** |
| **4** | **Anowara Khatun (66, Weaver)**<br>*Voluntary withdrawal & re-apply* | Citizen | Prior application transitioned to `WITHDRAWN`; mobile unblocked; second application successfully submitted with new application number. | **PASSED** |
| **5** | **Prabhat Sarma (72) & Officer**<br>*End-to-end multi-agent approval* | Multi-Agent | Citizen agent submits `PENDING` application; Officer agent retrieves dossier via `/mcp/officer` and approves; DB status updated to `APPROVED` with `decided_by = 'admin'`. | **PASSED** |
| **6** | **Tarun Gogoi (65) & Officer**<br>*Legitimate rejection & unblocking* | Officer | Application marked `REJECTED`; rejection reason recorded in audit log; mobile number unblocked in database so applicant can correct document and reapply. | **PASSED** |
| **7** | **Padmini Das (75, Flood Victim)**<br>*Statutory 15-day deemed approval* | Citizen | Application older than 15 days marked `DEEMED_APPROVED` by `RTPS-AUTO`; audit log verifies `system:rtps-cron`; citizen agent confirms statutory legal guarantee. | **PASSED** |
