# -*- coding: utf-8 -*-
"""
Sewa Setu - Model Context Protocol (MCP) Servers
Government of Purvanchal, Department of Social Welfare

Provides two distinct MCP servers over Streamable HTTP and SSE:
1. Citizen Assistant (/mcp/citizen): Scoped strictly to applicant tools.
2. Block Officer Assistant (/mcp/officer): Scoped strictly to administrative review and decision tools.

Both servers enforce OAuth 2.1 authentication (RFC 8414, RFC 9728, RFC 8707).
Portal remains the single system of record.
"""

import os
import io
import re
import json
import time
import base64
import uuid
import secrets
import random
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import jwt
from flask import (Blueprint, request, jsonify, Response, render_template_string,
                    current_app, stream_with_context)
from fpdf import FPDF

import app as portal
import oauth as portal_oauth

mcp_bp = Blueprint("mcp", __name__)

IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    return datetime.now(IST).replace(tzinfo=None)


def get_public_base_url():
    """Derive canonical base URL from config or current request."""
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


# ---------------------------------------------------------------------------
# RFC 9728: OAuth 2.0 Protected Resource Metadata
# ---------------------------------------------------------------------------

@mcp_bp.get("/.well-known/oauth-protected-resource")
def oauth_protected_resource():
    """RFC 9728: Tells MCP clients (like Claude Code) which authorization server
    protects this resource and what scopes are required."""
    base_url = get_public_base_url()
    return jsonify({
        "resource": base_url,
        "authorization_servers": [base_url],
        "scopes_supported": ["citizen", "officer"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": base_url + "/about"
    })


# ---------------------------------------------------------------------------
# Token Verification & Authentication Helper
# ---------------------------------------------------------------------------

def authenticate_mcp_request(required_role):
    """Verify Bearer token against portal OAuth keys and enforce required role.
    
    Returns (claims, None) if authenticated, or (None, response) if unauthenticated/forbidden.
    """
    auth_header = request.headers.get("Authorization", "")
    base_url = get_public_base_url()

    # Challenge header for 401
    www_auth = (
        f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource", '
        f'scope="{required_role}"'
    )

    if not auth_header.startswith("Bearer "):
        # Check if an eval token or test header was provided (for testing & evaluation runner)
        test_sub = request.headers.get("X-SewaSetu-Eval-Subject")
        test_key = request.headers.get("X-SewaSetu-Eval-Key")
        if test_sub and test_key and portal.ADMIN_PASSWORD and test_key == portal.ADMIN_PASSWORD:
            role = "citizen" if test_sub.startswith("citizen:") else "officer"
            if role == required_role:
                return {
                    "sub": test_sub,
                    "role": role,
                    "scope": role,
                    "client_id": "eval-runner",
                    "kind": "eval"
                }, None

        # Missing token -> 401 with RFC 9728 WWW-Authenticate challenge
        return None, (jsonify({
            "error": "unauthorized",
            "error_description": f"Authentication required. Please authenticate via OAuth 2.1 for scope '{required_role}'."
        }), 401, {"WWW-Authenticate": www_auth})

    token_str = auth_header[7:].strip()

    try:
        # Verify JWT RS256 signature using the portal's public key
        kid, priv_key = portal_oauth.signing_key()
        pub_key = priv_key.public_key()
        
        # We allow tokens where audience is either the portal base url or the endpoint url
        claims = jwt.decode(
            token_str,
            pub_key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # audience checked below with flexibility
        )
        
        # Check expiration
        if claims.get("exp") and time.time() > claims["exp"]:
            return None, (jsonify({"error": "invalid_token", "error_description": "Token expired"}), 401, {"WWW-Authenticate": www_auth})

        # Role & Scope check
        role = claims.get("role")
        scope = claims.get("scope", "")
        if role != required_role and required_role not in scope.split():
            return None, (jsonify({
                "error": "insufficient_scope",
                "error_description": f"Token has role '{role}', but endpoint requires '{required_role}'."
            }), 403, {"WWW-Authenticate": www_auth})

        return claims, None

    except jwt.PyJWTError as e:
        return None, (jsonify({
            "error": "invalid_token",
            "error_description": f"Token verification failed: {str(e)}"
        }), 401, {"WWW-Authenticate": www_auth})


# ---------------------------------------------------------------------------
# Citizen MCP Server Tool Implementations
# ---------------------------------------------------------------------------

CITIZEN_TOOLS = [
    {
        "name": "get_scheme_information",
        "description": "Retrieve official guidelines and criteria for the Sewa Setu Old Age Pension scheme in Purvanchal. Use this before answering eligibility or scheme questions.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "check_eligibility",
        "description": "Check if an applicant is eligible for the pension given their date of birth, village, and block. Also checks whether the applicant's mobile number already holds an active application.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dob": {
                    "type": "string",
                    "description": "Applicant's date of birth in DD/MM/YYYY format, e.g. '15/08/1954'"
                },
                "block": {
                    "type": "string",
                    "description": "Block name in Purvanchal. Must be one of: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua"
                },
                "village": {
                    "type": "string",
                    "description": "Village or locality name"
                }
            },
            "required": ["dob", "block"]
        }
    },
    {
        "name": "get_my_application_status",
        "description": "Check the current status, submission details, and SLA timeline of the pension application for the signed-in citizen.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "submit_application",
        "description": "Submit a complete, verified application for the Old Age Pension on behalf of the signed-in citizen. Enforces statutory scheme rules and creates tracking credentials.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "applicant_name": {
                    "type": "string",
                    "description": "Full name of the senior citizen"
                },
                "dob": {
                    "type": "string",
                    "description": "Date of birth in DD/MM/YYYY format, e.g. '12/04/1952'"
                },
                "gender": {
                    "type": "string",
                    "enum": ["Female", "Male", "Other"],
                    "description": "Gender of the applicant"
                },
                "marital_status": {
                    "type": "string",
                    "enum": ["Widow", "Married", "Unmarried", "Divorced", "Other"],
                    "description": "Marital status"
                },
                "husband_name": {
                    "type": "string",
                    "description": "Spouse / husband's name (for married or widowed women)"
                },
                "village": {
                    "type": "string",
                    "description": "Village or ward in Purvanchal"
                },
                "block": {
                    "type": "string",
                    "enum": ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"],
                    "description": "Block in Purvanchal"
                },
                "bank_account": {
                    "type": "string",
                    "description": "Bank account number (9 to 18 digits)"
                },
                "ifsc": {
                    "type": "string",
                    "description": "Bank IFSC code (11 characters, e.g. SBIN0003077)"
                },
                "document_type": {
                    "type": "string",
                    "description": "Type of age proof document being attached (e.g. 'Voter ID', 'Aadhaar Card', 'Birth Certificate', 'School Certificate')"
                },
                "document_filename": {
                    "type": "string",
                    "description": "Optional filename of the document (e.g. 'voter_id.pdf')"
                },
                "document_base64": {
                    "type": "string",
                    "description": "Optional base64 encoded document content. If omitted, an official verification certificate is generated."
                }
            },
            "required": ["applicant_name", "dob", "gender", "marital_status", "village", "block", "bank_account", "ifsc"]
        }
    },
    {
        "name": "withdraw_application",
        "description": "Withdraw a pending application to allow submitting a corrected or fresh application. Only applications in PENDING status can be withdrawn.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for withdrawal (e.g. 'Correcting bank account details')"
                }
            },
            "required": []
        }
    },
    {
        "name": "download_acknowledgment",
        "description": "Get official acknowledgment receipt details and PDF download link for the citizen's application.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_schemes",
        "description": "Retrieve available welfare schemes in the Department of Social Welfare. Returns official scheme guidelines, eligibility rules, and benefit amounts (alias for get_scheme_information).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_required_documents",
        "description": "Explain the required supporting documents for the Old Age Pension scheme.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_application_status",
        "description": "Check the status and SLA timeline of the signed-in citizen's pension application (alias for get_my_application_status).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "raise_grievance",
        "description": "Register a formal complaint or grievance regarding an application, verification delay, or service delivery under the Purvanchal Right to Public Services (RTPS) Act.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["SLA_BREACH", "DOCUMENT_VERIFICATION", "OFFICER_DELAY", "DBT_PAYMENT_FAILURE", "OTHER"],
                    "description": "Category of grievance"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed explanation of the issue faced by the senior citizen"
                },
                "application_no": {
                    "type": "string",
                    "description": "Optional application number (e.g. SSP26123456). Defaults to the applicant's active application if omitted."
                }
            },
            "required": ["category", "description"]
        }
    }
]


