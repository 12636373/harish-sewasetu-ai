# -*- coding: utf-8 -*-
"""
Sewa Setu - Old Age Pension Portal
Government of Purvanchal, Department of Social Welfare

Developed by: Netlink Infosolutions Pvt Ltd (2023)
Maintained in-house since 02/2026.
"""

import os
import io
import re
import random
import hashlib
import configparser
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    """The portal's clock is Indian Standard Time regardless of where the server runs."""
    return datetime.now(IST).replace(tzinfo=None)

import requests
import psycopg2
import werkzeug
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"
from flask import (Flask, request, session, redirect, url_for, render_template,
                   flash, send_file, abort, jsonify)
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

config = configparser.ConfigParser()
config.read(os.path.join(BASE_DIR, "config", "app.ini"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or config.get("app", "secret_key")
# Two hours: elderly applicants fill the form slowly; the draft lives in the session.
app.config["PERMANENT_SESSION_LIFETIME"] = 7200

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# An applicant may hold at most one application in these states at a time.
# WITHDRAWN and REJECTED applications do not block a fresh application.
ACTIVE_STATUSES = ("PENDING", "APPROVED", "DEEMED_APPROVED")

SMS_GATEWAY_URL = config.get("app", "sms_gateway_url")
OTP_VALIDITY_SECONDS = config.getint("app", "otp_validity_seconds")
UPLOAD_DIR = config.get("app", "upload_dir")
SCHEME_DEADLINE = datetime.strptime(config.get("pension", "scheme_deadline"),
                                    "%Y-%m-%d %H:%M")
MIN_AGE = config.getint("pension", "min_age")
SLA_DAYS = config.getint("pension", "sla_days")

BLOCKS = ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"]

import logging
_logdir = "/var/log/sewasetu"
try:
    os.makedirs(_logdir, exist_ok=True)
    _fh = logging.FileHandler(os.path.join(_logdir, "sewasetu-app.log"))
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s in app: %(message)s"))
    app.logger.addHandler(_fh)
    app.logger.setLevel(logging.INFO)
except Exception:
    pass


def get_db():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", config.get("database", "host")),
        port=os.environ.get("POSTGRES_PORT", config.get("database", "port")),
        dbname=os.environ.get("POSTGRES_DB", config.get("database", "name")),
        user=os.environ.get("POSTGRES_USER", config.get("database", "user")),
        password=os.environ.get("POSTGRES_PASSWORD", config.get("database", "password")),
    )


def sanitize(value, maxlen=100):
    # Trim whitespace and cap at the column width, counting characters (not
    # bytes) so Assamese/Bangla names are stored intact.
    if value is None:
        return ""
    return value.strip()[:maxlen]


def hash_password(p):
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def send_sms(mobile, text):
    try:
        requests.post(SMS_GATEWAY_URL + "/api/send",
                      json={"to": mobile, "text": text}, timeout=5)
    except Exception as e:
        app.logger.error("sms gateway error: %s" % e)


def deadline_remaining():
    delta = SCHEME_DEADLINE - now_ist()
    if delta.total_seconds() <= 0:
        return None
    return int(delta.total_seconds() // 3600)


VALID_TRANSITIONS = {
    "PENDING": {"APPROVED", "REJECTED", "WITHDRAWN", "DEEMED_APPROVED"},
    "APPROVED": set(),
    "REJECTED": set(),
    "WITHDRAWN": set(),
    "DEEMED_APPROVED": set(),
}


def can_transition(current_status, new_status):
    """Statutory welfare state machine: PENDING applications can transition to
    APPROVED, REJECTED, WITHDRAWN, or DEEMED_APPROVED. All resulting states are terminal."""
    return (new_status or "").upper() in VALID_TRANSITIONS.get((current_status or "").upper(), set())


def new_application_no(cur=None):
    for _ in range(15):
        candidate = "SSP" + datetime.now().strftime("%y") + str(random.randint(100000, 999999))
        if cur:
            cur.execute("SELECT 1 FROM applications WHERE application_no = %s", (candidate,))
            if not cur.fetchone():
                return candidate
        else:
            return candidate
    return candidate


def write_audit(cur, app_id, action, actor, note=""):
    cur.execute("INSERT INTO audit_log (application_id, action, actor, note, at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (app_id, action, actor, note, datetime.now()))


# ---------------------------------------------------------------------------
# Scheme rules: the single source of truth for what an application must satisfy.
# Every channel that creates an application (the web form, any API, any batch
# import) MUST go through validate_application() and create_application() so
# that no channel admits an application another channel would refuse.
# ---------------------------------------------------------------------------

def parse_dob(raw):
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def age_on(dob, on):
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def validate_application(data, doc_path):
    """Validate a complete application. Returns (errors, cleaned).

    `errors` is a list of plain-language problems (empty when valid);
    `cleaned` holds the normalised values ready for create_application().
    """
    errors = []
    cleaned = {
        "applicant_name": sanitize(data.get("applicant_name")),
        "village": (data.get("village") or "").strip(),
        "block": (data.get("block") or "").strip(),
        "gender": data.get("gender") or "",
        "marital_status": data.get("marital_status") or "",
        "husband_name": (data.get("husband_name") or "").strip(),
        "husband_employer": "",  # no longer collected (not a scheme requirement)
        "bank_account": re.sub(r"[\s-]", "", data.get("bank_account") or ""),
        "ifsc": re.sub(r"[\s-]", "", (data.get("ifsc") or "")).upper(),
        "doc_path": doc_path or "",
        "dob": None,
    }
    for label, key in (("full name", "applicant_name"), ("village", "village"),
                       ("block", "block"), ("bank account", "bank_account")):
        if not cleaned[key]:
            errors.append("%s is required" % label)
    if cleaned["block"] and cleaned["block"] not in BLOCKS:
        errors.append("block must be one of: " + ", ".join(BLOCKS))
    if cleaned["bank_account"] and not re.fullmatch(r"\d{9,18}", cleaned["bank_account"]):
        errors.append("bank account number must be 9 to 18 digits")
    if cleaned["ifsc"] and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", cleaned["ifsc"]):
        errors.append("IFSC must be 11 characters, e.g. SBIN0003077")
    dob = parse_dob(data.get("dob"))
    if dob is None:
        errors.append("date of birth must be given as DD/MM/YYYY")
    else:
        cleaned["dob"] = dob
        if age_on(dob, now_ist().date()) < MIN_AGE:
            errors.append("applicant must be %d years of age or above" % MIN_AGE)
    if not cleaned["doc_path"]:
        errors.append("age proof document is required")
    if now_ist() > SCHEME_DEADLINE:
        errors.append("the application window has closed")
    return errors, cleaned


def active_application(cur, mobile):
    """The applicant's current live application, if any."""
    cur.execute("SELECT id, application_no, status FROM applications "
                "WHERE mobile = %s AND status IN %s "
                "ORDER BY submitted_at DESC LIMIT 1", (mobile, ACTIVE_STATUSES))
    return cur.fetchone()


def create_application(cur, mobile, cleaned):
    """Insert a validated application; ensure the status-portal account exists.

    The caller commits. Returns (id, application_no).
    """
    app_no = new_application_no(cur)
    cur.execute(
        """INSERT INTO applications
           (application_no, applicant_name, mobile, dob, gender, marital_status,
            husband_name, husband_employer, village, block, bank_account, ifsc,
            doc_path, status, submitted_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING',%s)
           RETURNING id""",
        (app_no, cleaned["applicant_name"], mobile, cleaned["dob"], cleaned["gender"],
         cleaned["marital_status"], cleaned["husband_name"], cleaned["husband_employer"],
         cleaned["village"], cleaned["block"], cleaned["bank_account"], cleaned["ifsc"],
         cleaned["doc_path"], datetime.now()))
    new_id = cur.fetchone()[0]

    # status portal account; password is DOB as DDMMYYYY per dept. circular
    portal_pass = cleaned["dob"].strftime("%d%m%Y")
    cur.execute("SELECT count(*) FROM portal_users WHERE mobile = %s", (mobile,))
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO portal_users (mobile, password_hash) VALUES (%s,%s)",
                    (mobile, hash_password(portal_pass)))
    write_audit(cur, new_id, "SUBMIT", "applicant:%s" % mobile)
    return new_id, app_no


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", hours_left=deadline_remaining())


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/__gateway/", defaults={"subpath": ""})
@app.route("/__gateway/<path:subpath>")
def gateway_proxy(subpath):
    # Convenience proxy to the internal SMS gateway, so the OTP inbox is reachable
    # on the main site without opening a second port on the host. The gateway
    # itself runs only on the internal network.
    try:
        r = requests.get(SMS_GATEWAY_URL + "/" + subpath,
                         params=request.args, timeout=5)
        return (r.content, r.status_code,
                {"Content-Type": r.headers.get("Content-Type", "text/html")})
    except Exception as e:
        return ("SMS gateway unreachable: %s" % e, 502)


# ---------------------------------------------------------------------------
# Application flow: mobile -> OTP -> form steps -> upload -> declaration
# ---------------------------------------------------------------------------

@app.route("/apply", methods=["GET", "POST"])
def apply():
    if deadline_remaining() is None:
        flash("The application window for this scheme has closed.")
        return redirect(url_for("index"))
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        captcha = request.form.get("captcha", "")
        try:
            captcha_ok = int(captcha) == session.get("captcha_answer")
        except (ValueError, TypeError):
            captcha_ok = False
        if not captcha_ok:
            flash("Security check answer is incorrect. Please try again.")
            return render_template("apply.html", captcha_q=make_captcha())
        if len(mobile) != 10 or not mobile.isdigit():
            flash("Please enter a valid 10-digit mobile number.")
            return render_template("apply.html", captcha_q=make_captcha())
        code = str(random.randint(100000, 999999))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO otps (mobile, code, created_at) VALUES (%s, %s, %s)",
                    (mobile, code, datetime.now()))
        conn.commit()
        cur.close(); conn.close()
        send_sms(mobile, "Your Sewa Setu OTP is %s. Valid for 5 minutes." % code)
        session.permanent = True
        session["apply_mobile"] = mobile
        return redirect(url_for("verify"))
    return render_template("apply.html", captcha_q=make_captcha())


def make_captcha():
    a, b = random.randint(1, 9), random.randint(1, 9)
    session["captcha_answer"] = a + b
    return "%d + %d" % (a, b)


@app.route("/verify", methods=["GET", "POST"])
def verify():
    mobile = session.get("apply_mobile")
    if not mobile:
        return redirect(url_for("apply"))
    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT code, created_at FROM otps WHERE mobile = %s "
                    "ORDER BY id DESC LIMIT 1", (mobile,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0] == code:
            age = (datetime.now() - row[1]).total_seconds()
            if age > OTP_VALIDITY_SECONDS:
                app.logger.warning("otp expired mobile=%s age=%ds" % (mobile, int(age)))
                flash("OTP expired. Please request a new OTP.")
                return redirect(url_for("apply"))
            session["verified_mobile"] = mobile
            return redirect(url_for("form_step", step=1))
        flash("Invalid OTP.")
    return render_template("verify.html", mobile=mobile)


@app.route("/form/<int:step>", methods=["GET", "POST"])
def form_step(step):
    if not session.get("verified_mobile"):
        flash("Session expired. Please verify your mobile number again.")
        return redirect(url_for("apply"))
    if step not in (1, 2, 3):
        abort(404)
    if request.method == "POST":
        data = session.get("form_data", {})
        for k, v in request.form.items():
            data[k] = v
        session["form_data"] = data
        if step < 3:
            return redirect(url_for("form_step", step=step + 1))
        return redirect(url_for("upload"))
    return render_template("form_step%d.html" % step,
                           data=session.get("form_data", {}), blocks=BLOCKS)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not session.get("verified_mobile"):
        flash("Session expired. Please verify your mobile number again.")
        return redirect(url_for("apply"))
    if request.method == "POST":
        f = request.files.get("document")
        if f is None or f.filename == "":
            flash("Please choose a file to upload (JPG, PNG or PDF, up to 5 MB).")
            return render_template("upload.html")
        filename = f.filename.lower()
        content = f.read()
        if not filename.rsplit(".", 1)[-1] in ("pdf", "jpg", "jpeg", "png"):
            flash("Please upload a JPG, PNG or PDF file.")
            return render_template("upload.html")
        if len(content) > 5 * 1024 * 1024:
            flash("File is larger than 5 MB. Please upload a smaller file.")
            return render_template("upload.html")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        path = os.path.join(UPLOAD_DIR, "%s_%s" % (session["verified_mobile"], filename))
        with open(path, "wb") as out:
            out.write(content)
        session["doc_path"] = path
        return redirect(url_for("declaration"))
    return render_template("upload.html")


@app.route("/declaration", methods=["GET", "POST"])
def declaration():
    if not session.get("verified_mobile"):
        flash("Session expired. Please verify your mobile number again.")
        return redirect(url_for("apply"))
    if request.method == "POST":
        return handle_submission()
    # Preview everything before the applicant commits.
    data = session.get("form_data", {})
    errors, _ = validate_application(data, session.get("doc_path", ""))
    return render_template("declaration.html", data=data, errors=errors,
                           doc_name=os.path.basename(session.get("doc_path", "") or ""))


def handle_submission():
    mobile = session.get("verified_mobile")
    data = session.get("form_data", {})
    errors, cleaned = validate_application(data, session.get("doc_path", ""))
    if errors:
        flash("Please correct the following before submitting: " + "; ".join(errors) + ".")
        return redirect(url_for("form_step", step=1))

    conn = get_db()
    cur = conn.cursor()
    existing = active_application(cur, mobile)
    if existing:
        cur.close(); conn.close()
        flash("Application %s (%s) already exists for this mobile number. A pending "
              "application can be withdrawn from the status portal if you need to "
              "apply afresh." % (existing[1], existing[2]))
        return redirect(url_for("index"))

    new_id, app_no = create_application(cur, mobile, cleaned)
    conn.commit()
    cur.close(); conn.close()

    session.pop("form_data", None)
    session.pop("doc_path", None)
    session.pop("verified_mobile", None)
    # The applicant just proved ownership of this mobile by OTP, so let them
    # see their application and download the acknowledgment without a second login.
    session["logged_in"] = True
    session["portal_mobile"] = mobile
    send_sms(mobile, "Sewa Setu: application %s received. Track at the status portal "
                     "with mobile no. and password (DOB as DDMMYYYY)." % app_no)
    return render_template("confirmation.html", app_no=app_no, app_id=new_id)


def generate_acknowledgment(cur, app_id):
    cur.execute("SELECT application_no, applicant_name, mobile, dob, village, block, "
                "bank_account, ifsc, submitted_at, status FROM applications WHERE id = %s",
                (app_id,))
    row = cur.fetchone()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "GOVERNMENT OF PURVANCHAL", ln=1, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Department of Social Welfare", ln=1, align="C")
    pdf.cell(0, 8, "Old Age Pension Scheme - Acknowledgment", ln=1, align="C")
    pdf.ln(4)
    # letterhead rules
    pdf.line(10, 12, 200, 12)
    pdf.line(10, 282, 200, 282)
    labels = ["Application No", "Applicant Name", "Mobile", "Date of Birth",
              "Village", "Block", "Bank Account", "IFSC", "Submitted At", "Status"]
    pdf.set_font("Helvetica", "", 10)
    for label, val in zip(labels, row):
        try:
            pdf.cell(60, 8, label, border=1)
            pdf.cell(0, 8, str(val), border=1, ln=1)
        except Exception:
            pdf.cell(0, 8, "?", border=1, ln=1)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "This is a computer generated acknowledgment. Processing SLA "
                         "as per the Purvanchal Right to Public Services Act applies.")
    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Status portal (citizen login)
