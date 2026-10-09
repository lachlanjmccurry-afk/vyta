"""
VYTA - Step 2: Pull data out of Xero
-------------------------------------
Run with:   py pull_data.py            (pulls the 12 months ending last month)
       or:  py pull_data.py 2026-08    (pulls the 12 months ending Aug 2026)

Saves raw Xero data as JSON files into  data\\raw\\  plus a summary.txt.
Read-only: nothing is ever changed in Xero.
"""

import base64
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("XERO_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("XERO_CLIENT_SECRET", "").strip()

TOKEN_URL = "https://identity.xero.com/connect/token"
API = "https://api.xero.com/api.xro/2.0"
TOKEN_FILE = Path("tokens.json")
OUT_DIR = Path("data") / "raw"
PAUSE = 1.1  # Xero allows 60 calls/minute - this keeps us safely under


# ---------- login handling ----------

def stop(message):
    print(f"\n[STOPPED] {message}")
    sys.exit(1)


def load_tokens():
    if not TOKEN_FILE.exists():
        stop("No tokens.json found. Run  py connect_xero.py  first.")
    return json.loads(TOKEN_FILE.read_text())


def save_tokens(tokens):
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def refresh(tokens):
    """Get a fresh access token. Xero gives a NEW refresh token each time, so save it straight away."""
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        timeout=30,
    )
    if not resp.ok:
        stop(f"Couldn't refresh your login ({resp.status_code}). Run  py connect_xero.py  again.")
    new = resp.json()
    tokens["access_token"] = new["access_token"]
    tokens["refresh_token"] = new["refresh_token"]
    tokens["expires_at"] = time.time() + new.get("expires_in", 1800)
    save_tokens(tokens)


def get(tokens, path, params=None, _retry=True):
    """Call one Xero endpoint. Returns the JSON, or None if that endpoint failed."""
    if time.time() > tokens["expires_at"] - 60:
        refresh(tokens)
    resp = requests.get(
        f"{API}/{path}",
        headers={"Authorization": f"Bearer {tokens['access_token']}",
                 "Xero-tenant-id": tokens["tenant_id"],
                 "Accept": "application/json"},
        params=params,
        timeout=60,
    )
    time.sleep(PAUSE)

    if resp.status_code == 401 and _retry:
        refresh(tokens)
        return get(tokens, path, params, _retry=False)
    if resp.status_code == 429 and _retry:
        wait = int(resp.headers.get("Retry-After", 60))
        print(f"    Xero says slow down - waiting {wait}s...")
        time.sleep(wait)
        return get(tokens, path, params, _retry=False)
    if not resp.ok:
        print(f"    [!] {path} failed ({resp.status_code}): {resp.text[:200]}")
        return None
    return resp.json()


def get_all_pages(tokens, path, key, params=None):
    """For lists (invoices, contacts...) Xero returns 100 per page - keep going until done."""
    items, page = [], 1
    while True:
        data = get(tokens, path, {**(params or {}), "page": page})
        if data is None:
            return None if page == 1 else items
        batch = data.get(key, [])
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


# ---------- dates ----------

def month_end(year, month):
    first_of_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_of_next - timedelta(days=1)


def pick_month():
    if len(sys.argv) > 1:
        try:
            y, m = map(int, sys.argv[1].split("-"))
            return y, m
        except ValueError:
            stop("Month should look like 2026-08")
    last_month = date.today().replace(day=1) - timedelta(days=1)
    return last_month.year, last_month.month


# ---------- main ----------

def save(name, data):
    (OUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2))


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        stop("Your .env file is missing the Client ID or secret.")
    tokens = load_tokens()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    y, m = pick_month()
    end = month_end(y, m)
    start = date(y, m, 1)
    print(f"Organisation: {tokens['tenant_name']}")
    print(f"Pulling 12 months ending {end:%B %Y}\n")

    summary = []

    # Reports - 12 monthly columns (latest month + 11 earlier)
    reports = [
        ("profit_and_loss", "Reports/ProfitAndLoss",
         {"fromDate": start.isoformat(), "toDate": end.isoformat(),
          "periods": 11, "timeframe": "MONTH"}),
        ("balance_sheet", "Reports/BalanceSheet",
         {"date": end.isoformat(), "periods": 11, "timeframe": "MONTH"}),
        ("trial_balance", "Reports/TrialBalance", {"date": end.isoformat()}),
    ]
    for name, path, params in reports:
        print(f"  Pulling {name}...")
        data = get(tokens, path, params)
        if data is not None:
            save(name, data)
            summary.append(f"{name}: saved")
        else:
            summary.append(f"{name}: FAILED")

    # Single lookups
    for name, path in [("organisation", "Organisation"), ("accounts", "Accounts")]:
        print(f"  Pulling {name}...")
        data = get(tokens, path)
        if data is not None:
            save(name, data)
            summary.append(f"{name}: saved")
        else:
            summary.append(f"{name}: FAILED")

    # Lists (paged)
    lists = [
        ("invoices", "Invoices", "Invoices"),
        ("contacts", "Contacts", "Contacts"),
        ("payments", "Payments", "Payments"),
        ("bank_transactions", "BankTransactions", "BankTransactions"),
        ("manual_journals", "ManualJournals", "ManualJournals"),
    ]
    for name, path, key in lists:
        print(f"  Pulling {name}...")
        items = get_all_pages(tokens, path, key)
        if items is not None:
            save(name, items)
            summary.append(f"{name}: {len(items)} records")
        else:
            summary.append(f"{name}: FAILED")

    # Summary file
    lines = [
        f"Organisation: {tokens['tenant_name']}",
        f"Pulled on:    {date.today().isoformat()}",
        f"Period:       12 months ending {end.isoformat()}",
        "",
        *summary,
    ]
    (OUT_DIR / "summary.txt").write_text("\n".join(lines))

    print("\n" + "\n".join(lines))
    print(f"\n[DONE] Files saved in {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
