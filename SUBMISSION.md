# Build for Bharat Challenge: Sewa Setu — Submission Form Reference

Use this document to complete your Public Tech Challenge submission form. Replace placeholder hostnames (e.g., `https://your-domain-or-ip`) with your live deployed URL.

---

### 1. Seva Setu Portal URL
```text
https://<YOUR-DOMAIN-OR-IP>
```
*(e.g., `https://sewasetu.yourdomain.com` or `http://<SERVER-IP>:8000`)*

---

### 2. Public MCP Endpoint for Citizen
```text
https://<YOUR-DOMAIN-OR-IP>/mcp/citizen
```
*Description:*  
Streamable HTTP JSON-RPC 2.0 / SSE endpoint exposing applicant tools: `get_scheme_information`, `check_eligibility`, `get_my_application_status`, `submit_application`, `withdraw_application`, and `download_acknowledgment`. Authenticated via Bearer token (OAuth 2.1 scope `citizen`).

---

### 3. Public MCP Endpoint for Administrators (Block Officer)
```text
https://<YOUR-DOMAIN-OR-IP>/mcp/officer
```
*Description:*  
Streamable HTTP JSON-RPC 2.0 / SSE endpoint exposing administrative tools: `get_officer_dashboard`, `list_pending_applications`, `get_application_details`, `approve_application`, `reject_application`, and `search_applications`. Authenticated via Bearer token (OAuth 2.1 scope `officer` or program token from `/admin/tokens`).

---

### 4. Eval Dashboard URL
```text
https://<YOUR-DOMAIN-OR-IP>/eval-dashboard
```
*Description:*  
Live interactive evaluation dashboard running 7 realistic citizen and officer personas against the live 100,000-row PostgreSQL database, asserting state invariants post-conversation. Features real-time rerun execution via `/api/evals/run` and detailed turn-by-turn audit logs.

---

### 5. Private GitHub Repository URL
```text
https://github.com/<YOUR-GITHUB-USERNAME>/sewasetu-assistant
```
*Important:*  
- Keep the repository **private**.
- Invite **`harshnisar`** as a collaborator with read-only access (Settings > Collaborators > Add people).
- Full git commit history is preserved across all development milestones (no squashed commits).

---

### 6. Departmental Administrator Credentials (for Evaluators)
- **Login URL:** `https://<YOUR-DOMAIN-OR-IP>/admin`
- **Username:** `admin`
- **Password:** `<YOUR_ADMIN_PASSWORD>` *(defined in your `.env` file)*

---

### 7. Protected Resource & OAuth Discovery Endpoints
- **RFC 9728 Protected Resource Metadata:** `https://<YOUR-DOMAIN-OR-IP>/.well-known/oauth-protected-resource`
- **RFC 8414 Authorization Server Metadata:** `https://<YOUR-DOMAIN-OR-IP>/.well-known/oauth-authorization-server`
- **Operational Health Check:** `https://<YOUR-DOMAIN-OR-IP>/health`
- **Simulated SMS Gateway:** `https://<YOUR-DOMAIN-OR-IP>/__gateway/`

---

### 8. Accompanying Artifacts Included in Repository
1. **Design Note:** [`DESIGN-NOTE.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/DESIGN-NOTE.md)  
   *Covers the 3 decisions that mattered most (physical MCP endpoint partitioning, live DB post-condition invariant evals, and stateless RS256 token validation with session boundaries) and the 1 decision we would make differently with more time (asynchronous human-in-the-loop task escalation queues).*
2. **Loom Video Script:** [`LOOM-SCRIPT.md`](file:///c:/Users/haris/OneDrive/Desktop/CODE/sewasetu-ai-handout/LOOM-SCRIPT.md)  
   *Turn-by-turn 3-minute timed script for the Director's Loom walk-through (face and screen).*
3. **Stand-alone Repository Archive:** `sewasetu-assistant.zip`  
   *Full codebase bundle with `.git` history intact.*