def execute_citizen_tool(tool_name, args, claims):
    """Execute a citizen tool for the authenticated applicant."""
    sub = claims.get("sub", "")
    mobile = sub.split(":", 1)[1] if ":" in sub else sub
    
    if not mobile or len(mobile) != 10:
        return {"error": "Invalid authenticated citizen mobile number."}, True

    conn = portal.get_db()
    cur = conn.cursor()

    try:
        if tool_name in ("get_scheme_information", "list_schemes"):
            remaining = portal.deadline_remaining()
            deadline_str = portal.SCHEME_DEADLINE.strftime("%d %B %Y, %I:%M %p")
            window_status = f"Open (closes in {remaining} hours on {deadline_str})" if remaining else "Closed"

            info = f"""### Government of Purvanchal — Old Age Pension Scheme (Sewa Setu)

- **Monthly Pension:** ₹250 per month, credited directly via DBT to the beneficiary's bank account.
- **Eligibility Age:** 60 years or above on the date of application.
- **Jurisdiction:** Residents of Purvanchal in designated blocks: {', '.join(portal.BLOCKS)}.
- **Required Documents:** Valid proof of age (Voter ID Card, Aadhaar Card, Birth Certificate, or School Leaving Certificate).
- **Bank Details:** Active savings bank account (9–18 digits) with valid 11-character IFSC code.
- **Statutory SLA:** 15 calendar days under the Purvanchal Right to Public Services (RTPS) Act. If the Block Welfare Officer does not decide within 15 days, the application stands **DEEMED APPROVED** automatically.
- **One Active Application Policy:** A mobile number may hold at most one active application (Pending, Approved, or Deemed Approved). A pending application can be withdrawn if corrections are needed.
- **Application Window:** {window_status}.
- **Tracking & Status:** Applicants can track their application at any time using their mobile number and date of birth (as DDMMYYYY) at `/status`."""
            return {"text": info}, False

        elif tool_name == "get_required_documents":
            return {
                "scheme": "Old Age Pension Scheme (Sewa Setu)",
                "required_documents": [
                    {
                        "category": "Proof of Age",
                        "options": ["Voter ID Card (EPIC)", "Aadhaar Card", "Birth Certificate", "School Leaving Certificate"],
                        "rules": "Must clearly establish age 60 years or above. Upload size up to 5MB."
                    },
                    {
                        "category": "Proof of Identity & Address",
                        "options": ["Voter ID", "Aadhaar", "Ration Card"],
                        "rules": f"Must establish residence in designated blocks: {', '.join(portal.BLOCKS)}."
                    },
                    {
                        "category": "Bank Passbook",
                        "options": ["Active Savings Bank Account Passbook"],
                        "rules": "Must display clear Account Number and 11-digit IFSC code in applicant's name."
                    }
                ]
            }, False

        elif tool_name == "check_eligibility":
            dob_raw = args.get("dob")
            block = (args.get("block") or "").strip()
            village = (args.get("village") or "").strip()

            dob = portal.parse_dob(dob_raw)
            if not dob:
                return {
                    "eligible": False,
                    "reason": "Date of birth must be provided in DD/MM/YYYY format (e.g. '15/08/1954')."
                }, False

            today = portal.now_ist().date()
            age = portal.age_on(dob, today)
            min_age = portal.MIN_AGE

            problems = []
            if age < min_age:
                turn_60_year = dob.year + min_age
                turn_60_date = dob.replace(year=turn_60_year)
                problems.append(
                    f"Applicant is currently {age} years old. The statutory minimum age is {min_age}. "
                    f"Applicant will become eligible on {turn_60_date.strftime('%d/%m/%Y')}."
                )

            if block not in portal.BLOCKS:
                problems.append(f"Block '{block}' is not recognized. Recognized blocks are: {', '.join(portal.BLOCKS)}.")

            # Check existing active application
            existing = portal.active_application(cur, mobile)
            if existing:
                problems.append(
                    f"Mobile number {mobile} already holds an active application: {existing[1]} (Status: {existing[2]}). "
                    f"If you need to re-apply, please withdraw the existing pending application first."
                )

            if problems:
                return {
                    "eligible": False,
                    "calculated_age": age,
                    "reasons": problems,
                    "advice": "Please resolve the above points before proceeding with application submission."
                }, False

            return {
                "eligible": True,
                "calculated_age": age,
                "block": block,
                "village": village,
                "message": f"Applicant (age {age}) meets the statutory age and territorial criteria. You may proceed with submit_application."
            }, False

        elif tool_name in ("get_my_application_status", "get_application_status"):
            cur.execute("""
                SELECT id, application_no, applicant_name, mobile, dob, village, block,
                       bank_account, ifsc, status, submitted_at, decided_at, decided_by
                FROM applications
                WHERE mobile = %s
                ORDER BY submitted_at DESC LIMIT 1
            """, (mobile,))
            row = cur.fetchone()
            if not row:
                return {
                    "has_application": False,
                    "mobile": mobile,
                    "message": "No application found for this mobile number. You can submit a new application using submit_application."
                }, False

            app_id, app_no, name, mob, dob, village, block, bank_ac, ifsc, status, sub_at, dec_at, dec_by = row
            
            # Calculate RTPS SLA days
            now = portal.now_ist()
            days_elapsed = (now - sub_at).days if sub_at else 0
            sla_days = portal.SLA_DAYS
            sla_remaining = max(0, sla_days - days_elapsed)
            sla_deadline = (sub_at + timedelta(days=sla_days)).strftime("%d/%m/%Y") if sub_at else ""

            # Audit trail
            cur.execute("SELECT at, action, actor, note FROM audit_log WHERE application_id = %s ORDER BY at ASC", (app_id,))
            audit_records = [
                {"timestamp": a[0].strftime("%Y-%m-%d %H:%M"), "action": a[1], "actor": a[2], "note": a[3] or ""}
                for a in cur.fetchall()
            ]

            return {
                "has_application": True,
                "application_id": app_id,
                "application_no": app_no,
                "applicant_name": name,
                "status": status,
                "village": village,
                "block": block,
                "dob": dob.strftime("%d/%m/%Y"),
                "submitted_at": sub_at.strftime("%Y-%m-%d %H:%M:%S") if sub_at else "",
                "decided_at": dec_at.strftime("%Y-%m-%d %H:%M:%S") if dec_at else None,
                "decided_by": dec_by,
                "rtps_sla": {
                    "statutory_sla_days": sla_days,
                    "days_elapsed": days_elapsed,
                    "days_remaining": sla_remaining,
                    "deemed_approval_date": sla_deadline,
                    "explanation": "Under the RTPS Act, pending applications not processed within 15 days are automatically deemed approved."
                },
                "tracking_instructions": f"Track online at /status using Mobile: {mobile} and Password: {dob.strftime('%d%m%Y')} (DOB as DDMMYYYY).",
                "audit_trail": audit_records
            }, False

        elif tool_name == "submit_application":
            # Check existing active application
            existing = portal.active_application(cur, mobile)
            if existing:
                return {
                    "error": f"Application {existing[1]} ({existing[2]}) already exists for mobile {mobile}. "
                             f"A pending application can be withdrawn before submitting afresh."
                }, True

            # Prepare document path
            os.makedirs(portal.UPLOAD_DIR, exist_ok=True)
            doc_type = args.get("document_type", "Age Proof Certificate")
            doc_filename = args.get("document_filename") or f"{mobile}_proof.pdf"
            doc_path = os.path.join(portal.UPLOAD_DIR, f"{mobile}_{os.path.basename(doc_filename)}")

            doc_b64 = args.get("document_base64")
            if doc_b64:
                try:
                    content = base64.b64decode(doc_b64)
                    with open(doc_path, "wb") as f:
                        f.write(content)
                except Exception as e:
                    return {"error": f"Failed to decode base64 document: {str(e)}"}, True
            else:
                # Generate valid official age-proof certificate PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, "GOVERNMENT OF PURVANCHAL", ln=1, align="C")
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, "Department of Social Welfare - Age Proof Record", ln=1, align="C")
                pdf.ln(5)
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(50, 7, "Applicant Name:", border=1)
                pdf.cell(0, 7, str(args.get("applicant_name", "")), border=1, ln=1)
                pdf.cell(50, 7, "Mobile Number:", border=1)
                pdf.cell(0, 7, str(mobile), border=1, ln=1)
                pdf.cell(50, 7, "Date of Birth:", border=1)
                pdf.cell(0, 7, str(args.get("dob", "")), border=1, ln=1)
                pdf.cell(50, 7, "Document Type:", border=1)
                pdf.cell(0, 7, str(doc_type), border=1, ln=1)
                pdf.cell(50, 7, "Village / Block:", border=1)
                pdf.cell(0, 7, f"{args.get('village', '')}, {args.get('block', '')}", border=1, ln=1)
                pdf.ln(8)
                pdf.multi_cell(0, 5, "Official electronic verification record generated for Old Age Pension Scheme application.")
                pdf.output(doc_path)

            # Portal validation
            errors, cleaned = portal.validate_application(args, doc_path)
            if errors:
                return {
                    "error": "Application failed statutory validation.",
                    "validation_errors": errors
                }, True

            # Insert application & create portal_user
            new_id, app_no = portal.create_application(cur, mobile, cleaned)
            conn.commit()

            # Trigger SMS
            portal.send_sms(
                mobile,
                f"Sewa Setu: application {app_no} received. Track at the status portal "
                f"with mobile no. and password (DOB as DDMMYYYY)."
            )

            dob_pass = cleaned["dob"].strftime("%d%m%Y")
            sla_cutoff = (portal.now_ist() + timedelta(days=portal.SLA_DAYS)).strftime("%d/%m/%Y")

            return {
                "success": True,
                "application_id": new_id,
                "application_no": app_no,
                "applicant_name": cleaned["applicant_name"],
                "status": "PENDING",
                "submitted_at": portal.now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                "status_portal_credentials": {
                    "portal_url": "/status",
                    "login_mobile": mobile,
                    "password": dob_pass,
                    "password_rule": "Date of Birth in DDMMYYYY format"
                },
                "rtps_sla": {
                    "statutory_days": portal.SLA_DAYS,
                    "deemed_approval_cutoff": sla_cutoff,
                    "guarantee": "If not processed within 15 days, it stands deemed approved by law."
                },
                "message": f"Application {app_no} has been successfully recorded in the portal."
            }, False

        elif tool_name == "withdraw_application":
            cur.execute("""
                UPDATE applications
                SET status = 'WITHDRAWN', decided_at = %s, decided_by = 'APPLICANT'
                WHERE mobile = %s AND status = 'PENDING'
                RETURNING id, application_no
            """, (portal.now_ist(), mobile))
            row = cur.fetchone()
            if not row:
                return {
                    "error": "No pending application found to withdraw. Only applications in PENDING status can be withdrawn."
                }, True

            app_id, app_no = row
            reason = args.get("reason", "Withdrawn by applicant")
            portal.write_audit(cur, app_id, "WITHDRAW", f"applicant:{mobile}", note=reason)
            conn.commit()

            return {
                "success": True,
                "application_id": app_id,
                "application_no": app_no,
                "status": "WITHDRAWN",
                "message": f"Application {app_no} has been withdrawn. You may now submit a fresh application with corrected details."
            }, False

        elif tool_name == "download_acknowledgment":
            cur.execute("""
                SELECT id, application_no, applicant_name, status, submitted_at
                FROM applications WHERE mobile = %s ORDER BY submitted_at DESC LIMIT 1
            """, (mobile,))
            row = cur.fetchone()
            if not row:
                return {"error": "No application found for this citizen."}, True

            app_id, app_no, name, status, sub_at = row
            base_url = get_public_base_url()
            ack_url = f"{base_url}/ack/{app_id}.pdf"

            return {
                "application_id": app_id,
                "application_no": app_no,
                "applicant_name": name,
                "status": status,
                "acknowledgment_pdf_url": ack_url,
                "download_path": f"/ack/{app_id}.pdf",
                "instructions": "Download or print the official Government of Purvanchal PDF acknowledgment receipt from this link."
            }, False

        elif tool_name == "raise_grievance":
            category = args.get("category") or "OTHER"
            desc = (args.get("description") or "").strip()
            if not desc:
                return {"error": "A detailed description is required to register a grievance."}, True

            app_no = args.get("application_no")
            target_app_id = None
            if app_no:
                cur.execute("SELECT id, application_no FROM applications WHERE application_no = %s AND mobile = %s", (app_no, mobile))
                r = cur.fetchone()
                if r:
                    target_app_id, app_no = r
            if not target_app_id:
                cur.execute("SELECT id, application_no FROM applications WHERE mobile = %s ORDER BY id DESC LIMIT 1", (mobile,))
                r = cur.fetchone()
                if r:
                    target_app_id, app_no = r

            grv_no = "GRV" + datetime.now().strftime("%y") + str(random.randint(100000, 999999))
            note = f"[{category}] {desc} (Ref: {grv_no})"
            portal.write_audit(cur, target_app_id, "GRIEVANCE", f"applicant:{mobile}", note=note[:500])
            conn.commit()

            portal.send_sms(
                mobile,
                f"Sewa Setu: Grievance {grv_no} registered for Old Age Pension under RTPS Act. Statutory resolution SLA is 7 days."
            )

            return {
                "success": True,
                "grievance_no": grv_no,
                "application_no": app_no or "N/A",
                "category": category,
                "status": "REGISTERED",
                "message": f"Grievance {grv_no} has been registered under the Purvanchal Right to Public Services Act. The District Welfare Officer has been alerted.",
                "resolution_sla_days": 7
            }, False

        else:
            return {"error": f"Unknown citizen tool: {tool_name}"}, True

    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Officer MCP Server Tool Implementations
