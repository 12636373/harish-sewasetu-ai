# -*- coding: utf-8 -*-
"""
Automated Backend & Business Logic Test Suite
Public Tech Challenge: Take Home — Seva Setu, agent-ready
Department of Social Welfare, Government of Purvanchal

Verifies:
1. Scheme validation rules & statutory eligibility criteria
2. State machine status transitions & terminal states
3. Duplicate submission prevention & mobile re-application logic
4. Database integrity, persistence, and partial unique constraints
5. Audit log invariants for administrative and citizen actions
6. Application number collision resistance
7. Consistent error handling (JSON vs HTML)
"""

import os
import sys
import unittest
from datetime import datetime, date, timedelta

import werkzeug
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

# Ensure /app or repo root is in python path
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

import app as portal


class TestSchemeValidation(unittest.TestCase):
    """Test statutory welfare scheme validation rules."""

    def setUp(self):
        self.valid_data = {
            "applicant_name": "Jogeshwar Barua",
            "village": "Sepon Tea Estate",
            "block": "Sonari",
            "gender": "Male",
            "marital_status": "Married",
            "husband_name": "",
            "bank_account": "123456789012",
            "ifsc": "SBIN0003077",
            "dob": "15/08/1954",  # Age 72
        }
        self.doc_path = "/var/sewasetu/uploads/test_doc.pdf"

    def test_valid_application_passes(self):
        errors, cleaned = portal.validate_application(self.valid_data, self.doc_path)
        self.assertEqual(errors, [], f"Expected 0 errors, got: {errors}")
        self.assertEqual(cleaned["applicant_name"], "Jogeshwar Barua")
        self.assertEqual(cleaned["block"], "Sonari")
        self.assertEqual(cleaned["ifsc"], "SBIN0003077")
        self.assertEqual(cleaned["dob"], date(1954, 8, 15))

    def test_underage_applicant_fails(self):
        data = self.valid_data.copy()
        # Age 58
        data["dob"] = (portal.now_ist().date() - timedelta(days=58 * 365.25)).strftime("%d/%m/%Y")
        errors, _ = portal.validate_application(data, self.doc_path)
        self.assertTrue(any("must be 60 years of age or above" in e for e in errors))

    def test_missing_required_fields_fail(self):
        required_fields = ["applicant_name", "village", "block", "bank_account"]
        for field in required_fields:
            data = self.valid_data.copy()
            data[field] = ""
            errors, _ = portal.validate_application(data, self.doc_path)
            self.assertTrue(len(errors) > 0, f"Expected error when {field} is missing")

    def test_unrecognized_block_fails(self):
        data = self.valid_data.copy()
        data["block"] = "Guwahati Metropolitan"
        errors, _ = portal.validate_application(data, self.doc_path)
        self.assertTrue(any("block must be one of" in e for e in errors))

    def test_invalid_bank_account_fails(self):
        # Letters in account
        data = self.valid_data.copy()
        data["bank_account"] = "1234ABC99"
        errors, _ = portal.validate_application(data, self.doc_path)
        self.assertTrue(any("bank account number must be 9 to 18 digits" in e for e in errors))

        # Too short (< 9 digits)
        data["bank_account"] = "12345"
        errors, _ = portal.validate_application(data, self.doc_path)
        self.assertTrue(any("bank account number must be 9 to 18 digits" in e for e in errors))

    def test_invalid_ifsc_fails(self):
        # Invalid format
        data = self.valid_data.copy()
        data["ifsc"] = "SBIN123"
        errors, _ = portal.validate_application(data, self.doc_path)
        self.assertTrue(any("IFSC must be 11 characters" in e for e in errors))

        # Lowercase IFSC normalized to uppercase
        data["ifsc"] = "sbin0003077"
        errors, cleaned = portal.validate_application(data, self.doc_path)
        self.assertEqual(cleaned["ifsc"], "SBIN0003077")

    def test_invalid_dob_format_fails(self):
        data = self.valid_data.copy()
        for bad_dob in ["31/02/1955", "invalid-date", "1954-08-15", ""]:
            data["dob"] = bad_dob
            errors, _ = portal.validate_application(data, self.doc_path)
            self.assertTrue(any("date of birth must be given as DD/MM/YYYY" in e for e in errors))

    def test_missing_doc_path_fails(self):
        errors, _ = portal.validate_application(self.valid_data, "")
        self.assertTrue(any("age proof document is required" in e for e in errors))


