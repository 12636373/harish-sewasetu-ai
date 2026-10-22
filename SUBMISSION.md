# Build for Bharat Challenge: Sewa Setu — Assessment Form Submission Reference

> **Public Tech Challenge:** *Take Home — Seva Setu, agent-ready.*  
> **Role:** Build for Bharat Fellow (AI Track)  
> **Department:** Department of Social Welfare, Government of Purvanchal  
> **Assessment Form Guide:** Exact field-by-field values for final submission.

---

## 1. Official Assessment Form Fields

| Form Field | Value to Submit | Notes / Instructions |
| :--- | :--- | :--- |
| **Assignment understood** | `Yes` | Confirms full understanding of the IAS Director's brief and problem statement. |
| **Citizen MCP endpoint** | `https://<YOUR-DOMAIN-OR-IP>/mcp/citizen` | Streamable HTTP (JSON-RPC 2.0 `POST`) & SSE (`GET`) exposing 10 citizen tools with OAuth 2.1 scope `citizen`. |
| **Administrator MCP endpoint** | `https://<YOUR-DOMAIN-OR-IP>/mcp/officer` | Streamable HTTP & SSE exposing 10 staff tools with OAuth 2.1 scope `officer` and RS256 token verification. |
| **Seva Setu portal** | `https://<YOUR-DOMAIN-OR-IP>` | Live accessible web portal with senior citizen accessibility bar (`A- / A / A+`) and high contrast. |
| **Evaluation dashboard** | `https://<YOUR-DOMAIN-OR-IP>/eval-dashboard` | Live persona test runner verifying PostgreSQL invariants post-conversation (100% pass rate). |
| **GitHub repository** | `https://github.com/12636373/harish-sewasetu-ai` | Full atomic commit history. Public repository with comprehensive documentation. |
| **Repository ZIP** | Attach `sewasetu-assistant.zip` (26.33 MB) | Complete standalone bundle containing full `.git` history and all source files (verified in isolated test). |
| **Loom demonstration** | `https://www.loom.com/share/<YOUR_LOOM_ID>` | Publicly accessible video ($\le 3$ minutes) showing face and screen following [`LOOM-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/LOOM-SCRIPT.md). |
| **Deployment commitment** | `Yes` | Confirm you will actively maintain the deployment for 30 days after deadline until assessment completes. |
| **Optional scheme video** | `https://youtu.be/<YOUR_UNLISTED_ID>` | YouTube Unlisted video ($\le 2$ minutes) on *Mukhyamantri Gramin Sanjivani* following [`CM-SCHEME-VIDEO-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/CM-SCHEME-VIDEO-SCRIPT.md). |

---

## 2. Departmental Administrator Credentials (for Evaluators)

* **Admin Login URL:** `https://<YOUR-DOMAIN-OR-IP>/admin`
* **Username:** `admin`
* **Password:** `<YOUR_ADMIN_PASSWORD>` *(defined in your production `.env` file)*
* **Program Tokens Interface:** `https://<YOUR-DOMAIN-OR-IP>/admin/tokens` (for minting long-lived officer tokens)

---

## 3. Supplementary Discovery & Health Endpoints

* **RFC 9728 Protected Resource Metadata:** `https://<YOUR-DOMAIN-OR-IP>/.well-known/oauth-protected-resource`
* **RFC 8414 Authorization Server Metadata:** `https://<YOUR-DOMAIN-OR-IP>/.well-known/oauth-authorization-server`
* **JWKS Public Key Set:** `https://<YOUR-DOMAIN-OR-IP>/.well-known/jwks.json`
* **Operational Health Check:** `https://<YOUR-DOMAIN-OR-IP>/health`
* **Simulated SMS Gateway:** `https://<YOUR-DOMAIN-OR-IP>/__gateway/`

---

## 4. Key Documentation Included in Repository

1. [`DESIGN-NOTE.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DESIGN-NOTE.md): The 3 architectural decisions that mattered most + 1 decision for the future.
2. [`LOOM-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/LOOM-SCRIPT.md): Timed 3-minute script for the Loom technical walkthrough (screen + face).
3. [`CM-SCHEME-VIDEO-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/CM-SCHEME-VIDEO-SCRIPT.md): 2-minute pitch for *Mukhyamantri Gramin Sanjivani*.
4. [`DEPLOYMENT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DEPLOYMENT.md): Detailed cloud provisioning instructions for AWS, DigitalOcean, Hetzner, etc.
5. [`verify_mcp_independent.py`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/verify_mcp_independent.py): Standalone 8-step independent MCP verification test suite.