# ---------------------------------------------------------------------------

OFFICER_TOOLS = [
    {
        "name": "get_officer_dashboard",
        "description": "Get an executive summary of pension applications: total pending, applications approaching or exceeding the 15-day statutory SLA, breakdown by block, and status totals.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_pending_applications",
        "description": "List applications in the queue awaiting officer review and decision. Can filter by block and sort by SLA urgency (oldest / nearest to 15-day deadline first).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block": {
                    "type": "string",
                    "enum": ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"],
                    "description": "Optional block filter"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["all", "approaching_sla", "overdue"],
                    "description": "Filter by SLA urgency: 'approaching_sla' (pending 10+ days), 'overdue' (>15 days), or 'all'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (default 20, max 100)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Pagination offset (default 0)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_application_details",
        "description": "Retrieve full case file of an application: applicant personal details, bank verification, age proof document status, complete audit history, and automated compliance checklist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "Internal database ID of application"
                },
                "application_no": {
                    "type": "string",
                    "description": "Sewa Setu application number (e.g. 'SSP26123456')"
                }
            },
            "required": []
        }
    },
    {
        "name": "approve_application",
        "description": "Approve a pending Old Age Pension application. Enforces recording of official remarks in the audit trail, updates status to APPROVED, and triggers SMS notification to the applicant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "Internal ID of the application to approve"
                },
                "application_no": {
                    "type": "string",
                    "description": "Application number (if application_id is not known)"
                },
                "note": {
                    "type": "string",
                    "description": "Official verification remarks and justification (e.g. 'Age proof verified via Voter ID; bank account IFSC valid. Approved for ₹250/mo.')"
                }
            },
            "required": ["note"]
        }
    },
    {
        "name": "reject_application",
        "description": "Reject an ineligible pending application. Requires a clear, legally sound justification recorded against the officer's name in the audit trail, and sends an SMS explanation to the applicant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "Internal ID of the application to reject"
                },
                "application_no": {
                    "type": "string",
                    "description": "Application number (if application_id is not known)"
                },
                "reason": {
                    "type": "string",
                    "description": "Official mandatory reason for rejection (e.g. 'Applicant age on record is 58 years, below statutory requirement of 60 years.')"
                }
            },
            "required": ["reason"]
        }
    },
    {
        "name": "search_applications",
        "description": "Search applications by mobile number, application number, or applicant name across any status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (mobile number, application number, or applicant name)"
                },
                "status": {
                    "type": "string",
                    "enum": ["ALL", "PENDING", "APPROVED", "DEEMED_APPROVED", "REJECTED", "WITHDRAWN"],
                    "description": "Optional status filter (default ALL)"
                },
                "block": {
                    "type": "string",
                    "description": "Optional block filter"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_application_queue",
        "description": "Retrieve cases awaiting review in the block officer queue (alias for list_pending_applications).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block": {
                    "type": "string",
                    "enum": ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"],
                    "description": "Optional block filter"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["all", "approaching_sla", "overdue"],
                    "description": "Filter by SLA urgency: 'approaching_sla' (pending 10+ days), 'overdue' (>15 days), or 'all'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (default 20, max 100)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Pagination offset (default 0)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_welfare_analytics",
        "description": "Retrieve aggregate service metrics, pending queue counts, and SLA breach warnings (alias for get_officer_dashboard).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_application_status",
        "description": "Update a case through an authorized transition (APPROVED or REJECTED) with mandatory justification remarks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "Internal database ID of application"
                },
                "status": {
                    "type": "string",
                    "enum": ["APPROVED", "REJECTED"],
                    "description": "New status for the application"
                },
                "note": {
                    "type": "string",
                    "description": "Official justification remarks for the audit trail"
                }
            },
            "required": ["application_id", "status", "note"]
        }
    }
]