# ---------------------------------------------------------------------------

@app.route("/status", methods=["GET", "POST"])
def status_login():
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM portal_users WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0] == hash_password(password):
            session["logged_in"] = True
            session["portal_mobile"] = mobile
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM applications WHERE mobile = %s "
                        "ORDER BY submitted_at DESC LIMIT 1", (mobile,))
            r = cur.fetchone()
            cur.close(); conn.close()
            if r:
                return redirect(url_for("view_application", app_id=r[0]))
            flash("No application found for this mobile number.")
            return redirect(url_for("status_login"))
        flash("Mobile number or password is incorrect. The password is your date of "
              "birth as DDMMYYYY.")
    return render_template("status_login.html")


@app.route("/application/<int:app_id>")
def view_application(app_id):
    if not session.get("logged_in"):
        flash("Please login to view application status.")
        return redirect(url_for("status_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT application_no, applicant_name, mobile, dob, village, block, "
                "bank_account, ifsc, status, submitted_at, decided_at "
                "FROM applications WHERE id = %s AND mobile = %s",
                (app_id, session.get("portal_mobile")))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        abort(404)
    return render_template("application.html", a=row, app_id=app_id)


@app.route("/application/<int:app_id>/withdraw", methods=["POST"])
def withdraw_application(app_id):
    """Applicant withdraws their own PENDING application so they can apply afresh."""
    if not session.get("logged_in") or not session.get("portal_mobile"):
        flash("Please login to manage your application.")
        return redirect(url_for("status_login"))
    mobile = session["portal_mobile"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE applications SET status = 'WITHDRAWN', decided_at = %s, "
                "decided_by = 'APPLICANT' WHERE id = %s AND mobile = %s "
                "AND status = 'PENDING' RETURNING application_no",
                (datetime.now(), app_id, mobile))
    row = cur.fetchone()
    if row:
        write_audit(cur, app_id, "WITHDRAW", "applicant:%s" % mobile)
        conn.commit()
        flash("Application %s has been withdrawn. You may submit a new application." % row[0])
    else:
        flash("Only a pending application can be withdrawn.")
    cur.close(); conn.close()
    return redirect(url_for("view_application", app_id=app_id))


@app.route("/ack/<int:app_id>.pdf")
def ack_pdf(app_id):
    if not session.get("admin"):
        conn0 = get_db(); c0 = conn0.cursor()
        c0.execute("SELECT 1 FROM applications WHERE id = %s AND mobile = %s",
                   (app_id, session.get("portal_mobile")))
        owned = c0.fetchone()
        c0.close(); conn0.close()
        if not owned:
            abort(403)
    path = os.path.join(UPLOAD_DIR, "ack", "%d.pdf" % app_id)
    if not os.path.exists(path):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM applications WHERE id = %s", (app_id,))
        if not cur.fetchone():
            cur.close(); conn.close()
            abort(404)
        data = generate_acknowledgment(cur, app_id)
        cur.close(); conn.close()
        return send_file(io.BytesIO(data), mimetype="application/pdf")
    return send_file(path, mimetype="application/pdf")


@app.route("/status/reset", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        mobile = request.form.get("mobile", "")
        conn = get_db()
        cur = conn.cursor()
        # fetch account for reset
        cur.execute("SELECT mobile FROM portal_users WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        if row:
            cur.execute("SELECT id, dob FROM applications WHERE mobile = %s ORDER BY id DESC LIMIT 1", (mobile,))
            r2 = cur.fetchone()
            if r2:
                app_id, dob_val = r2
                newpass = dob_val.strftime("%d%m%Y")
                cur.execute("UPDATE portal_users SET password_hash = %s WHERE mobile = %s",
                            (hash_password(newpass), row[0]))
                write_audit(cur, app_id, "RESET_PASSWORD", "system:citizen-reset", "Password reset to Date of Birth requested")
                conn.commit()
                send_sms(row[0], "Sewa Setu: your password has been reset to your "
                                 "date of birth (DDMMYYYY).")
        cur.close(); conn.close()
        flash("If the mobile number exists, the password has been reset and sent by SMS.")
    return render_template("reset.html")


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (ADMIN_PASSWORD and request.form.get("username") == ADMIN_USERNAME and
                request.form.get("password") == ADMIN_PASSWORD):
            session["logged_in"] = True
            session["admin"] = True
            session["admin_user"] = ADMIN_USERNAME
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials.")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status, count(*) FROM applications GROUP BY status")
    by_status = cur.fetchall()
    cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING' "
                "AND submitted_at < %s", (datetime.now() - timedelta(days=SLA_DAYS),))
    overdue = cur.fetchone()[0]
    cur.execute("SELECT block, count(*) FROM applications WHERE status = 'PENDING' "
                "GROUP BY block ORDER BY count(*) DESC")
    by_block = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_dashboard.html", by_status=by_status,
                           overdue=overdue, by_block=by_block, sla=SLA_DAYS)


