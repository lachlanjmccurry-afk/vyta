"""
VYTA - Step 1: Connect to Xero
--------------------------------
Run with:   py connect_xero.py

What it does:
  1. Opens your browser at the Xero login page
  2. You log in, choose "Demo Company (AU)" and click Allow access
  3. Xero sends you back to this script, which swaps the login code for tokens
  4. Saves the tokens + the organisation ID to tokens.json

You only need to run this once. After that, pull_data.py keeps you logged in
automatically. If pull_data.py ever says your login has expired (after ~60 days
of not using it), just run this again.

tokens.json is effectively a password - don't share or upload it.
"""

import base64
import json
import os
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("XERO_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("XERO_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("XERO_REDIRECT_URI", "http://localhost:8080/callback").strip()

# Read-only scopes only - Vyta never writes back to Xero
SCOPES = " ".join([
    "offline_access",
    "accounting.settings.read",
    "accounting.contacts.read",
    "accounting.invoices.read",
    "accounting.payments.read",
    "accounting.banktransactions.read",
    "accounting.manualjournals.read",
    "accounting.reports.aged.read",
    "accounting.reports.balancesheet.read",
    "accounting.reports.profitandloss.read",
    "accounting.reports.trialbalance.read",
    "accounting.reports.banksummary.read",
    "accounting.reports.executivesummary.read",
])

AUTH_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"
TOKEN_FILE = "tokens.json"
WAIT_SECONDS = 300  # give you 5 minutes to log in

callback = {}


class CallbackHandler(BaseHTTPRequestHandler):
    """Tiny local web page that catches Xero's redirect after you log in."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != urlparse(REDIRECT_URI).path:
            self.send_response(404)
            self.end_headers()
            return
        params = parse_qs(parsed.query)
        callback["code"] = params.get("code", [None])[0]
        callback["state"] = params.get("state", [None])[0]
        callback["error"] = params.get("error", [None])[0]

        if callback["code"]:
            msg = "Connected to Xero. You can close this tab and go back to the terminal."
        else:
            msg = f"Something went wrong: {callback['error']}. Check the terminal."
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

    def log_message(self, *args):
        pass  # keep the terminal tidy


def stop(message):
    print(f"\n[STOPPED] {message}")
    sys.exit(1)


def main():
    # 1. Check the .env file is filled in
    if not CLIENT_ID or not CLIENT_SECRET or "paste" in CLIENT_SECRET.lower():
        stop("Your .env file is missing the Client ID or secret. Open it with: notepad .env")

    # 2. Start the little local server that catches Xero's redirect
    port = urlparse(REDIRECT_URI).port or 80
    try:
        server = HTTPServer(("localhost", port), CallbackHandler)
    except OSError:
        stop(f"Port {port} is already in use. Close other terminals running this script and try again.")
    server.timeout = 5

    # 3. Open the Xero login page
    state = secrets.token_urlsafe(16)
    login_url = AUTH_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    })
    print("Opening Xero in your browser...")
    print("Log in, choose 'Demo Company (AU)', then click 'Allow access'.")
    print("\nIf the browser doesn't open, copy this link into it:\n")
    print(login_url + "\n")
    webbrowser.open(login_url)

    # 4. Wait for you to finish logging in
    deadline = time.time() + WAIT_SECONDS
    while not callback and time.time() < deadline:
        server.handle_request()
    server.server_close()

    if not callback:
        stop("Timed out waiting for the Xero login. Run the script again.")
    if callback.get("error"):
        stop(f"Xero returned an error: {callback['error']}. "
             "If it mentions scopes or redirect URI, screenshot this and send it through.")
    if callback.get("state") != state:
        stop("Security check failed (state mismatch). Run the script again.")

    # 5. Swap the one-time code for real tokens
    print("Login received. Getting tokens...")
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code",
              "code": callback["code"],
              "redirect_uri": REDIRECT_URI},
        timeout=30,
    )
    if not resp.ok:
        stop(f"Token swap failed ({resp.status_code}): {resp.text[:300]}\n"
             "Most common cause: the secret in .env doesn't match the one in the Xero portal.")
    tokens = resp.json()

    # 6. Find out which organisation(s) you connected
    resp = requests.get(CONNECTIONS_URL,
                        headers={"Authorization": f"Bearer {tokens['access_token']}"},
                        timeout=30)
    if not resp.ok:
        stop(f"Couldn't read connected organisations ({resp.status_code}): {resp.text[:300]}")
    orgs = resp.json()
    if not orgs:
        stop("No organisation was connected. Run again and make sure you tick Demo Company (AU).")

    print("\nConnected organisations:")
    for org in orgs:
        print(f"  - {org['tenantName']}")
    chosen = next((o for o in orgs if "demo" in o["tenantName"].lower()), orgs[0])

    # 7. Save everything pull_data.py needs
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": time.time() + tokens.get("expires_in", 1800),
            "tenant_id": chosen["tenantId"],
            "tenant_name": chosen["tenantName"],
        }, f, indent=2)

    print(f"\n[DONE] Connected to '{chosen['tenantName']}'. Tokens saved to {TOKEN_FILE}.")
    print("Next step:  py pull_data.py")


if __name__ == "__main__":
    main()
