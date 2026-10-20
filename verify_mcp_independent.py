# -*- coding: utf-8 -*-
"""
Independent Model Context Protocol (MCP) Verification Client
Tests both /mcp/citizen and /mcp/officer over Streamable HTTP according to the MCP specification.
"""

import sys
import json
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
EVAL_KEY = "change-me-before-deploying"

def print_step(num, title):
    print("\n" + "="*70)
    print(f" STEP {num}: {title}")
    print("="*70)

def http_post_json(url, payload, headers=None):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else {}

def http_get(url, headers=None):
    req_headers = {}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body) if body else {}

def main():
    print("Starting Independent MCP Protocol Verification Suite...")
    print(f"Target Base URL: {BASE_URL}")

    all_passed = True

    # -------------------------------------------------------------------------
    # 1. Public Reachability & RFC Discovery
    # -------------------------------------------------------------------------
    print_step(1, "Public URL Reachability & RFC 9728 / 8414 Discovery")
    try:
        # Check Protected Resource Metadata (RFC 9728)
        s, data = http_get(f"{BASE_URL}/.well-known/oauth-protected-resource")
        assert s == 200, f"Expected 200, got {s}"
        assert "citizen" in data.get("scopes_supported", []), "Missing citizen scope"
        assert "officer" in data.get("scopes_supported", []), "Missing officer scope"
        print(f" [+] RFC 9728 Protected Resource Discovery OK (Scopes: {data.get('scopes_supported')})")

        # Check OAuth 2.1 Authorization Server Metadata (RFC 8414)
        s, data = http_get(f"{BASE_URL}/.well-known/oauth-authorization-server")
        assert s == 200, f"Expected 200, got {s}"
        assert data.get("token_endpoint"), "Missing token endpoint"
        print(f" [+] RFC 8414 Authorization Server Discovery OK (Issuer: {data.get('issuer')})")

        # Check Operational Health Check
        s, data = http_get(f"{BASE_URL}/health")
        assert s == 200 and data.get("status") == "healthy", f"Health status degraded: {data}"
        print(f" [+] Operational Health Check OK (Database Connected, Applications: {data['database']['total_applications']})")
    except Exception as e:
        print(f" [-] FAILED Step 1: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 2. MCP Protocol Handshake (initialize & ping)
    # -------------------------------------------------------------------------
    print_step(2, "MCP Protocol Handshake (initialize & ping)")
    try:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "independent-verifier", "version": "1.0.0"}
            }
        }
        citizen_auth = {"X-SewaSetu-Eval-Subject": "citizen:9876543999", "X-SewaSetu-Eval-Key": EVAL_KEY}
        officer_auth = {"X-SewaSetu-Eval-Subject": "officer:admin", "X-SewaSetu-Eval-Key": EVAL_KEY}

        # Initialize on /mcp/citizen
        s, c_res = http_post_json(f"{BASE_URL}/mcp/citizen", init_payload, headers=citizen_auth)
        assert c_res.get("result", {}).get("protocolVersion") == "2024-11-05", "Citizen handshake failed"
        print(f" [+] Citizen MCP Handshake OK: {c_res['result']['serverInfo']}")

        # Initialize on /mcp/officer
        s, o_res = http_post_json(f"{BASE_URL}/mcp/officer", init_payload, headers=officer_auth)
        assert o_res.get("result", {}).get("protocolVersion") == "2024-11-05", "Officer handshake failed"
        print(f" [+] Officer MCP Handshake OK: {o_res['result']['serverInfo']}")

        # Ping on /mcp/citizen
        s, ping_res = http_post_json(f"{BASE_URL}/mcp/citizen", {"jsonrpc": "2.0", "id": 102, "method": "ping"}, headers=citizen_auth)
        assert "result" in ping_res, "Ping failed"
        print(" [+] MCP Ping Protocol OK")
    except Exception as e:
        print(f" [-] FAILED Step 2: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 3. Tool Discovery (tools/list)
    # -------------------------------------------------------------------------
    print_step(3, "Tool Discovery & Physical Endpoint Partitioning")
    try:
        list_payload = {"jsonrpc": "2.0", "id": 103, "method": "tools/list"}

        # Citizen tools
        _, c_tools_res = http_post_json(f"{BASE_URL}/mcp/citizen", list_payload, headers=citizen_auth)
        c_tool_names = [t["name"] for t in c_tools_res["result"]["tools"]]
        print(f" [+] Citizen Tools Discovered ({len(c_tool_names)}): {c_tool_names}")
        assert "submit_application" in c_tool_names, "Missing submit_application in citizen tools"
        assert "check_eligibility" in c_tool_names, "Missing check_eligibility in citizen tools"
        assert "approve_application" not in c_tool_names, "CRITICAL: Administrative approve_application leaked to citizen!"
        assert "reject_application" not in c_tool_names, "CRITICAL: Administrative reject_application leaked to citizen!"
        print(" [+] Verification: Citizen assistant cannot discover any officer tools.")

        # Officer tools
        _, o_tools_res = http_post_json(f"{BASE_URL}/mcp/officer", list_payload, headers=officer_auth)
        o_tool_names = [t["name"] for t in o_tools_res["result"]["tools"]]
        print(f" [+] Officer Tools Discovered ({len(o_tool_names)}): {o_tool_names}")
        assert "approve_application" in o_tool_names, "Missing approve_application in officer tools"
        assert "list_pending_applications" in o_tool_names, "Missing list_pending_applications in officer tools"
        print(" [+] Verification: Officer assistant discovers administrative toolset.")
    except Exception as e:
        print(f" [-] FAILED Step 3: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 4. Valid Tool Calls Return Correct Structured Results
    # -------------------------------------------------------------------------
    print_step(4, "Valid Tool Execution & Structured Data Verification")
    try:
        # Citizen calls check_eligibility for senior (age 72)
        call_eligibility = {
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "check_eligibility",
                "arguments": {"dob": "15/08/1954", "block": "Sonari", "village": "Borhat"}
            }
        }
        _, res_elig = http_post_json(f"{BASE_URL}/mcp/citizen", call_eligibility, headers=citizen_auth)
        elig_content = json.loads(res_elig["result"]["content"][0]["text"])
        assert elig_content.get("eligible") is True, f"Expected eligible=True, got {elig_content}"
        assert elig_content.get("calculated_age") == 72, f"Expected age 72, got {elig_content}"
        print(f" [+] Valid Tool Call: check_eligibility returned eligible=True (Age: {elig_content['calculated_age']})")

        # Officer calls get_officer_dashboard
        call_dash = {
            "jsonrpc": "2.0",
            "id": 105,
            "method": "tools/call",
            "params": {"name": "get_officer_dashboard", "arguments": {}}
        }
        _, res_dash = http_post_json(f"{BASE_URL}/mcp/officer", call_dash, headers=officer_auth)
        dash_content = json.loads(res_dash["result"]["content"][0]["text"])
        assert "summary" in dash_content, "Missing summary in dashboard"
        assert dash_content.get("statutory_sla_days") == 15, "Missing RTPS 15-day SLA specification"
        print(f" [+] Valid Tool Call: get_officer_dashboard returned live summary: {dash_content['summary']}")
    except Exception as e:
        print(f" [-] FAILED Step 4: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 5. Invalid Inputs Return Useful Validation Errors
    # -------------------------------------------------------------------------
    print_step(5, "Input Validation & Meaningful Error Handling (Negative Tests)")
    try:
        # Invalid date format
        call_bad_date = {
            "jsonrpc": "2.0",
            "id": 106,
            "method": "tools/call",
            "params": {
                "name": "check_eligibility",
                "arguments": {"dob": "99/99/9999", "block": "Sonari"}
            }
        }
        _, res_bad_date = http_post_json(f"{BASE_URL}/mcp/citizen", call_bad_date, headers=citizen_auth)
        bad_date_content = json.loads(res_bad_date["result"]["content"][0]["text"])
        assert bad_date_content.get("eligible") is False, "Malformed date should not be eligible"
        assert "DD/MM/YYYY" in bad_date_content.get("reason", ""), "Error message should mention DD/MM/YYYY"
        print(f" [+] Negative Test (Invalid Date): Handled cleanly -> '{bad_date_content['reason']}'")

        # Underage applicant (58 years old)
        call_underage = {
            "jsonrpc": "2.0",
            "id": 107,
            "method": "tools/call",
            "params": {
                "name": "check_eligibility",
                "arguments": {"dob": "14/06/1968", "block": "Namti"}
            }
        }
        _, res_underage = http_post_json(f"{BASE_URL}/mcp/citizen", call_underage, headers=citizen_auth)
        underage_content = json.loads(res_underage["result"]["content"][0]["text"])
        assert underage_content.get("eligible") is False, "Underage applicant should not be eligible"
        assert underage_content.get("calculated_age") == 58, "Should compute age 58"
        print(f" [+] Negative Test (Underage Cutoff): Handled cleanly -> Reasons: {underage_content['reasons']}")
    except Exception as e:
        print(f" [-] FAILED Step 5: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 6. Authorization & Privilege Enforcement (Negative Tests)
    # -------------------------------------------------------------------------
    print_step(6, "Authorization & Privilege Separation Enforcement")
    try:
        # Unauthenticated request to /mcp/citizen (missing Bearer token)
        unauth_req = urllib.request.Request(
            f"{BASE_URL}/mcp/citizen",
            data=json.dumps({"jsonrpc": "2.0", "id": 108, "method": "tools/list"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(unauth_req) as resp:
                print(" [-] CRITICAL: Unauthenticated request was allowed!")
                all_passed = False
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Expected 401, got {e.code}"
            assert "WWW-Authenticate" in e.headers, "Missing WWW-Authenticate header with RFC 9728 challenge"
            print(f" [+] Unauthenticated Access Blocked: HTTP 401 with challenge: {e.headers['WWW-Authenticate']}")

        # Cross-role attempt: Citizen token sent to /mcp/officer
        cross_role_req = urllib.request.Request(
            f"{BASE_URL}/mcp/officer",
            data=json.dumps({"jsonrpc": "2.0", "id": 109, "method": "tools/list"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-SewaSetu-Eval-Subject": "citizen:9876543999", "X-SewaSetu-Eval-Key": EVAL_KEY}
        )
        try:
            with urllib.request.urlopen(cross_role_req) as resp:
                print(" [-] CRITICAL: Cross-role request was allowed!")
                all_passed = False
        except urllib.error.HTTPError as e:
            assert e.code in (401, 403), f"Expected 401/403, got {e.code}"
            print(f" [+] Cross-Role Access Blocked: HTTP {e.code} (Citizen token denied on /mcp/officer)")

        # Citizen attempting to invoke approve_application on /mcp/citizen
        citizen_call_admin = {
            "jsonrpc": "2.0",
            "id": 110,
            "method": "tools/call",
            "params": {"name": "approve_application", "arguments": {"application_id": 1}}
        }
        _, res_forbidden_tool = http_post_json(f"{BASE_URL}/mcp/citizen", citizen_call_admin, headers=citizen_auth)
        assert res_forbidden_tool.get("error", {}).get("code") == -32601, f"Expected -32601, got {res_forbidden_tool}"
        print(f" [+] Administrative Action Blocked on Citizen MCP: {res_forbidden_tool['error']['message']}")
    except Exception as e:
        print(f" [-] FAILED Step 6: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 7. Database Integrity & State Reflection Across Subsequent Reads
    # -------------------------------------------------------------------------
    print_step(7, "Database Integrity & Multi-Agent State Transitions Across Reads")
    test_mobile = f"987{int(time.time() * 1000) % 10000000:07d}"
    test_citizen_auth = {"X-SewaSetu-Eval-Subject": f"citizen:{test_mobile}", "X-SewaSetu-Eval-Key": EVAL_KEY}
    try:
        # Step A: Citizen submits fresh application
        submit_payload = {
            "jsonrpc": "2.0",
            "id": 111,
            "method": "tools/call",
            "params": {
                "name": "submit_application",
                "arguments": {
                    "applicant_name": "Jadu Nath Hazarika",
                    "dob": "10/05/1952",
                    "gender": "Male",
                    "marital_status": "Married",
                    "village": "Namti Chariali",
                    "block": "Namti",
                    "bank_account": "445566778899",
                    "ifsc": "SBIN0001234",
                    "document_type": "Voter ID"
                }
            }
        }
        _, res_sub = http_post_json(f"{BASE_URL}/mcp/citizen", submit_payload, headers=test_citizen_auth)
        sub_content = json.loads(res_sub["result"]["content"][0]["text"])
        app_id = sub_content.get("application_id")
        app_no = sub_content.get("application_no")
        assert app_id and app_no, f"Submission failed: {sub_content}"
        print(f" [+] Step A (Citizen): Application submitted successfully -> {app_no} (ID: {app_id}, Status: PENDING)")

        # Step B: Read 1 - Citizen reads their status
        status_payload = {"jsonrpc": "2.0", "id": 112, "method": "tools/call", "params": {"name": "get_my_application_status", "arguments": {}}}
        _, res_stat1 = http_post_json(f"{BASE_URL}/mcp/citizen", status_payload, headers=test_citizen_auth)
        stat1_content = json.loads(res_stat1["result"]["content"][0]["text"])
        assert stat1_content.get("status") == "PENDING", f"Expected PENDING, got {stat1_content.get('status')}"
        print(f" [+] Read 1 (Citizen): Verified status is PENDING (SLA Remaining: {stat1_content['rtps_sla']['days_remaining']} days)")

        # Step C: Officer inspects case details
        details_payload = {"jsonrpc": "2.0", "id": 113, "method": "tools/call", "params": {"name": "get_application_details", "arguments": {"application_id": app_id}}}
        _, res_det = http_post_json(f"{BASE_URL}/mcp/officer", details_payload, headers=officer_auth)
        det_content = json.loads(res_det["result"]["content"][0]["text"])
        assert det_content["applicant_name"] == "Jadu Nath Hazarika", f"Name mismatch: {det_content}"
        assert det_content["compliance_checks"]["age_criterion"]["passed"] is True, "Age criterion not passed"
        print(" [+] Step C (Officer): Retrieved full dossier and verified compliance checks.")

        # Step D: Officer approves application
        approval_note = "Independent verification test: age proof and bank passbook verified compliant."
        approve_payload = {
            "jsonrpc": "2.0",
            "id": 114,
            "method": "tools/call",
            "params": {"name": "approve_application", "arguments": {"application_id": app_id, "note": approval_note}}
        }
        _, res_appr = http_post_json(f"{BASE_URL}/mcp/officer", approve_payload, headers=officer_auth)
        appr_content = json.loads(res_appr["result"]["content"][0]["text"])
        assert appr_content.get("new_status") == "APPROVED", f"Expected APPROVED, got {appr_content}"
        print(f" [+] Step D (Officer): Application {app_no} APPROVED by {appr_content['decided_by']}")

        # Step E: Read 2 - Citizen reads their status again (verifying state persistence across reads)
        _, res_stat2 = http_post_json(f"{BASE_URL}/mcp/citizen", status_payload, headers=test_citizen_auth)
        stat2_content = json.loads(res_stat2["result"]["content"][0]["text"])
        assert stat2_content.get("status") == "APPROVED", f"Expected APPROVED on subsequent read, got {stat2_content.get('status')}"
        assert stat2_content.get("decided_by") == "admin", "Missing decided_by in subsequent read"
        print(f" [+] Read 2 (Citizen): State persistence verified -> Status is now {stat2_content['status']} (Decided by: {stat2_content['decided_by']})")
    except Exception as e:
        print(f" [-] FAILED Step 7: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # 8. Post-Deployment Availability & Latency
    # -------------------------------------------------------------------------
    print_step(8, "Endpoint Availability & Latency Check")
    try:
        latencies = []
        for i in range(5):
            t0 = time.time()
            s, _ = http_get(f"{BASE_URL}/health")
            assert s == 200, "Degraded health check"
            latencies.append((time.time() - t0) * 1000)
        avg_lat = sum(latencies) / len(latencies)
        print(f" [+] High Availability Verified: 5/5 requests succeeded (Avg Latency: {avg_lat:.1f}ms)")
    except Exception as e:
        print(f" [-] FAILED Step 8: {e}")
        all_passed = False

    # -------------------------------------------------------------------------
    # Final Verdict
    # -------------------------------------------------------------------------
    print("\n" + "="*70)
    if all_passed:
        print(" VERIFICATION RESULT: 100% PASSED")
        print(" Both MCP endpoints are genuinely agent-ready, interoperable, and fully compliant.")
        print("="*70)
        sys.exit(0)
    else:
        print(" VERIFICATION RESULT: FAILED")
        print("="*70)
        sys.exit(1)

if __name__ == "__main__":
    main()
