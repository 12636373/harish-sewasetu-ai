#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Root entrypoint for Sewa Setu Portal & MCP Servers.
Supports Wasmer Edge (WASI/WASIX), Gunicorn, and standard WSGI servers.
"""
import os
import sys

# Ensure 'app' directory and repo root are in python search path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import Flask application from app/app.py
from app import app

# Standard WSGI callable for Wasmer Edge and WSGI servers
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Sewa Setu Portal & Dual MCP Servers on http://{host}:{port}...")
    app.run(host=host, port=port, debug=False)
