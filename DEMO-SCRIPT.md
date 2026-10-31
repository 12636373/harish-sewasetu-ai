# Sewa Setu: Agent-Ready Public Pension Delivery
## 3-Minute Loom Video Script & Walkthrough
**Challenge:** "Seva Setu, agent-ready" — Build for Bharat AI Fellow
**Target Audience:** IAS Director, Department of Social Welfare, Government of Purvanchal & Review Committee

---

### Video Setup Checklist
- **Format:** Loom with Webcam (bottom corner, face visible) + Screen recording.
- **Duration:** Strictly $\le 3$ minutes (180 seconds).
- **Tabs to Pre-open:**
  1. `http://localhost:8000/eval-dashboard` (Evaluation Dashboard with 12 personas, 100% pass rate)
  2. `http://localhost:8000/` (Sewa Setu Citizen Portal)
  3. `http://localhost:8000/admin` (Block Officer Portal)
  4. `http://localhost:8025/` (PurvSMS Gateway Console)
  5. Terminal with `verify_mcp_independent.py` or MCP client connection

---

### Timed Script & Stage Directions

#### [0:00 – 0:35] Problem Context & The Director's Note
* **Camera / Screen:** Face on camera; screen shows the Sewa Setu portal home page and Director's briefing.
* **Spoken Script:**
  > *"Namaskar Director Ma'am and fellow team members. In your audio briefing, you shared a poignant story from Sonari block: a 70-year-old grandmother and her grandson on a bus, trying to use an AI assistant to apply for her ₹250 monthly pension, only for it to fail because the assistant gave outdated guidelines and couldn't talk to our portal.
  >
  > Over the past few days, I re-imagined Sewa Setu for an agent-ready world. We didn't build a disconnected chat demo; we implemented two standards-compliant Model Context Protocol (MCP) servers over streamable HTTP, directly wired into our 100,000-record database, our OAuth 2.1 authorization server, and the Purvanchal Right to Public Services statutory timeline."*

---

#### [0:35 – 1:15] Dual MCP Architecture & Cryptographic Role Separation
* **Screen:** Switch to `/mcp/citizen` and `/mcp/officer` discovery endpoints.
* **Spoken Script:**
  > *"Our primary architecture principle is **strict physical privilege bifurcation**:
  >
  > 1. **Citizen MCP (`/mcp/citizen`):** Authenticated with scope `citizen` tied to the citizen's mobile. It exposes 10 applicant tools—eligibility checking, submission, status tracking, grievance registration, and voluntary withdrawal. It contains zero administrative tools.
  > 2. **Block Officer MCP (`/mcp/officer`):** Accessible only with scope `officer`. It exposes administrative tools: queue review, compliance inspection, document verification, and approvals/rejections with mandatory justification.
  >
  > Both endpoints implement RFC 9728 Protected Resource Metadata. An external MCP client auto-discovers our OAuth server, prompts for citizen OTP or officer credentials, and receives an RS256 Bearer JWT token. Cross-role calls are strictly rejected with HTTP 401/403 at the protocol gate."*

---

#### [1:15 – 2:15] The 12 Personas, Live Evals & Database Invariants
* **Screen:** Switch to `/eval-dashboard`. Scroll through the summary metrics (12/12 passed, 100%) and persona dossiers.
* **Spoken Script:**
  > *"The Director specifically required real MCP conversations and post-condition database verification. On `/eval-dashboard`, we evaluate 12 authentic citizen personas covering clean, invalid, and adversarial cases:
  >
  > - **Phuleswari Saikia (Age 71, Sonari):** Grandson Bikash applies from the bus. The assistant checks eligibility and submits the application. In our database, a PENDING row is created, a `portal_users` account is generated with her DOB password hash, and an SMS is dispatched.
  > - **Bhabani Prasad Sarma (Age 58):** Insists on applying underage. The assistant politely refuses, calculating the exact date he turns 60. The database confirms zero rows were inserted—preventing policy bypass!
  > - **Subhasini Baruah & Hiren Chaliha:** Negative tests refusing invalid IFSC syntax (e.g. SBIN000) and truncated bank accounts, preventing financial routing failures.
  > - **Moina Begum & Minoti Gogoi:** Duplicate active application prevention and mandatory age-proof document enforcement.
  > - **Padmini Das (Age 75):** Demonstrates statutory 15-day deemed approval under the RTPS Act after bureaucratic delay.
  > - **Bireswar Roy:** Registers formal grievance GRV... with a statutory 7-day resolution window.
  > - **Ratul Sarma & Prabin Borah:** Adversarial IDOR and privilege escalation attempts—proving zero data leakage and total administrative isolation."*

---

#### [2:15 – 2:45] What Our Evals Taught Us & What We Changed
* **Screen:** Highlight the green 'What We Learned & Changed' callout boxes on `/eval-dashboard`.
* **Spoken Script:**
  > *"What did these evaluations teach us?
  >
  > 1. **Immediate Tracking Credentials:** Elderly citizens share phones and misplace slips. Auto-provisioning their portal login (DOB as DDMMYYYY) allows immediate tracking at `/status`.
  > 2. **Mandatory Administrative Accountability:** In `approve_application` and `reject_application`, plain-language notes are mandatory—ensuring no welfare decision occurs without legal accountability in `audit_log`.
  > 3. **Constructive Rejection:** Rejections unblock the citizen's mobile, allowing them to fix unreadable documents and re-apply without traveling 25 km to the block office."*

---

#### [2:45 – 3:00] Conclusion & Live Deployment
* **Screen:** Click 'Run All Evaluations Now' button showing live 100% execution, then show GitHub repository and live deployment URL.
* **Spoken Script:**
  > *"Everything here runs live in Docker with 100,000 production records. The private GitHub repo `sewasetu-assistant` with full atomic commit history has been shared with harshnisar, and our endpoints stand ready for testing.
  >
  > Thank you for this inspiring challenge—we have made Sewa Setu truly agent-ready for the senior citizens of Purvanchal."*