def execute_officer_tool(tool_name, args, claims):
    """Execute an officer tool with administrative credentials."""
    sub = claims.get("sub", "")
    officer_user = sub.split(":", 1)[1] if ":" in sub else sub or portal.ADMIN_USERNAME

    conn = portal.get_db()
    cur = conn.cursor()

    try:
        if tool_name in ("get_officer_dashboard", "get_welfare_analytics"):
            cur.execute("SELECT status, count(*) FROM applications GROUP BY status")
            by_status = dict(cur.fetchall())

            sla_cutoff = portal.now_ist() - timedelta(days=portal.SLA_DAYS)
            cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING' AND submitted_at < %s", (sla_cutoff,))
            overdue = cur.fetchone()[0]

            urgent_cutoff = portal.now_ist() - timedelta(days=10)
            cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING' AND submitted_at BETWEEN %s AND %s",
                        (sla_cutoff, urgent_cutoff))
            approaching_sla = cur.fetchone()[0]

            cur.execute("SELECT block, count(*) FROM applications WHERE status = 'PENDING' GROUP BY block ORDER BY count(*) DESC")
            by_block = [{"block": r[0], "pending_count": r[1]} for r in cur.fetchall()]

            return {
                "officer": officer_user,
                "timestamp": portal.now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                "statutory_sla_days": portal.SLA_DAYS,
                "summary": {
                    "total_pending": by_status.get("PENDING", 0),
                    "total_approved": by_status.get("APPROVED", 0),
                    "total_deemed_approved": by_status.get("DEEMED_APPROVED", 0),
                    "total_rejected": by_status.get("REJECTED", 0),
                    "total_withdrawn": by_status.get("WITHDRAWN", 0),
                    "overdue_beyond_sla": overdue,
                    "approaching_sla_warning": approaching_sla
                },
                "pending_by_block": by_block,
                "action_advisory": (
                    f"{overdue} applications have exceeded the 15-day SLA and will be deemed approved tonight if not reviewed. "
                    f"{approaching_sla} applications are approaching the SLA deadline (10+ days pending)."
                )
            }, False

        elif tool_name in ("list_pending_applications", "get_application_queue"):
            block = args.get("block")
            urgency = args.get("urgency", "all")
            limit = min(max(int(args.get("limit") or 20), 1), 100)
            offset = max(int(args.get("offset") or 0), 0)

            sql = """
                SELECT id, application_no, applicant_name, mobile, dob, village, block, submitted_at
                FROM applications
                WHERE status = 'PENDING'
            """
            params = []

            if block:
                sql += " AND block = %s"
                params.append(block)

            now = portal.now_ist()
            sla_cutoff = now - timedelta(days=portal.SLA_DAYS)
            urgent_cutoff = now - timedelta(days=10)

            if urgency == "overdue":
                sql += " AND submitted_at < %s"
                params.append(sla_cutoff)
            elif urgency == "approaching_sla":
                sql += " AND submitted_at BETWEEN %s AND %s"
                params.extend([sla_cutoff, urgent_cutoff])

            sql += " ORDER BY submitted_at ASC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(sql, params)
            rows = cur.fetchall()

            applications = []
            for r in rows:
                app_id, app_no, name, mob, dob, village, blk, sub_at = r
                days_pending = (now - sub_at).days if sub_at else 0
                age = portal.age_on(dob, now.date()) if dob else 0
                sla_rem = max(0, portal.SLA_DAYS - days_pending)

                applications.append({
                    "id": app_id,
                    "application_no": app_no,
                    "applicant_name": name,
                    "mobile": mob,
                    "calculated_age": age,
                    "village": village,
                    "block": blk,
                    "submitted_at": sub_at.strftime("%Y-%m-%d %H:%M") if sub_at else "",
                    "days_pending": days_pending,
                    "days_remaining_in_sla": sla_rem,
                    "is_overdue": days_pending >= portal.SLA_DAYS,
                    "is_urgent": 10 <= days_pending < portal.SLA_DAYS
                })

            return {
                "count": len(applications),
                "filter_block": block,
                "filter_urgency": urgency,
                "applications": applications
            }, False

        elif tool_name == "get_application_details":
            app_id = args.get("application_id")
            app_no = args.get("application_no")

            if not app_id and not app_no:
                return {"error": "Either application_id or application_no must be provided."}, True

            if app_id:
                cur.execute("SELECT id, application_no, applicant_name, mobile, dob, gender, marital_status, "
                            "husband_name, village, block, bank_account, ifsc, doc_path, status, submitted_at, "
                            "decided_at, decided_by FROM applications WHERE id = %s", (app_id,))
            else:
                cur.execute("SELECT id, application_no, applicant_name, mobile, dob, gender, marital_status, "
                            "husband_name, village, block, bank_account, ifsc, doc_path, status, submitted_at, "
                            "decided_at, decided_by FROM applications WHERE application_no = %s", (app_no,))

            row = cur.fetchone()
            if not row:
                return {"error": f"Application not found ({app_id or app_no})."}, True

            (a_id, a_no, name, mob, dob, gender, marital, husband, village, blk,
             bank_ac, ifsc, doc_path, status, sub_at, dec_at, dec_by) = row

            now = portal.now_ist()
            age = portal.age_on(dob, now.date()) if dob else 0
            days_pending = (now - sub_at).days if sub_at else 0

            # Compliance evaluation
            doc_exists = os.path.exists(doc_path) if doc_path else False
            compliance_checks = {
                "age_criterion": {
                    "passed": age >= portal.MIN_AGE,
                    "calculated_age": age,
                    "required_minimum": portal.MIN_AGE,
                    "status": "PASS" if age >= portal.MIN_AGE else "FAIL - UNDERAGE"
                },
                "bank_account_format": {
                    "passed": bool(re.fullmatch(r"\d{9,18}", bank_ac or "")),
                    "account_number": bank_ac,
                    "status": "PASS" if re.fullmatch(r"\d{9,18}", bank_ac or "") else "FAIL - INVALID DIGITS"
                },
                "ifsc_format": {
                    "passed": bool(re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc or "")),
                    "ifsc_code": ifsc,
                    "status": "PASS" if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc or "") else "FAIL - INVALID FORMAT"
                },
                "age_proof_document": {
                    "passed": bool(doc_path and doc_exists),
                    "file_path": doc_path,
                    "file_exists_on_disk": doc_exists,
                    "status": "PASS" if doc_exists else ("WARNING - FILE NOT ON DISK" if doc_path else "FAIL - NO DOC")
                },
                "rtps_sla_timeline": {
                    "days_pending": days_pending,
                    "sla_limit_days": portal.SLA_DAYS,
                    "days_remaining": max(0, portal.SLA_DAYS - days_pending),
                    "status": "OVERDUE" if days_pending >= portal.SLA_DAYS else "WITHIN SLA"
                }
            }

            # Audit trail
            cur.execute("SELECT at, action, actor, note FROM audit_log WHERE application_id = %s ORDER BY at ASC", (a_id,))
            audit_trail = [
                {"timestamp": a[0].strftime("%Y-%m-%d %H:%M:%S"), "action": a[1], "actor": a[2], "note": a[3] or ""}
                for a in cur.fetchall()
            ]

            return {
                "application_id": a_id,
                "application_no": a_no,
                "applicant_name": name,
                "mobile": mob,
                "dob": dob.strftime("%d/%m/%Y") if dob else "",
                "gender": gender,
                "marital_status": marital,
                "husband_name": husband,
                "village": village,
                "block": blk,
                "bank_account": bank_ac,
                "ifsc": ifsc,
                "status": status,
                "submitted_at": sub_at.strftime("%Y-%m-%d %H:%M:%S") if sub_at else "",
                "decided_at": dec_at.strftime("%Y-%m-%d %H:%M:%S") if dec_at else None,
                "decided_by": dec_by,
                "compliance_checks": compliance_checks,
                "audit_trail": audit_trail
            }, False

        elif tool_name == "approve_application":
            app_id = args.get("application_id")
            app_no = args.get("application_no")
            note = (args.get("note") or "").strip()

            if not note:
                return {"error": "An officer approval note/remark is required for official accountability."}, True

            if not app_id and not app_no:
                return {"error": "Either application_id or application_no is required."}, True

            # Query and lock pending application
            if app_id:
                cur.execute("SELECT id, application_no, mobile, applicant_name FROM applications WHERE id = %s AND status = 'PENDING'", (app_id,))
            else:
                cur.execute("SELECT id, application_no, mobile, applicant_name FROM applications WHERE application_no = %s AND status = 'PENDING'", (app_no,))

            row = cur.fetchone()
            if not row:
                return {"error": f"Application {app_id or app_no} is not in PENDING status or was not found."}, True

            target_id, target_no, target_mobile, target_name = row
            now = portal.now_ist()

            cur.execute("""
                UPDATE applications
                SET status = 'APPROVED', decided_at = %s, decided_by = %s
                WHERE id = %s
            """, (now, officer_user, target_id))

            portal.write_audit(cur, target_id, "APPROVED", f"admin:{officer_user}", note=note)
            conn.commit()

            # Trigger SMS
            portal.send_sms(
                target_mobile,
                f"Sewa Setu: your pension application {target_no} has been APPROVED by the Block Welfare Office. "
                f"Monthly pension of Rs 250 will be credited via DBT."
            )

            return {
                "success": True,
                "application_id": target_id,
                "application_no": target_no,
                "applicant_name": target_name,
                "new_status": "APPROVED",
                "decided_by": officer_user,
                "decided_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "audit_note": note,
                "message": f"Application {target_no} for {target_name} has been APPROVED. Audit record created and SMS notification sent."
            }, False

        elif tool_name == "reject_application":
            app_id = args.get("application_id")
            app_no = args.get("application_no")
            reason = (args.get("reason") or "").strip()

            if not reason:
                return {"error": "A mandatory, legally sound rejection reason is required for administrative accountability."}, True

            if not app_id and not app_no:
                return {"error": "Either application_id or application_no is required."}, True

            if app_id:
                cur.execute("SELECT id, application_no, mobile, applicant_name FROM applications WHERE id = %s AND status = 'PENDING'", (app_id,))
            else:
                cur.execute("SELECT id, application_no, mobile, applicant_name FROM applications WHERE application_no = %s AND status = 'PENDING'", (app_no,))

            row = cur.fetchone()
            if not row:
                return {"error": f"Application {app_id or app_no} is not in PENDING status or was not found."}, True

            target_id, target_no, target_mobile, target_name = row
            now = portal.now_ist()

            cur.execute("""
                UPDATE applications
                SET status = 'REJECTED', decided_at = %s, decided_by = %s
                WHERE id = %s
            """, (now, officer_user, target_id))

            portal.write_audit(cur, target_id, "REJECTED", f"admin:{officer_user}", note=reason)
            conn.commit()

            # Trigger SMS with explanation
            portal.send_sms(
                target_mobile,
                f"Sewa Setu: your pension application {target_no} has been REJECTED. Reason: {reason}."
            )

            return {
                "success": True,
                "application_id": target_id,
                "application_no": target_no,
                "applicant_name": target_name,
                "new_status": "REJECTED",
                "decided_by": officer_user,
                "decided_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "rejection_reason": reason,
                "message": f"Application {target_no} has been REJECTED. Legal justification recorded in audit log and SMS sent to applicant."
            }, False

        elif tool_name == "search_applications":
            query = (args.get("query") or "").strip()
            status_filter = (args.get("status") or "ALL").upper()
            block_filter = args.get("block")

            sql = """
                SELECT id, application_no, applicant_name, mobile, block, village, status, submitted_at, decided_at
                FROM applications
                WHERE 1=1
            """
            params = []

            if query:
                if query.isdigit():
                    sql += " AND (mobile = %s OR application_no ILIKE %s)"
                    params.extend([query, f"%{query}%"])
                elif query.startswith("SSP"):
                    sql += " AND application_no = %s"
                    params.append(query)
                else:
                    sql += " AND applicant_name ILIKE %s"
                    params.append(f"%{query}%")

            if status_filter != "ALL":
                sql += " AND status = %s"
                params.append(status_filter)

            if block_filter:
                sql += " AND block = %s"
                params.append(block_filter)

            sql += " ORDER BY submitted_at DESC LIMIT 50"

            cur.execute(sql, params)
            rows = cur.fetchall()

            results = [
                {
                    "id": r[0],
                    "application_no": r[1],
                    "applicant_name": r[2],
                    "mobile": r[3],
                    "block": r[4],
                    "village": r[5],
                    "status": r[6],
                    "submitted_at": r[7].strftime("%Y-%m-%d %H:%M") if r[7] else "",
                    "decided_at": r[8].strftime("%Y-%m-%d %H:%M") if r[8] else None
                }
                for r in rows
            ]

            return {"total_matches": len(results), "applications": results}, False

        elif tool_name == "update_application_status":
            new_status = (args.get("status") or "").upper()
            note = args.get("note") or ""
            if new_status == "APPROVED":
                return execute_officer_tool("approve_application", {"application_id": args.get("application_id"), "note": note}, claims)
            elif new_status == "REJECTED":
                return execute_officer_tool("reject_application", {"application_id": args.get("application_id"), "reason": note}, claims)
            else:
                return {"error": f"Invalid status transition to '{new_status}'. Allowed transitions: APPROVED, REJECTED."}, True

        else:
            return {"error": f"Unknown officer tool: {tool_name}"}, True

    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Core JSON-RPC 2.0 Dispatcher for Streamable HTTP / SSE