@app.route("/admin/applications")
def admin_list():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    status = request.args.get("status", "PENDING")
    mobile = request.args.get("mobile", "").strip()
    page = int(request.args.get("page", 1))
    conn = get_db()
    cur = conn.cursor()
    if mobile:
        cur.execute("SELECT id, application_no, applicant_name, mobile, block, status, "
                    "submitted_at FROM applications WHERE mobile = %s ORDER BY submitted_at ASC",
                    (mobile,))
        status = "mobile %s" % mobile
    else:
        cur.execute("SELECT id, application_no, applicant_name, mobile, block, status, "
                    "submitted_at FROM applications WHERE status = %s "
                    "ORDER BY submitted_at ASC LIMIT 50 OFFSET %s",
                    (status, (page - 1) * 50))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_list.html", rows=rows, status=status, page=page, mobile=mobile)


@app.route("/admin/application/<int:app_id>")
def admin_view(app_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT application_no, applicant_name, mobile, dob, gender, "
                "marital_status, village, block, bank_account, ifsc, doc_path, "
                "status, submitted_at, decided_at, decided_by "
                "FROM applications WHERE id = %s", (app_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        abort(404)
    cur.execute("SELECT at, action, actor, note FROM audit_log "
                "WHERE application_id = %s ORDER BY at ASC", (app_id,))
    audit = cur.fetchall()
    cur.close(); conn.close()
    return render_template("admin_view.html", a=row, app_id=app_id, audit=audit)


def _admin_decide(app_id, new_status, note):
    """Approve/reject a PENDING application, recording who decided and when."""
    if not session.get("admin"):
        abort(403)
    actor = session.get("admin_user", ADMIN_USERNAME)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM applications WHERE id = %s", (app_id,))
    cur_row = cur.fetchone()
    if not cur_row:
        cur.close(); conn.close()
        abort(404)
    if not can_transition(cur_row[0], new_status):
        cur.close(); conn.close()
        flash("Cannot transition application from status %s to %s." % (cur_row[0], new_status))
        return redirect(url_for("admin_view", app_id=app_id))

    cur.execute("UPDATE applications SET status = %s, decided_at = %s, decided_by = %s "
                "WHERE id = %s AND status = 'PENDING' RETURNING application_no",
                (new_status, datetime.now(), actor, app_id))
    row = cur.fetchone()
    if row:
        write_audit(cur, app_id, new_status, "admin:%s" % actor, note)
        conn.commit()
        flash("Application %s %s." % (row[0], new_status.lower()))
    else:
        flash("Only a pending application can be decided.")
    cur.close(); conn.close()
    return redirect(url_for("admin_view", app_id=app_id))


@app.route("/admin/approve/<int:app_id>", methods=["POST"])
def admin_approve(app_id):
    return _admin_decide(app_id, "APPROVED", request.form.get("note", ""))


@app.route("/admin/reject/<int:app_id>", methods=["POST"])
def admin_reject(app_id):
    return _admin_decide(app_id, "REJECTED", request.form.get("note", ""))


from oauth import oauth as _oauth_blueprint   # noqa: E402  (needs the definitions above)
app.register_blueprint(_oauth_blueprint)

import mcp_server as _mcp_module
app.register_blueprint(_mcp_module.mcp_bp)

import evals as _evals_module

@app.route("/eval-dashboard")
def eval_dashboard():
    summary, results = _evals_module.get_eval_results()
    return render_template("eval_dashboard.html", summary=summary, results=results)

@app.route("/api/evals/run", methods=["POST"])
def api_run_evals():
    summary, results = _evals_module.run_all_evals()
    return jsonify({"summary": summary, "results": results})

@app.route("/assistant")
def assistant():
    return render_template("assistant.html")

@app.route("/api/citizen-assistant", methods=["POST"])
def api_citizen_assistant():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "").strip()
    if not msg:
        return jsonify({"reply": "Namaskar! How can I assist you with the Old Age Pension scheme today?", "action_links": []})

    msg_lower = msg.lower()
    action_links = []
    reply = ""

    # Security Guard 1: Prompt Injection & Jailbreak Defense
    injection_patterns = [
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
        r"system\s+prompt",
        r"override\s+security",
        r"jailbreak",
        r"developer\s+mode",
        r"disregard\s+rules",
        r"act\s+as\s+(?:an?\s+)?admin"
    ]
    for pattern in injection_patterns:
        if re.search(pattern, msg_lower):
            return jsonify({
                "reply": "<strong>Security Notice:</strong> Instructions attempting to override system prompts, role boundaries, or security constraints are strictly blocked. The assistant operates exclusively within statutory scheme rules.",
                "action_links": []
            })

    # Security Guard 2: Intercept Administrative Command Attempts via Natural Language
    admin_intent_patterns = [
        r"\b(?:approve|reject|authorize)\s+(?:application|case|SSP\d+)",
        r"\bchange\s+status\s+to\s+(?:approved|rejected)",
        r"\bmark\s+(?:as\s+)?(?:approved|rejected)",
        r"\bgrant\s+officer\s+access"
    ]
    for pattern in admin_intent_patterns:
        if re.search(pattern, msg_lower):
            return jsonify({
                "reply": "<strong>Administrative Action Notice:</strong> Decisions to approve, reject, or alter application statuses cannot be executed via natural language instructions on this citizen assistant. Administrative actions are strictly restricted to authorized Block Welfare Officers logged in via <a href='/admin'>Departmental Admin</a> or authenticated via the Officer MCP server (<code>/mcp/officer</code>) with verified RS256 credentials.",
                "action_links": [{"label": "Officer Login", "url": "/admin"}, {"label": "Officer MCP Info", "url": "/mcp/officer"}]
            })

    # Security Guard 3: Block Credential & Infrastructure Extraction
    cred_patterns = [
        r"(?:what\s+is|show\s+me|give\s+me|tell\s+me)\s+(?:the\s+)?(?:admin|root|database|db|postgres)\s+password",
        r"(?:what\s+is|show\s+me|give\s+me)\s+(?:the\s+)?(?:jwt|signing|private|secret)\s+key",
        r"(?:what\s+is|show\s+me|give\s+me)\s+(?:the\s+)?api\s+key"
    ]
    for pattern in cred_patterns:
        if re.search(pattern, msg_lower):
            return jsonify({
                "reply": "<strong>Security &amp; Privacy Protection:</strong> System passwords, cryptographic signing keys, API credentials, and internal infrastructure configurations are strictly protected and never disclosed.",
                "action_links": []
            })

    # Check for mobile number or application number
    mobile_match = re.search(r"\b([6-9]\d{9})\b", msg)
    app_no_match = re.search(r"\b(SSP\d+)\b", msg, re.IGNORECASE)

    if mobile_match or app_no_match or "status" in msg_lower or "track" in msg_lower or "check my" in msg_lower:
        query_val = mobile_match.group(1) if mobile_match else (app_no_match.group(1).upper() if app_no_match else None)
        if query_val:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, application_no, applicant_name, status, block, village,
                           submitted_at, decided_at, decided_by, dob
                    FROM applications
                    WHERE mobile = %s OR application_no = %s
                    ORDER BY id DESC LIMIT 1
                """, (query_val, query_val))
                row = cur.fetchone()

                if row:
                    app_id, app_no, name, status, block, village, sub_at, dec_at, dec_by, dob = row
                    cur.execute("SELECT action, actor, note, at FROM audit_log WHERE application_id = %s ORDER BY id DESC LIMIT 3", (app_id,))
                    audits = cur.fetchall()
                    cur.close(); conn.close()

                    days_elapsed = (now_ist() - sub_at.replace(tzinfo=None)).days if sub_at else 0
                    days_left = max(0, SLA_DAYS - days_elapsed)

                    if status == "PENDING":
                        reply = (
                            f"<strong>Application Found:</strong> {app_no} for <strong>{name}</strong><br>"
                            f"Status: <span class='status-pill status-pending'>PENDING</span> in {block} block.<br>"
                            f"Submitted on: {sub_at.strftime('%d/%m/%Y')}.<br>"
                            f"<strong>Statutory RTPS Guarantee:</strong> {days_left} days remaining of the 15-day SLA. "
                            f"If an officer does not decide by day 15, your application stands <em>Deemed Approved</em> by law.<br>"
                            f"Track online at <code>/status</code> using your mobile and Date of Birth as password (DDMMYYYY format)."
                        )
                        action_links = [
                            {"label": "Open Status Portal", "url": "/status"},
                            {"label": "Download Stamped Acknowledgment", "url": f"/ack/{app_id}.pdf"}
                        ]
                    elif status in ("APPROVED", "DEEMED_APPROVED"):
                        badge_cls = "status-approved" if status == "APPROVED" else "status-deemed_approved"
                        label = "APPROVED" if status == "APPROVED" else "DEEMED APPROVED (RTPS Statutory)"
                        by_txt = f"by Officer {dec_by}" if status == "APPROVED" else "automatically under RTPS 15-day statutory SLA"
                        reply = (
                            f"<strong>Application Found:</strong> {app_no} for <strong>{name}</strong><br>"
                            f"Status: <span class='status-pill {badge_cls}'>{label}</span><br>"
                            f"Decision: Processed {by_txt} on {dec_at.strftime('%d/%m/%Y') if dec_at else 'recently'}.<br>"
                            f"Your monthly pension of <strong>₹250/month</strong> will be disbursed via Direct Benefit Transfer (DBT) to your registered bank account."
                        )
                        action_links = [
                            {"label": "View Status Record", "url": "/status"},
                            {"label": "Download Certificate/Ack", "url": f"/ack/{app_id}.pdf"}
                        ]
                    elif status == "REJECTED":
                        note = audits[0][2] if audits and audits[0][2] else "Documentation did not meet statutory criteria."
                        reply = (
                            f"<strong>Application Found:</strong> {app_no} for <strong>{name}</strong><br>"
                            f"Status: <span class='status-pill status-rejected'>REJECTED</span><br>"
                            f"Reason given by block officer: <em>\"{note}\"</em><br>"
                            f"<strong>Important:</strong> Your mobile number is now unblocked. You can obtain a clearer document and submit a fresh application right away."
                        )
                        action_links = [
                            {"label": "Apply Again", "url": "/apply"},
                            {"label": "View Status Details", "url": "/status"}
                        ]
                    elif status == "WITHDRAWN":
                        reply = (
                            f"Application {app_no} was <strong>WITHDRAWN</strong> voluntarily.<br>"
                            f"Your mobile number is completely clear with no active applications. You may submit a corrected application anytime."
                        )
                        action_links = [{"label": "Start Fresh Application", "url": "/apply"}]
                    return jsonify({"reply": reply, "action_links": action_links})
                else:
                    cur.close(); conn.close()
                    reply = (
                        f"No application was found matching <code>{query_val}</code> in the portal database.<br>"
                        f"If you haven't applied yet and are 60 years or older, you can begin your application online."
                    )
                    action_links = [{"label": "Apply for Pension", "url": "/apply"}]
                    return jsonify({"reply": reply, "action_links": action_links})
            except Exception as e:
                app.logger.error("Error querying application status: %s", e)
                return jsonify({
                    "reply": "We encountered an issue looking up records in the portal database. Please try again or visit <a href='/status'>/status</a> directly.",
                    "action_links": [{"label": "Open Status Portal", "url": "/status"}]
                })
        else:
            reply = (
                "To check your application status, please provide your <strong>10-digit mobile number</strong> "
                "(e.g., <em>9876500001</em>) or your <strong>Application Number</strong> (e.g., <em>SSP26318977</em>)."
            )
            action_links = [{"label": "Go to Status Portal", "url": "/status"}]
            return jsonify({"reply": reply, "action_links": action_links})

    # Age / DOB / Eligibility Check
    age_match = re.search(r"\b(\d{2})\s*(?:years|yrs|age)\b", msg_lower)
    if not age_match:
        age_match = re.search(r"\bage\s*(\d{2})\b", msg_lower)
    dob_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", msg)

    if age_match or dob_match or "eligible" in msg_lower or "qualify" in msg_lower or "criteria" in msg_lower:
        cal_age = None
        if dob_match:
            try:
                d, m, y = int(dob_match.group(1)), int(dob_match.group(2)), int(dob_match.group(3))
                dob_dt = datetime(y, m, d)
                today = now_ist()
                cal_age = today.year - dob_dt.year - ((today.month, today.day) < (dob_dt.month, dob_dt.day))
            except Exception:
                pass
        elif age_match:
            cal_age = int(age_match.group(1))

        if cal_age is not None:
            if cal_age >= MIN_AGE:
                reply = (
                    f"<strong>Eligible on Age:</strong> An applicant aged <strong>{cal_age}</strong> meets the statutory minimum age of {MIN_AGE} years!<br>"
                    f"<strong>Territorial Coverage:</strong> Available to residents of Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, and Khelua blocks.<br>"
                    f"<strong>Benefit:</strong> ₹250 per month deposited directly into your bank account via DBT."
                )
                action_links = [
                    {"label": "Apply Now", "url": "/apply"},
                    {"label": "Read Scheme Guidelines", "url": "/about"}
                ]
            else:
                years_left = MIN_AGE - cal_age
                reply = (
                    f"<strong>Not Currently Eligible:</strong> The statutory minimum age is <strong>{MIN_AGE} years</strong>. "
                    f"An individual aged {cal_age} will become eligible in ~{years_left} year(s).<br>"
                    f"Under state law, applications below age 60 cannot be recorded."
                )
                action_links = [{"label": "View Scheme Rules", "url": "/about"}]
            return jsonify({"reply": reply, "action_links": action_links})
        else:
            reply = (
                f"<strong>Eligibility Requirements:</strong><br>"
                f"1. <strong>Age:</strong> Must be <strong>{MIN_AGE} years or older</strong>.<br>"
                f"2. <strong>Jurisdiction:</strong> Resident of designated blocks (Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua).<br>"
                f"3. <strong>Single Application:</strong> Applicant cannot have another active pension application.<br>"
                f"Tell me your age or Date of Birth (DD/MM/YYYY) and block to verify instantly!"
            )
            action_links = [{"label": "Check Eligibility Online", "url": "/about"}]
            return jsonify({"reply": reply, "action_links": action_links})

    # Documents question
    if "document" in msg_lower or "proof" in msg_lower or "voter" in msg_lower or "aadhaar" in msg_lower or "bank" in msg_lower:
        reply = (
            "<strong>Required Documents:</strong><br>"
            "1. <strong>Age Proof (Upload up to 5MB):</strong> Any one of Voter ID (EPIC), Aadhaar Card, School Certificate, or Birth Certificate.<br>"
            "2. <strong>Active Bank Details:</strong> Savings Bank Account Number & IFSC (e.g. Jan Dhan or any scheduled bank) in the applicant's name.<br>"
            "3. <strong>Working Mobile Number:</strong> Required to receive SMS OTP and status updates."
        )
        action_links = [
            {"label": "Start Application", "url": "/apply"},
            {"label": "Scheme Details", "url": "/about"}
        ]
        return jsonify({"reply": reply, "action_links": action_links})

    # RTPS / SLA question
    if "15 day" in msg_lower or "sla" in msg_lower or "deemed" in msg_lower or "rtps" in msg_lower or "how long" in msg_lower or "time" in msg_lower:
        reply = (
            "<strong>Purvanchal Right to Public Services (RTPS) Act Guarantee:</strong><br>"
            f"Under state law, your application must be reviewed within <strong>{SLA_DAYS} statutory days</strong>.<br>"
            "If the block welfare officer does not approve or reject your application within 15 days, "
            "the system's nightly automated scheduler marks it <strong>DEEMED APPROVED</strong> automatically. "
            "You are legally protected against administrative delays."
        )
        action_links = [{"label": "Check My Status", "url": "/status"}]
        return jsonify({"reply": reply, "action_links": action_links})

    # Withdrawal / Edit question
    if "withdraw" in msg_lower or "cancel" in msg_lower or "change" in msg_lower or "mistake" in msg_lower or "fix" in msg_lower:
        reply = (
            "<strong>Voluntary Withdrawal & Corrections:</strong><br>"
            "If you entered an incorrect bank account or need to change details, you can withdraw your pending application:<br>"
            "1. Sign in to the <a href='/status'>Status Portal</a> with your Mobile and Date of Birth password (DDMMYYYY).<br>"
            "2. Click <strong>'Withdraw Application'</strong>.<br>"
            "3. Once withdrawn, your mobile number is instantly unblocked, and you can submit a clean, corrected application at <code>/apply</code> immediately."
        )
        action_links = [
            {"label": "Go to Status Portal", "url": "/status"},
            {"label": "Apply for Pension", "url": "/apply"}
        ]
        return jsonify({"reply": reply, "action_links": action_links})

    # Default fallback
    reply = (
        "Namaskar! I can help you with:<br>"
        "• Checking if you are eligible (tell me your age or Date of Birth)<br>"
        "• Checking the status of an existing application (provide your mobile number)<br>"
        "• Explaining required documents and the 15-day RTPS statutory guarantee<br>"
        "• Withdrawing an application to correct details<br>"
        "What would you like assistance with?"
    )
    action_links = [
        {"label": "Apply for Pension", "url": "/apply"},
        {"label": "Check Status", "url": "/status"},
        {"label": "Scheme Information", "url": "/about"}
    ]
    return jsonify({"reply": reply, "action_links": action_links})

@app.route("/health")
def health():
    db_ok = False
    app_count = 0
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM applications")
        app_count = cur.fetchone()[0]
        cur.close(); conn.close()
        db_ok = True
    except Exception as e:
        app.logger.error("Health check DB error: %s" % e)

    sms_ok = False
    try:
        r = requests.get(SMS_GATEWAY_URL + "/api/messages", timeout=2)
        sms_ok = (r.status_code == 200)
    except Exception:
        pass

    status_code = 200 if (db_ok and sms_ok) else 503
    return jsonify({
        "status": "healthy" if status_code == 200 else "degraded",
        "timestamp": now_ist().isoformat(),
        "database": {"connected": db_ok, "total_applications": app_count},
        "sms_gateway": {"connected": sms_ok},
        "scheme": {
            "window_open": deadline_remaining() is not None,
            "deadline": SCHEME_DEADLINE.strftime("%Y-%m-%d %H:%M:%S")
        }
    }), status_code

@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _wants_json():
    return (
        request.path.startswith("/api/") or
        request.path.startswith("/mcp/") or
        request.is_json or
        "application/json" in request.headers.get("Accept", "")
    )


@app.errorhandler(400)
def bad_request(e):
    if _wants_json():
        return jsonify({
            "error": "bad_request",
            "message": str(getattr(e, "description", "Bad Request")),
            "status_code": 400
        }), 400
    return render_template("error.html", code=400, title="400 — Bad Request",
                           message="The request could not be processed due to invalid parameters or formatting."), 400


@app.errorhandler(403)
def forbidden(e):
    if _wants_json():
        return jsonify({
            "error": "forbidden",
            "message": str(getattr(e, "description", "Access Forbidden")),
            "status_code": 403
        }), 403
    return render_template("error.html", code=403, title="403 — Access Forbidden",
                           message="You do not have administrative or ownership permissions to access this page or record."), 403


@app.errorhandler(404)
def not_found(e):
    if _wants_json():
        return jsonify({
            "error": "not_found",
            "message": str(getattr(e, "description", "Resource Not Found")),
            "status_code": 404
        }), 404
    return render_template("error.html", code=404, title="404 — Page Not Found",
                           message="The requested welfare portal page or application record was not found."), 404


@app.errorhandler(500)
def internal_server_error(e):
    if _wants_json():
        return jsonify({
            "error": "internal_server_error",
            "message": "An internal server error occurred while processing the request.",
            "status_code": 500
        }), 500
    return render_template("error.html", code=500, title="500 — Server Error",
                           message="The welfare service encountered an unexpected error. The system administrator has been alerted."), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
