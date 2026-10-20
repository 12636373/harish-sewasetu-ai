# Sewa Setu: Agent-Ready Public Pension Delivery
## Loom Walkthrough Script (3 Minutes &middot; Face and Screen)
**Author:** Build for Bharat AI Fellow  
**Target Audience:** IAS Director, Department of Social Welfare, Government of Purvanchal & Review Committee

---

### Video Setup Checklist
- **Format:** Loom with Webcam (bottom corner, face visible) + Screen recording.
- **Tabs to Pre-open:**
  1. `http://localhost:8000/eval-dashboard` (The Evaluation Dashboard)
  2. `http://localhost:8000/mcp/citizen` and `http://localhost:8000/mcp/officer`
  3. `http://localhost:8000/admin` (Departmental Portal)
  4. `http://localhost:8000/__gateway/` (SMS Gateway Console)
  5. Terminal showing Claude Code / MCP client connectivity

---

### Timed Script & Stage Directions

#### [0:00 – 0:35] Introduction & The Core Problem
* **Camera / Screen:** Face on camera; screen shows the Sewa Setu portal home page and Director's briefing.
* **Spoken Script:**
  > *"Namaskar Director Ma'am and fellow team members. In your audio note, you shared a poignant story from Sonari block: a 70-year-old grandmother and her grandson on a bus, trying to use an AI assistant to apply for her ₹250 monthly pension, only for it to fail because the assistant couldn't talk to our portal and gave outdated guidelines.
  >
  > Over the past two days, I re-imagined Sewa Setu for an agentic world. We didn't build a demo toy; we built two standards-compliant Model Context Protocol (MCP) servers over streamable HTTP, directly wired into our 100k-record database, our OAuth 2.1 authorization server, and the Purvanchal Right to Public Services statutory timeline."*

---

#### [0:35 – 1:20] Architecture & Design Decisions Across Two MCPs
* **Screen:** Switch to `/mcp/citizen` and `/mcp/officer` tabs, highlighting endpoint separation.
* **Spoken Script:**
  > *"Our primary design principle was **strict privilege bifurcation**:
  >
  > 1. **Citizen MCP (`/mcp/citizen`):** Authenticated with scope `citizen` tied to the citizen's mobile. It exposes applicant tools: checking eligibility, submitting an application, tracking status, and withdrawing a pending application. It does not even possess the schemas of officer tools.
  > 2. **Block Officer MCP (`/mcp/officer`):** Accessible only with scope `officer`. It provides queue inspection, compliance validation, and approve/reject actions.
  >
  > Both endpoints implement RFC 9728 Protected Resource Metadata, allowing real MCP clients like Claude Code to discover our OAuth server, prompt the user for OTP or admin login, and authenticate with RS256 Bearer tokens.
  >
  > Crucially, our portal remains the single source of truth: whether submitted by paper or through Claude, every application goes through `validate_application()` in Python and PostgreSQL. The AI cannot hallucinate a pass for an underage applicant or create duplicate active applications."*

---

#### [1:20 – 2:20] The Personas, Evaluations & Live Database Invariants
* **Screen:** Switch to `/eval-dashboard`. Scroll through the summary metrics (100% pass rate) and persona dossiers.
* **Spoken Script:**
  > *"To test this rigorously, I sat at the block office counter in my head and invented 7 distinct, authentic citizen personas, each with a specific name, age, block, and legal database contract:
  >
  > - **Phuleswari Saikia (Age 71, Sonari):** Grandson Bikash applies from the bus. The assistant checks eligibility and submits the application. In our database, a PENDING row is created, a `portal_users` account is generated with her DOB password hash, and an SMS is dispatched.
  > - **Bhabani Prasad Sarma (Age 58, Namti):** A retired tea garden worker who insists on applying. The assistant politely refuses, calculating the exact date he turns 60. The database confirms zero rows were inserted—preventing LLM policy bypass!
  > - **Moina Begum (Age 64, Rajapara):** Tests duplicate prevention when a CSC operator attempts to re-apply for an existing case. The assistant discovers her active case and reports her remaining SLA days.
  > - **Hemanta Konwar (Age 68, Khelua):** An elderly farmer who entered the wrong bank details. He withdraws his pending case via the assistant and re-applies afresh.
  > - **Lilabati Devi & Dambaru Gogoi:** We tested end-to-end multi-agent workflows. The citizen submits, and the officer assistant reviews the compliance checks, approving Lilabati with mandatory recorded remarks and rejecting Dambaru's unreadable scan while unblocking his mobile for future re-application.
  > - **Padmini Das (Age 75, Sonari):** Demonstrates statutory deemed approval under the RTPS Act after 15 days of bureaucratic delay."*

---

#### [2:20 – 2:50] What Our Evals Found & What We Changed
* **Screen:** Highlight the green 'What We Learned & Changed' callout boxes on `/eval-dashboard`.
* **Spoken Script:**
  > *"What did these evaluations teach us?
  >
  > First, our initial prototype crashed when generating PDF certificates due to Unicode em-dashes in standard Helvetica font streams. Our evals caught this immediately, prompting us to sanitize font streams for robust document generation.
  >
  > Second, we learned that elderly citizens frequently share phones and misplace acknowledgment slips. Instead of stranding them in an ephemeral chat, our assistant automatically provisions their status-portal account so they can check `/status` anytime using their date of birth.
  >
  > Third, for officers, we made justification notes strictly mandatory in `approve_application` and `reject_application` so no administrative action occurs without auditable legal accountability."*

---

#### [2:50 – 3:00] Conclusion & Live Deployment
* **Screen:** Click 'Run All Evaluations Now' button showing live execution, then show GitHub repo and deployment link.
* **Spoken Script:**
  > *"Everything you see here is running live in Docker containers with 100,000 production records. The private GitHub repo `sewasetu-assistant` with full commit history has been shared with harshnisar, and our endpoints stand ready for Claude Code to test.
  >
  > Thank you for this inspiring challenge—we have made Sewa Setu truly agent-ready for the citizens of Purvanchal."*