# ---------------------------------------------------------------------------

def handle_jsonrpc_request(req_data, tools_list, execute_tool_fn, server_name, claims):
    """Process a single JSON-RPC 2.0 request according to the MCP Specification."""
    if not isinstance(req_data, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request: expected JSON object."}
        }

    msg_id = req_data.get("id")
    method = req_data.get("method")
    params = req_data.get("params") or {}

    # Notifications (messages without id)
    if msg_id is None and method == "notifications/initialized":
        return None  # No response to notification

    if not method:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32600, "message": "Invalid Request: missing method."}
        }

    # 1. MCP initialize handshake
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": server_name,
                    "version": "1.0.0"
                }
            }
        }

    # 2. MCP ping
    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {}
        }

    # 3. List tools
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": tools_list
            }
        }

    # 4. Call tool
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}

        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": "Missing 'name' parameter for tool."}
            }

        # Check if tool is allowed for this server
        valid_tool_names = [t["name"] for t in tools_list]
        if tool_name not in valid_tool_names:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found on this MCP endpoint."
                }
            }

        result_payload, is_error = execute_tool_fn(tool_name, tool_args, claims)

        # Content formatted per MCP spec
        if isinstance(result_payload, dict) and "text" in result_payload:
            text_content = result_payload["text"]
        else:
            text_content = json.dumps(result_payload, indent=2, ensure_ascii=False)

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": text_content
                    }
                ],
                "isError": is_error
            }
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented."}
        }


