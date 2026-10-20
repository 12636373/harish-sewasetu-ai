# Sewa Setu: Agent-Ready Public Pension Delivery
## One-Page Design Note — Build for Bharat Fellow (AI Track)
**Department of Social Welfare, Government of Purvanchal**

---

### Overview
Sewa Setu manages monthly welfare pensions of ₹250 for senior citizens aged 60 and above across six blocks of Purvanchal. Re-imagining this portal in an agentic world requires serving two distinct human actors: elderly citizens (assisted by family members or rural CSC operators) and block welfare officers adjudicating hundreds of pending files. We built two independent Model Context Protocol (MCP) servers over Streamable HTTP and SSE, integrated with Sewa Setu’s OAuth 2.1 authorization server, preserving the portal as the single, authoritative system of record.

---

### The Three Decisions That Mattered Most

#### 1. Strict Endpoint & Schema Bifurcation with OAuth 2.1 Role Enforcement
* **Decision:** We established two completely separate MCP endpoints: `/mcp/citizen` and `/mcp/officer`, each registered with its own tool catalog and guarded by OAuth 2.1 Bearer token validation (RFC 9728 / RFC 8707). A citizen’s assistant is strictly physically isolated from administrative tools.
* **Why it mattered:** In public welfare administration, privilege containment must be architectural, not prompt-based. LLMs presented with unified schemas can suffer from prompt injection, role confusion, or hallucinated authorization. By publishing distinct endpoints and rejecting cross-role tokens with `403 Forbidden`, a citizen assistant cannot even discover—let alone invoke—officer tools like `approve_application` or `list_pending_applications`. Furthermore, citizen actions are cryptographically pinned to the authenticated subject’s mobile number (`sub: citizen:<mobile>`), preventing identity spoofing.

#### 2. Deterministic Code-Level Enforcement of Statutory Rules (Anti-Hallucination & Counter Parity)
* **Decision:** All MCP tool actions route directly through the portal’s core business logic (`validate_application()`, `active_application()`, `create_application()`). Prompt guidance is supplemented by hard schema constraints and database-level checks.
* **Why it mattered:** AI assistants tend to be overly accommodating—they might tolerate a 58-year-old’s plea or allow multiple pending applications from the same phone. Our server deterministically enforces:
  1. Minimum statutory age of 60 computed against Indian Standard Time (IST).
  2. Single active application policy per mobile number.
  3. Strict 9–18 digit bank account validation and 11-character RBI IFSC syntax.
  4. Mandatory plain-language justification notes for all officer approvals and rejections.
  As mandated by the Director, the AI assistant never admits an application that the physical counter or paper form would refuse.

#### 3. Full-Lifecycle System Synchronization (Status Credentials, SMS Gateway, & RTPS Deemed Approval)
* **Decision:** Submission via an AI assistant does not leave the citizen stranded in a proprietary chat transcript. The submission tool atomically registers a portal tracking account in `portal_users` (password: DOB as `DDMMYYYY`), saves an official age-proof document in the uploads repository, writes an auditable row to `audit_log`, and triggers real-time carrier dispatch via the simulated SMS gateway.
* **Why it mattered:** Elderly citizens share phones, sit at rural kiosks, and rely on family members. If the assistant fails or the chat ends, the applicant can track their case at `/status` or download their legal PDF acknowledgment (`/ack/<id>.pdf`). Crucially, agent-submitted applications seamlessly enter the statutory 15-day timeline under the Purvanchal Right to Public Services (RTPS) Act, standing automatically `DEEMED_APPROVED` if unreviewed within the legal SLA.

---

### The One Decision We Would Make Differently With More Time

#### Asynchronous Multimodal Document Verification with Discrepancy Scoring
* **What we would change:** Currently, the Citizen MCP allows agents to upload base64-encoded document bytes or generates an official age-proof verification certificate if only document metadata is supplied.
* **The improved approach:** With additional time, we would build an asynchronous multimodal verification sidecar for the Block Officer Assistant. When a rural citizen uploads a smartphone photograph of an Assamese/Bengali physical Voter ID or handwritten Jan Dhan passbook, an in-container OCR pipeline would extract the printed name, father's/husband's name, DOB, and IFSC, and present the officer with a side-by-side **Discrepancy Score**:
  * *Green:* Optical text matches form fields exactly.
  * *Amber/Red:* Name transliteration divergence or age mismatch (e.g. card indicates 1968, form claimed 1960).
* **Why:** In rural India, discrepancies between phonetically spelled vernacular names and English bank records cause high rejection rates. Giving the officer assistant an evidence-backed discrepancy assistant would accelerate reviews while preserving human civil service discretion.
