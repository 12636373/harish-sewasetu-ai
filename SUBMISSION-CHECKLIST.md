# Sewa Setu: Official Challenge Submission Checklist
**Public Tech Challenge: "Sewa Setu, agent-ready"**
*Department of Social Welfare, Government of Purvanchal*

---

## 1. Submission Deliverables Summary

| Deliverable | Required Field / Location | Status | Details |
| :--- | :--- | :--- | :--- |
| **Citizen Portal URL** | Application Form | **READY** | `http://<VM-IP>:8000/` or local `http://localhost:8000/` |
| **Citizen MCP Endpoint** | Application Form | **READY** | `http://<VM-IP>:8000/mcp/citizen` (Streamable HTTP / SSE, Scope: `citizen`) |
| **Officer MCP Endpoint** | Application Form | **READY** | `http://<VM-IP>:8000/mcp/officer` (Streamable HTTP / SSE, Scope: `officer`) |
| **Officer Login Credentials** | Application Form (Secure field) | **READY** | Username: `admin`, Password: *(configured via `ADMIN_PASSWORD` in `.env`)* |
| **Private GitHub Repository** | `https://github.com/12636373/harish-sewasetu-ai` | **READY** | Full atomic commit history preserved across all phases |
| **GitHub Collaborator Invite** | Read access to `harshnisar` | **ACTION REQUIRED BY USER** | Go to GitHub Settings $\rightarrow$ Collaborators $\rightarrow$ Add `harshnisar` |
| **Evaluation Dashboard URL** | Application Form | **READY** | `http://<VM-IP>:8000/eval-dashboard` (12 personas, 100% pass rate) |
| **Standalone ZIP Archive** | Archive including `.git` folder | **READY** | Instructions in Section 2 below |
| **3-Minute Loom Video** | Public/Unlisted Loom link | **ACTION REQUIRED BY USER** | Record using [`DEMO-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DEMO-SCRIPT.md) (face and screen) |
| **One-Page Design Note** | [`DESIGN-NOTE.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DESIGN-NOTE.md) | **READY** | The 3 decisions that mattered most, and the 1 decision with more time |

---

## 2. Standalone Repository ZIP Packaging

To package the entire repository including full `.git` commit history:

### In PowerShell (Windows):
```powershell
# Navigate to the parent directory of your project
cd C:\Users\haris\OneDrive\Desktop\CODE

# Create the submission zip archive including .git history
Compress-Archive -Path "sewasetu-ai-handout\*" -DestinationPath "sewasetu-assistant.zip" -Force
```

### In Linux / Bash:
```bash
zip -r sewasetu-assistant.zip sewasetu-assistant -x "sewasetu-assistant/.venv/*" "sewasetu-assistant/__pycache__/*"
```

---

## 3. Pre-Flight Verification Checklist

- [x] **Dual MCP Endpoints Running:** Verified `/mcp/citizen` and `/mcp/officer` respond to JSON-RPC 2.0 `POST` and SSE `GET`.
- [x] **Privilege Separation:** Automated tests confirm citizen tokens receive `401/403` on `/mcp/officer`, and citizen catalog has zero officer tools.
- [x] **OAuth 2.1 & RFC 9728:** Endpoint-specific protected-resource metadata (`/mcp/citizen` advertises only `citizen`; `/mcp/officer` advertises only `officer`).
- [x] **Token Exchange Fix:** SQLite timestamp string deserialization resolved; token minting, PKCE, and refresh tested.
- [x] **12 Evaluation Personas:** All 12 personas execute over HTTP protocol with 100% database assertions passing on `/eval-dashboard`.
- [x] **Deterministic Government Rules:** Age $\ge 60$ in IST, 1 active app per mobile, 9-18 digit account, 11-char IFSC.
- [x] **SMS Gateway & Audit Trail:** Verified carrier dispatch at port 8025 and comprehensive `audit_log` rows.
- [x] **RTPS 15-Day SLA:** Automatic transition to `DEEMED_APPROVED` with decider `RTPS-AUTO`.
- [x] **Security Hardening:** Automatic fallback secret generation; zero plaintext passwords in chat or logs.
- [x] **Automated Test Suite:** 29/29 unit and integration tests passing (`pytest -q`).
- [x] **Independent Protocol Suite:** 8/8 protocol verification stages passing (`verify_mcp_independent.py`).
- [x] **OpenCode Real Client:** OpenCode 1.19.5 connected and authenticated via OAuth 2.1 (`opencode mcp list`).
- [x] **Pre-packaged Archive:** `sewasetu-assistant.zip` (37.86 MB) packaged with complete `.git` history.
