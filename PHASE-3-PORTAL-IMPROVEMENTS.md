# Phase 3: Portal Fixes, Modernization & Accessibility Overhaul

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Deliverable:** Functional, Accessible Portal Powered by Live Backend Records

---

## 1. Executive Summary

Phase 3 focused on transforming the legacy, broken starter portal into a **high-reliability, highly accessible, and visually clean public welfare service**. 

Senior citizens in rural Purvanchal often face failing eyesight, physical tremors, low-end smartphones, and weak rural bandwidth. The redesigned portal prioritizes **clarity, strong contrast, intuitive navigation, and task completion over visual complexity**, backed by real-time validation against the 100,000-row PostgreSQL database.

---

## 2. Bug Fixes & Technical Remediation

| Issue ID | File / Component | Defect Found | Engineering Fix Applied | Live Verification |
| :---: | :--- | :--- | :--- | :---: |
| **FIX-01** | `app/mcp_server.py` | `FPDFException: Character "—" outside range for helveticaB` during receipt rendering. | Sanitized Unicode typography to ASCII-safe hyphen streams (`-`) before calling FPDF2 font rendering. | Stamped PDF acknowledgment generation verified without crashes. |
| **FIX-02** | `app/app.py` | Missing `jsonify` import in Flask web module. | Added `jsonify` to top-level Flask imports in `app/app.py`. | API endpoints (`/api/evals/run`, `/api/citizen-assistant`) return clean HTTP 200 JSON. |
| **FIX-03** | `app/app.py` & `scripts/deemed_approval.py` | Database connection parameters hardcoded to `app.ini`. | Updated `get_db()` to check `os.environ.get("POSTGRES_*")` with fallback to `app.ini`. | 12-factor cloud deployment verified; respects `.env` database overrides. |
| **FIX-04** | `docker-compose.yml` | Missing restart policies across services. | Added `restart: unless-stopped` to all 4 containers (`db`, `app`, `scheduler`, `smsgw`). | Stack recovers automatically across server reboots. |
| **FIX-05** | `docker-compose.yml` | Startup race condition between PostgreSQL seed loading and Gunicorn workers. | Configured `pg_isready` healthcheck on `db` and `condition: service_healthy` on `app` and `scheduler`. | Zero startup connection errors; database initialization fully synchronized. |
| **FIX-06** | `app/app.py` | Audit log column name mismatch (`timestamp` vs `at`). | Corrected SQL column select to `at` in audit log queries. | Case audit histories and status inquiries execute cleanly. |

---

## 3. UI/UX Redesign & Senior Citizen Accessibility

### 3.1 Legibility & Senior Accessibility Toolbar (`app/templates/base.html`)
* **Senior Accessibility Bar:**  
  A dedicated utility bar fixed to the top of the viewport offers one-click accessibility controls:
  * **Dynamic Font Scaling (`A- / A / A+`):** Scales page root typography ($90\%$, $100\%$, $115\%$) to accommodate elderly citizens with failing eyesight. User selection persists across pages and sessions via `localStorage`.
  * **High-Contrast Mode:** One-click toggle switching to true-black text (`#000000`), pure white surfaces, and bold $2\text{px}$ high-contrast borders for maximum outdoor legibility in rural village environments.
* **Modern Typography:** Standardized on the clean, open-source **Inter** typeface with explicit hierarchy and tabular numbers for financial figures.
* **Large Touch Targets:** Minimum $44\text{px}$ touch targets for all buttons and interactive elements with visible focus rings (`outline: 3px solid var(--accent)`) to prevent missed taps from physical tremors.

### 3.2 Responsive Layout Across Devices
* Fully responsive layout using CSS3 Grid and Flexbox.
* Cards adapt seamlessly from desktop ($920\text{px}$ max-width container) down to small mobile devices ($< 640\text{px}$) with proportional padding adjustments.
* Clean horizontal navigation on desktop with automatic flex wrapping and clean mobile tap targets.

### 3.3 Clear Visual Contrast & Status Badging
* Unambiguous, semantic color coding across the portal:
  * **Approved & Deemed Approved:** Emerald Green (`#059669`, `#ecfdf5`)
  * **Pending Review:** Amber / Warm Gold (`#d97706`, `#fffbeb`)
  * **Rejected:** Rose / Crimson (`#dc2626`, `#fef2f2`)
  * **Withdrawn:** Slate Gray (`#64748b`, `#f1f5f9`)

---

## 4. Implementation of Core Welfare Workflows

The portal supports **6 complete citizen and administrative workflows**, verified against the live PostgreSQL database:

```
                                  Sewa Setu Portal
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
  [1. Discovery]                   [2. Eligibility]                 [3. Application]
  - Scheme Rules                   - Age >= 60 Check                - Mobile OTP
  - ₹250/mo DBT                    - Block Jurisdiction             - Bank Account & IFSC
  - 15-day RTPS SLA                - Single Active App              - Age Proof Upload
        │                                │                                │
        └────────────────────────────────┼────────────────────────────────┘
                                         ▼
                                [4. Status Tracking]
                                - Mobile + DOB Password
                                - RTPS Countdown Timer
                                - Voluntary Withdrawal
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
  [5. Officer Review]                                           [6. Deemed Approval]
  - Filter Pending Queue                                        - 15-day SLA Expiry
  - Document Inspection                                         - Nightly Cron (02:00)
  - 1-Click Approve / Reject                                    - RTPS-AUTO Status
```

### Workflow 1: Scheme Discovery & Guidelines (`/` & `/about`)
* Clear, jargon-free summary of scheme benefits: $\text{₹}250/\text{month}$ disbursed directly into beneficiary bank accounts via Direct Benefit Transfer (DBT).
* Real-time countdown timer displaying remaining hours before the statutory application window closes.
* Explicit enumeration of the 6 recognized blocks: *Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua*.

### Workflow 2: Conversational AI-Assisted Eligibility Check (`/assistant`)
* Senior-friendly natural language assistant directly connected to portal database logic via `POST /api/citizen-assistant`.
* Ingests age or Date of Birth and verifies compliance with statutory rules.
* For underage applicants, it calculates the exact future date when they become eligible (e.g. 58-year-old applicant informed of eligibility on 14/06/2028).

### Workflow 3: Progressive Application Submission (`/apply`)
* **Step 1 (Mobile Verification):** Ingests 10-digit mobile number, generates 6-digit OTP, and dispatches via SMS gateway.
* **Step 2 (Personal Details):** Captures name, Date of Birth, gender, marital status, village, block, and active savings bank account + 11-digit IFSC.
* **Step 3 (Document Upload):** Ingests age proof (Voter ID, Aadhaar, Birth Certificate, School Record; max 5MB).
* **Step 4 (Preview & Stamped PDF Receipt):** Generates application number (`SSP26...`), provisions hashed status portal credentials, logs `SUBMIT` in `audit_log`, and downloads stamped receipt.

### Workflow 4: Citizen Status Tracking & Self-Service (`/status`)
* Accessible using the applicant's mobile number and Date of Birth password (`DDMMYYYY`).
* Displays current status, officer decision details, and days remaining under the 15-day statutory RTPS SLA.
* **Voluntary Withdrawal:** Citizens can voluntarily withdraw a pending application to fix mistakes, immediately unblocking their mobile number to re-apply.

### Workflow 5: Departmental Case Review & Decisions (`/admin`)
* Officer dashboard with breakdown by status and block jurisdiction.
* Overdue case warning banner alerting officers to applications approaching or exceeding the 15-day SLA.
* Comprehensive case dossier (`/admin/application/<id>`) displaying personal details, bank verification, and inline document viewer.
* **1-Click Approval:** Updates status to `APPROVED`, records officer remarks in `audit_log`, and dispatches approval SMS.
* **Structured Rejection:** Updates status to `REJECTED`, records mandatory defect notes in `audit_log`, sends explanatory SMS, and unblocks applicant phone.

### Workflow 6: Statutory RTPS 15-Day Deemed Approval
* Enforced by the nightly cron job (`scripts/deemed_approval.py`) running in the `scheduler` container.
* Automatically transitions applications pending $> 15$ days to `DEEMED_APPROVED` with `decided_by = 'RTPS-AUTO'`.

---

## 5. Live Backend Verification

All 6 workflows were executed and verified against the running containerized stack:

```bash
# 1. Operational Health Check
curl -s http://localhost:8000/health | jq .status
# Output: "healthy"

# 2. Automated Evaluation Suite Execution
curl -s -X POST http://localhost:8000/api/evals/run | jq .summary
# Output: {"failed_count": 0, "pass_rate_percentage": 100, "passed_count": 7, "total_personas": 7}

# 3. Independent MCP Protocol Verification
python verify_mcp_independent.py
# Output: VERIFICATION RESULT: 100% PASSED (8/8 Checks Succeeded)
```

* **Modernized & Accessible Portal:** Verified live at `http://localhost:8000`.
* **Full Git Commit History:** 15 atomic commits on branch `master`.
* **Permanent Deliverable:** [`PHASE-3-PORTAL-IMPROVEMENTS.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/PHASE-3-PORTAL-IMPROVEMENTS.md) committed to repository.
* **Submission Bundle:** `sewasetu-assistant.zip` (28.07 MB, full `.git` preserved).
