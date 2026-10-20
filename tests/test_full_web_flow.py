#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Test for all Citizen Web Pages and Flows.
"""
import re
import unittest
import psycopg2
import app as portal

class TestFullWebPages(unittest.TestCase):
    def setUp(self):
        self.app = portal.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.test_mobile = "9876599999"
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        conn = portal.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM applications WHERE mobile = %s", (self.test_mobile,))
        rows = cur.fetchall()
        for r in rows:
            cur.execute("DELETE FROM audit_log WHERE application_id = %s", (r[0],))
        cur.execute("DELETE FROM applications WHERE mobile = %s", (self.test_mobile,))
        cur.execute("DELETE FROM portal_users WHERE mobile = %s", (self.test_mobile,))
        cur.execute("DELETE FROM otps WHERE mobile = %s", (self.test_mobile,))
        conn.commit()
        cur.close()
        conn.close()

    def test_all_pages_render_and_work(self):
        # 1. Homepage
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Old Age Pension", res.data)

        # 2. About page
        res = self.client.get("/about")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Department of Social Welfare", res.data)

        # 3. Health check
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)

        # 4. Assistant page
        res = self.client.get("/assistant")
        self.assertEqual(res.status_code, 200)

        # 5. Eval dashboard
        res = self.client.get("/eval-dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Evaluation", res.data)

        # 6. Apply page (GET)
        res = self.client.get("/apply")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Mobile Verification", res.data)

        # Extract captcha answer from session
        with self.client.session_transaction() as sess:
            captcha_ans = sess.get("captcha_answer")

        # 7. Apply page (POST)
        res = self.client.post("/apply", data={
            "mobile": self.test_mobile,
            "captcha": str(captcha_ans)
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Enter OTP", res.data)

        # 8. Retrieve OTP from DB
        conn = portal.get_db()
        cur = conn.cursor()
        cur.execute("SELECT code FROM otps WHERE mobile = %s ORDER BY created_at DESC LIMIT 1", (self.test_mobile,))
        otp = cur.fetchone()[0]
        cur.close(); conn.close()

        # 9. Verify OTP (POST)
        res = self.client.post("/verify", data={"otp": otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Personal Details", res.data)

        # 10. Form Step 1 (Personal Details)
        res = self.client.post("/form/1", data={
            "applicant_name": "Hiteswar Saikia",
            "dob": "12/05/1952",
            "gender": "Male",
            "marital_status": "Married",
            "husband_name": ""
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Address Details", res.data)

        # 11. Form Step 2 (Address Details)
        res = self.client.post("/form/2", data={
            "village": "Borhat",
            "block": "Sonari"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Bank Details", res.data)

        # 12. Form Step 3 (Bank Details)
        res = self.client.post("/form/3", data={
            "bank_account": "14220100099999",
            "ifsc": "UCBA0001422"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Upload Age Proof Document", res.data)

        # 13. Upload document (POST)
        import io
        fake_file = (io.BytesIO(b"%PDF-1.4 test document content"), "age_proof.pdf")
        res = self.client.post("/upload", data={"document": fake_file}, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Preview &amp; Declaration", res.data)

        # 14. Submit Declaration (POST)
        res = self.client.post("/declaration", data={"agree": "1"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Application Successfully Submitted", res.data)
        self.assertIn(b"SSP26", res.data)

        # 15. Verify DB record and Acknowledgment PDF download
        conn = portal.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, application_no FROM applications WHERE mobile = %s", (self.test_mobile,))
        app_row = cur.fetchone()
        self.assertIsNotNone(app_row)
        app_id, app_no = app_row[0], app_row[1]
        cur.close(); conn.close()

        res = self.client.get(f"/ack/{app_id}.pdf")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/pdf")
        self.assertTrue(res.data.startswith(b"%PDF"))

        # 16. Status login (GET and POST)
        # Logout first
        with self.client.session_transaction() as sess:
            sess.clear()

        res = self.client.get("/status")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Check Application Status", res.data)

        # Login with DOB password: 12051952
        res = self.client.post("/status", data={
            "mobile": self.test_mobile,
            "password": "12051952"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Application Status", res.data)
        self.assertIn(app_no.encode("utf-8"), res.data)

        # 17. Application view (GET)
        res = self.client.get(f"/application/{app_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Hiteswar Saikia", res.data)

        # 18. Admin login and dashboard
        with self.client.session_transaction() as sess:
            sess.clear()

        res = self.client.post("/admin", data={
            "username": "admin",
            "password": "change-me-before-deploying"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Departmental Dashboard", res.data)

        # 19. Admin applications queue
        res = self.client.get("/admin/applications?status=PENDING")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Applications", res.data)
        self.assertIn(b"PENDING", res.data)

        # 20. Admin view specific application
        res = self.client.get(f"/admin/application/{app_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Applicant Details", res.data)
        self.assertIn(b"Hiteswar Saikia", res.data)

        # 21. Admin approve application
        res = self.client.post(f"/admin/approve/{app_id}", data={
            "note": "Verified Voter ID and bank passbook. Meets all criteria."
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 22. Verify in DB that status is APPROVED
        conn = portal.get_db()
        cur = conn.cursor()
        cur.execute("SELECT status, decided_by FROM applications WHERE id = %s", (app_id,))
        status_row = cur.fetchone()
        self.assertEqual(status_row[0], "APPROVED")
        self.assertEqual(status_row[1], "admin")
        cur.close(); conn.close()

if __name__ == "__main__":
    unittest.main()