class TestStatusTransitions(unittest.TestCase):
    """Test welfare state machine and terminal status invariant rules."""

    def test_valid_transitions_from_pending(self):
        self.assertTrue(portal.can_transition("PENDING", "APPROVED"))
        self.assertTrue(portal.can_transition("PENDING", "REJECTED"))
        self.assertTrue(portal.can_transition("PENDING", "WITHDRAWN"))
        self.assertTrue(portal.can_transition("PENDING", "DEEMED_APPROVED"))

    def test_invalid_transitions_from_terminal_states(self):
        terminal_states = ["APPROVED", "REJECTED", "WITHDRAWN", "DEEMED_APPROVED"]
        target_states = ["PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "DEEMED_APPROVED"]
        for curr in terminal_states:
            for target in target_states:
                self.assertFalse(portal.can_transition(curr, target),
                                 f"State transition {curr} -> {target} should be illegal!")


class TestApplicationNumberGeneration(unittest.TestCase):
    """Test format and collision resistance of application numbers."""

    def test_app_number_format(self):
        app_no = portal.new_application_no()
        self.assertTrue(app_no.startswith("SSP26"), f"Expected SSP26..., got {app_no}")
        self.assertEqual(len(app_no), 11, f"Expected length 11, got {len(app_no)}")
        self.assertTrue(app_no[5:].isdigit(), "Suffix must be 6 digits")

    def test_unique_generation_with_cursor(self):
        conn = portal.get_db()
        cur = conn.cursor()
        try:
            app_no = portal.new_application_no(cur)
            cur.execute("SELECT 1 FROM applications WHERE application_no = %s", (app_no,))
            self.assertIsNone(cur.fetchone(), "Generated app_no should not already exist in DB")
        finally:
            cur.close()
            conn.close()


class TestDatabaseIntegrityAndPersistence(unittest.TestCase):
    """Test live PostgreSQL database operations, constraints, and audit logging."""

    def setUp(self):
        self.test_mobile = "9999900001"
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        conn = portal.get_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM applications WHERE mobile = %s", (self.test_mobile,))
            app_ids = [r[0] for r in cur.fetchall()]
            if app_ids:
                cur.execute("DELETE FROM audit_log WHERE application_id = ANY(%s)", (app_ids,))
                cur.execute("DELETE FROM applications WHERE id = ANY(%s)", (app_ids,))
            cur.execute("DELETE FROM portal_users WHERE mobile = %s", (self.test_mobile,))
            cur.execute("DELETE FROM otps WHERE mobile = %s", (self.test_mobile,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_create_and_active_application_lifecycle(self):
        conn = portal.get_db()
        cur = conn.cursor()
        try:
            # 1. No active application initially
            existing = portal.active_application(cur, self.test_mobile)
            self.assertIsNone(existing)

            # 2. Create application
            cleaned = {
                "applicant_name": "Test Citizen Barua",
                "village": "Borhat",
                "block": "Sonari",
                "gender": "Male",
                "marital_status": "Married",
                "husband_name": "",
                "husband_employer": "",
                "bank_account": "987654321012",
                "ifsc": "UCBA0001422",
                "doc_path": "/var/sewasetu/uploads/test.pdf",
                "dob": date(1955, 3, 10),
            }
            app_id, app_no = portal.create_application(cur, self.test_mobile, cleaned)
            conn.commit()

            self.assertIsNotNone(app_id)
            self.assertTrue(app_no.startswith("SSP"))

            # 3. Active application exists
            active = portal.active_application(cur, self.test_mobile)
            self.assertIsNotNone(active)
            self.assertEqual(active[0], app_id)
            self.assertEqual(active[2], "PENDING")

            # 4. Audit log recorded SUBMIT
            cur.execute("SELECT action, actor FROM audit_log WHERE application_id = %s", (app_id,))
            audit_row = cur.fetchone()
            self.assertIsNotNone(audit_row)
            self.assertEqual(audit_row[0], "SUBMIT")
            self.assertEqual(audit_row[1], f"applicant:{self.test_mobile}")

            # 5. Portal user record created with DOB hash
            cur.execute("SELECT password_hash FROM portal_users WHERE mobile = %s", (self.test_mobile,))
            user_row = cur.fetchone()
            self.assertIsNotNone(user_row)
            expected_hash = portal.hash_password("10031955")
            self.assertEqual(user_row[0], expected_hash)

            # 6. Database partial unique index blocks duplicate active application
            with self.assertRaises(Exception):
                portal.create_application(cur, self.test_mobile, cleaned)
                conn.commit()
            conn.rollback()

            # 7. Voluntary withdrawal unblocks mobile
            cur.execute("""
                UPDATE applications SET status = 'WITHDRAWN', decided_at = %s, decided_by = 'APPLICANT'
                WHERE id = %s RETURNING status
            """, (datetime.now(), app_id))
            portal.write_audit(cur, app_id, "WITHDRAW", f"applicant:{self.test_mobile}", "Mistake in bank details")
            conn.commit()

            # 8. Active application check returns None now
            active_after_withdraw = portal.active_application(cur, self.test_mobile)
            self.assertIsNone(active_after_withdraw)

            # 9. Clean audit trail has both SUBMIT and WITHDRAW
            cur.execute("SELECT action FROM audit_log WHERE application_id = %s ORDER BY at ASC", (app_id,))
            actions = [r[0] for r in cur.fetchall()]
            self.assertEqual(actions, ["SUBMIT", "WITHDRAW"])

        finally:
            cur.close()
            conn.close()


class TestErrorResponses(unittest.TestCase):
    """Test consistent JSON vs HTML error responses across the application."""

    def setUp(self):
        self.client = portal.app.test_client()

    def test_json_404_for_api(self):
        resp = self.client.get("/api/non-existent-endpoint", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "not_found")
        self.assertEqual(data.get("status_code"), 404)

    def test_json_404_for_mcp(self):
        resp = self.client.get("/mcp/unknown", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(resp.is_json)

    def test_html_404_for_browser(self):
        resp = self.client.get("/non-existent-portal-page", headers={"Accept": "text/html"})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.is_json)
        self.assertIn(b"404", resp.data)
        self.assertIn(b"Page Not Found", resp.data)


class TestAuthenticationAndAuthorization(unittest.TestCase):
    """Test server-side authentication and role-based access control."""

    def setUp(self):
        self.client = portal.app.test_client()

    def test_unauthenticated_admin_routes_redirect(self):
        protected_routes = [
            "/admin/dashboard",
            "/admin/applications",
            "/admin/application/1",
            "/admin/tokens",
        ]
        for route in protected_routes:
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 302, f"Route {route} should redirect unauthenticated users")
            self.assertIn("/admin", resp.headers.get("Location", ""))

    def test_unauthenticated_citizen_routes_redirect(self):
        resp = self.client.get("/application/1")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/status", resp.headers.get("Location", ""))

    def test_mcp_unauthenticated_challenge(self):
        resp = self.client.post("/mcp/citizen", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("WWW-Authenticate", resp.headers)
        self.assertIn("resource_metadata", resp.headers["WWW-Authenticate"])


class TestAuditLogSensitiveOperations(unittest.TestCase):
    """Test audit trail recording for sensitive administrative actions."""

    def test_administrative_audit_actions(self):
        conn = portal.get_db()
        cur = conn.cursor()
        try:
            # 1. Password reset audit entry
            portal.write_audit(cur, None, "RESET_PASSWORD", "system:citizen-reset", "Password reset for test")
            # 2. Program token minting audit entry
            portal.write_audit(cur, None, "MINT_PROGRAM_TOKEN", "admin:admin", "Minted officer token")
            conn.commit()

            cur.execute("SELECT action, actor, note FROM audit_log WHERE action = 'MINT_PROGRAM_TOKEN' ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "MINT_PROGRAM_TOKEN")
            self.assertEqual(row[1], "admin:admin")
            self.assertIn("Minted officer token", row[2])
        finally:
            cur.close()
            conn.close()


if __name__ == "__main__":
    unittest.main()