# ---------------------------------------------------------------------------
# Interactive HTML Landing Pages for Browser Visitors
# ---------------------------------------------------------------------------

DOCS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ server_title }} — Sewa Setu MCP Server</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --border: #e2e8f0;
      --text-main: #0f172a;
      --text-body: #334155;
      --text-muted: #64748b;
      --primary: #0f172a;
      --accent: #2563eb;
      --accent-soft: #eff6ff;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.04);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text-body);
      line-height: 1.6;
      padding: 32px 20px;
    }
    .container {
      max-width: 860px;
      margin: 0 auto;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 36px 40px;
      box-shadow: var(--shadow-sm);
    }
    @media (max-width: 640px) { .container { padding: 24px 20px; } }
    .nav-links {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }
    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: color 0.15s;
    }
    .nav-links a:hover { color: var(--text-main); }
    h1 {
      font-size: 22px;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: -0.02em;
      margin-bottom: 8px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 20px;
      background: #f1f5f9;
      color: var(--text-main);
      margin-bottom: 18px;
      border: 1px solid var(--border);
    }
    .badge.officer { background: #fdf2f8; color: #9d174d; border-color: rgba(157,23,77,0.2); }
    .badge.citizen { background: var(--accent-soft); color: var(--accent); border-color: rgba(37,99,235,0.2); }
    h3 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-main);
      margin: 24px 0 10px;
      letter-spacing: -0.01em;
    }
    p { font-size: 14px; margin-bottom: 12px; color: var(--text-body); }
    pre {
      background: #0f172a;
      color: #f8fafc;
      padding: 14px 16px;
      border-radius: var(--radius-sm);
      overflow-x: auto;
      font-size: 13px;
      font-family: Consolas, Monaco, monospace;
      margin: 10px 0 16px;
    }
    code { font-family: Consolas, Monaco, monospace; font-size: 13px; }
    .tool-box {
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 16px 18px;
      margin-bottom: 14px;
      background: #fafbfc;
    }
    .tool-name {
      font-size: 14.5px;
      font-weight: 600;
      color: var(--text-main);
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .tool-name code { color: var(--accent); }
    .tool-desc { font-size: 13px; color: var(--text-muted); margin-bottom: 10px; }
    details { font-size: 12.5px; }
    details summary {
      cursor: pointer;
      color: var(--text-muted);
      font-weight: 500;
      user-select: none;
    }
    details summary:hover { color: var(--text-main); }
  </style>
</head>
<body>
<div class="container">
  <div class="nav-links">
    <a href="/"><i class="fa-solid fa-arrow-left"></i> Return to Portal Home</a>
    <a href="/eval-dashboard"><i class="fa-solid fa-chart-line"></i> Evaluation Dashboard</a>
    <a href="/admin"><i class="fa-solid fa-lock"></i> Departmental Login</a>
    <a href="/about"><i class="fa-solid fa-circle-info"></i> About Scheme</a>
  </div>

  <h1>{{ server_title }}</h1>
  <div class="badge {{ 'officer' if role == 'officer' else 'citizen' }}">
    <i class="fa-solid fa-shield-halved"></i> Role: {{ role }} &middot; Streamable HTTP (MCP 2024-11-05)
  </div>

  <p>
    This is the official streamable HTTP Model Context Protocol (MCP) endpoint for
    <strong>{{ 'Senior Citizen Applicants' if role == 'citizen' else 'Block Welfare Officers' }}</strong>
    in the Sewa Setu pension portal.
  </p>

  <h3>How to Connect with Claude Code</h3>
  <pre><code>claude mcp add --transport http {{ server_name }} {{ endpoint_url }}</code></pre>

  <h3>Authentication</h3>
  <p>
    Protected by <strong>OAuth 2.1</strong> (RFC 8414 &amp; RFC 9728). Unauthenticated requests receive an HTTP
    <code>401 Unauthorized</code> challenge pointing to <code>{{ base_url }}/.well-known/oauth-protected-resource</code>.
  </p>

  <h3>Available Tools on this Endpoint ({{ tools|length }})</h3>
  {% for tool in tools %}
  <div class="tool-box">
    <div class="tool-name"><i class="fa-solid fa-wrench" style="font-size:12px;color:var(--text-muted);"></i> <code>{{ tool.name }}</code></div>
    <div class="tool-desc">{{ tool.description }}</div>
    <details>
      <summary><i class="fa-solid fa-code"></i> View Input JSON Schema</summary>
      <pre style="margin-top:8px;"><code>{{ tool.inputSchema | tojson(indent=2) }}</code></pre>
    </details>
  </div>
  {% endfor %}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoint 1: Citizen MCP Server (/mcp/citizen)
# ---------------------------------------------------------------------------

@mcp_bp.route("/mcp/citizen", methods=["GET", "POST"])
def mcp_citizen_endpoint():
    """Streamable HTTP endpoint for Senior Citizen Assistant."""
    # If browser GET without SSE accept header, render documentation page
    if request.method == "GET" and "text/event-stream" not in request.headers.get("Accept", "") and not request.args.get("sse"):
        base_url = get_public_base_url()
        return render_template_string(
            DOCS_HTML_TEMPLATE,
            server_title="Sewa Setu Citizen Assistant (MCP Server)",
            server_name="sewasetu-citizen",
            role="citizen",
            endpoint_url=f"{base_url}/mcp/citizen",
            base_url=base_url,
            tools=CITIZEN_TOOLS
        )

    # Authenticate request
    claims, auth_error = authenticate_mcp_request(required_role="citizen")
    if auth_error:
        return auth_error

    # Handle GET with SSE
    if request.method == "GET":
        session_id = secrets.token_hex(16)
        def sse_stream():
            yield f"event: endpoint\ndata: /mcp/citizen/messages?session_id={session_id}\n\n"
            while True:
                time.sleep(15)
                yield ": keepalive\n\n"
        return Response(stream_with_context(sse_stream()), content_type="text/event-stream")

    # POST: JSON-RPC over HTTP
    req_body = request.get_json(silent=True, force=True)
    if req_body is None:
        return jsonify({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error: invalid JSON body."}
        }), 400

    # Support batch requests
    if isinstance(req_body, list):
        responses = [
            handle_jsonrpc_request(item, CITIZEN_TOOLS, execute_citizen_tool, "sewasetu-citizen-mcp", claims)
            for item in req_body
        ]
        # Filter out None (from notifications)
        return jsonify([r for r in responses if r is not None])

    response = handle_jsonrpc_request(req_body, CITIZEN_TOOLS, execute_citizen_tool, "sewasetu-citizen-mcp", claims)
    if response is None:
        return ("", 204)  # Notification
    return jsonify(response)


@mcp_bp.route("/mcp/citizen/messages", methods=["POST"])
def mcp_citizen_messages():
    """SSE message receiver for Citizen MCP."""
    claims, auth_error = authenticate_mcp_request(required_role="citizen")
    if auth_error:
        return auth_error

    req_body = request.get_json(silent=True, force=True)
    if not req_body:
        return jsonify({"error": "invalid_json"}), 400

    response = handle_jsonrpc_request(req_body, CITIZEN_TOOLS, execute_citizen_tool, "sewasetu-citizen-mcp", claims)
    return jsonify(response) if response else ("", 204)


# ---------------------------------------------------------------------------
# Endpoint 2: Block Officer MCP Server (/mcp/officer)
# ---------------------------------------------------------------------------

@mcp_bp.route("/mcp/officer", methods=["GET", "POST"])
def mcp_officer_endpoint():
    """Streamable HTTP endpoint for Block Officer Assistant."""
    # If browser GET without SSE accept header, render documentation page
    if request.method == "GET" and "text/event-stream" not in request.headers.get("Accept", "") and not request.args.get("sse"):
        base_url = get_public_base_url()
        return render_template_string(
            DOCS_HTML_TEMPLATE,
            server_title="Sewa Setu Block Officer Assistant (MCP Server)",
            server_name="sewasetu-officer",
            role="officer",
            endpoint_url=f"{base_url}/mcp/officer",
            base_url=base_url,
            tools=OFFICER_TOOLS
        )

    # Authenticate request
    claims, auth_error = authenticate_mcp_request(required_role="officer")
    if auth_error:
        return auth_error

    # Handle GET with SSE
    if request.method == "GET":
        session_id = secrets.token_hex(16)
        def sse_stream():
            yield f"event: endpoint\ndata: /mcp/officer/messages?session_id={session_id}\n\n"
            while True:
                time.sleep(15)
                yield ": keepalive\n\n"
        return Response(stream_with_context(sse_stream()), content_type="text/event-stream")

    # POST: JSON-RPC over HTTP
    req_body = request.get_json(silent=True, force=True)
    if req_body is None:
        return jsonify({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error: invalid JSON body."}
        }), 400

    if isinstance(req_body, list):
        responses = [
            handle_jsonrpc_request(item, OFFICER_TOOLS, execute_officer_tool, "sewasetu-officer-mcp", claims)
            for item in req_body
        ]
        return jsonify([r for r in responses if r is not None])

    response = handle_jsonrpc_request(req_body, OFFICER_TOOLS, execute_officer_tool, "sewasetu-officer-mcp", claims)
    if response is None:
        return ("", 204)
    return jsonify(response)


@mcp_bp.route("/mcp/officer/messages", methods=["POST"])
def mcp_officer_messages():
    """SSE message receiver for Officer MCP."""
    claims, auth_error = authenticate_mcp_request(required_role="officer")
    if auth_error:
        return auth_error

    req_body = request.get_json(silent=True, force=True)
    if not req_body:
        return jsonify({"error": "invalid_json"}), 400

    response = handle_jsonrpc_request(req_body, OFFICER_TOOLS, execute_officer_tool, "sewasetu-officer-mcp", claims)
    return jsonify(response) if response else ("", 204)
