#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Compatibility Layer for Sewa Setu.
Provides transparent SQLite fallback when PostgreSQL or psycopg2 is not available
(such as in Wasmer Edge, WASI/WASIX sandboxes, or serverless environments).
"""
import os
import re
import sqlite3
import hashlib
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "sewasetu.sqlite")


class SQLiteCompatCursor:
    def __init__(self, cursor):
        self._cur = cursor

    def _convert_query_and_params(self, sql, params):
        # Convert NOW() to CURRENT_TIMESTAMP
        clean_sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)
        # Convert ILIKE to LIKE for case-insensitive match in SQLite
        clean_sql = re.sub(r'\bILIKE\b', 'LIKE', clean_sql, flags=re.IGNORECASE)
        # Convert '= ANY(%s)' to 'IN %s' for SQLite compatibility
        clean_sql = re.sub(r'=\s*ANY\s*\(%s\)', 'IN %s', clean_sql, flags=re.IGNORECASE)

        if params is None:
            clean_sql = clean_sql.replace('%s', '?')
            return clean_sql, None

        if '%s' not in clean_sql:
            if isinstance(params, (list, tuple)):
                return clean_sql, tuple(params)
            return clean_sql, (params,)

        if not isinstance(params, (list, tuple)):
            params = [params]

        # Handle tuple parameters like `status IN %s`
        new_sql = ""
        new_params = []
        parts = clean_sql.split('%s')

        for i, part in enumerate(parts[:-1]):
            if i < len(params):
                val = params[i]
                if isinstance(val, (tuple, list)):
                    placeholders = ', '.join(['?'] * len(val))
                    # Check if part already ends with '(' (e.g. `IN (%s)`)
                    if part.rstrip().endswith('('):
                        new_sql += part + placeholders
                    else:
                        new_sql += part + '(' + placeholders + ')'
                    new_params.extend(val)
                else:
                    new_sql += part + '?'
                    new_params.append(val)
            else:
                new_sql += part + '?'
        new_sql += parts[-1]

        return new_sql, tuple(new_params)

    def execute(self, sql, params=None):
        clean_sql, clean_params = self._convert_query_and_params(sql, params)
        if clean_params is None:
            return self._cur.execute(clean_sql)
        else:
            return self._cur.execute(clean_sql, clean_params)

    def executemany(self, sql, seq_of_params):
        if not seq_of_params:
            return
        sample_sql, _ = self._convert_query_and_params(sql, seq_of_params[0])
        converted_seq = []
        for p in seq_of_params:
            _, clean_p = self._convert_query_and_params(sql, p)
            converted_seq.append(clean_p)
        return self._cur.executemany(sample_sql, converted_seq)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        if size is None:
            return self._cur.fetchmany()
        return self._cur.fetchmany(size)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class SQLiteCompatConnection:
    def __init__(self, db_path):
        # Allow multi-threaded use common in Flask
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self._conn.row_factory = sqlite3.Row

    def cursor(self, *args, **kwargs):
        return SQLiteCompatCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def init_sqlite_schema(conn):
    """Initializes tables, indexes, and seeded data in SQLite if not present."""
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        application_no  VARCHAR(20),
        applicant_name  VARCHAR(100),
        mobile          VARCHAR(15),
        dob             DATE,
        gender          VARCHAR(10),
        marital_status  VARCHAR(20),
        husband_name    VARCHAR(100),
        husband_employer VARCHAR(100),
        village         VARCHAR(100),
        block           VARCHAR(50),
        bank_account    VARCHAR(30),
        ifsc            VARCHAR(15),
        doc_path        VARCHAR(200),
        status          VARCHAR(20) DEFAULT 'PENDING',
        submitted_at    TIMESTAMP,
        decided_at      TIMESTAMP,
        decided_by      VARCHAR(50)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portal_users (
        mobile        VARCHAR(15) PRIMARY KEY,
        password_hash VARCHAR(80)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS otps (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        mobile     VARCHAR(15),
        code       VARCHAR(6),
        created_at TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER,
        action         VARCHAR(20),
        actor          VARCHAR(50),
        note           VARCHAR(500),
        at             TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_keys (
        kid         VARCHAR(32) PRIMARY KEY,
        private_pem TEXT,
        created_at  TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_clients (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id     VARCHAR(300) UNIQUE,
        client_name   VARCHAR(100),
        redirect_uris TEXT,
        secret_hash   VARCHAR(64),
        kind          VARCHAR(10),
        created_at    TIMESTAMP,
        fetched_at    TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_requests (
        id             VARCHAR(64) PRIMARY KEY,
        params         TEXT,
        subject        VARCHAR(80),
        role           VARCHAR(10),
        pending_mobile VARCHAR(15),
        created_at     TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_codes (
        code_hash      VARCHAR(64) PRIMARY KEY,
        client_id      VARCHAR(300),
        redirect_uri   VARCHAR(500),
        scope          VARCHAR(20),
        code_challenge VARCHAR(128),
        resource       VARCHAR(300),
        subject        VARCHAR(80),
        role           VARCHAR(10),
        created_at     TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
        token_hash  VARCHAR(64) PRIMARY KEY,
        client_id   VARCHAR(300),
        client_name VARCHAR(100),
        subject     VARCHAR(80),
        role        VARCHAR(10),
        scope       VARCHAR(20),
        resource    VARCHAR(300),
        created_at  TIMESTAMP,
        expires_at  TIMESTAMP,
        revoked_at  TIMESTAMP
    );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_app_mobile ON applications(mobile);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_active_app_mobile ON applications (mobile) WHERE status IN ('PENDING', 'APPROVED', 'DEEMED_APPROVED');")
    conn.commit()

    # Seed with initial records if empty
    cur.execute("SELECT COUNT(*) FROM applications")
    count = cur.fetchone()[0]
    if count == 0:
        now = datetime.now()
        # Seed 1: Phuleswari Saikia (Pending, Sonari)
        cur.execute("""
        INSERT INTO applications (application_no, applicant_name, mobile, dob, gender, marital_status, village, block, bank_account, ifsc, status, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('SSP26840970', 'Phuleswari Saikia', '9876500001', '1955-03-10', 'Female', 'Widow', 'Borhat', 'Sonari', '14220100054321', 'UCBA0001422', 'PENDING', now - timedelta(days=2)))

        p_hash = hashlib.sha256('10031955'.encode('utf-8')).hexdigest()
        cur.execute("INSERT OR REPLACE INTO portal_users (mobile, password_hash) VALUES (?, ?)", ('9876500001', p_hash))

        # Seed 2: Padmini Das (Deemed Approved, RTPS 16 days ago)
        cur.execute("""
        INSERT INTO applications (application_no, applicant_name, mobile, dob, gender, marital_status, village, block, bank_account, ifsc, status, submitted_at, decided_at, decided_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('SSP26987607', 'Padmini Das', '9876500007', '1951-04-02', 'Female', 'Widow', 'Sepon', 'Sonari', '2049101002231', 'SBIN0002049', 'DEEMED_APPROVED', now - timedelta(days=16), now - timedelta(days=1), 'RTPS-AUTO'))

        p_hash7 = hashlib.sha256('02041951'.encode('utf-8')).hexdigest()
        cur.execute("INSERT OR REPLACE INTO portal_users (mobile, password_hash) VALUES (?, ?)", ('9876500007', p_hash7))

        conn.commit()


_SQLITE_INSTANCE = None


def get_sqlite_db(db_path=None):
    """Returns a thread-safe SQLite compatibility connection with auto-initialization."""
    if db_path is None:
        db_path = os.environ.get("SQLITE_DB_PATH", DEFAULT_SQLITE_PATH)

    # In read-only filesystems (like serverless edge sandboxes), fallback to /tmp
    try:
        dirname = os.path.dirname(db_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)
        # Test file creation
        test_file = db_path + ".test"
        with open(test_file, "a") as f:
            pass
        os.remove(test_file)
    except Exception:
        db_path = "/tmp/sewasetu.sqlite"

    conn = SQLiteCompatConnection(db_path)
    init_sqlite_schema(conn)
    return conn
