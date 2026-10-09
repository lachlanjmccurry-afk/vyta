"""
VYTA - Test data: a healthy and a stressed business
----------------------------------------------------
Run with:   py make_test_data.py

Creates two made-up businesses in Xero's own file format, so the whole pipeline can be
tested end to end:
  data_healthy\\raw\\    - growing, profitable, pays the ATO on time, customers pay promptly
  data_stressed\\raw\\   - falling revenue and margin, ATO debt building, slow debtors,
                          stretched creditors, overdraft growing

Then for each folder:
  py build_model.py data_healthy     then   py score.py data_healthy
  py build_model.py data_stressed    then   py score.py data_stressed

Everything here is synthetic and labelled TEST. Nothing is read from or sent to Xero, and the
real  data\\  folder is never touched. 24 months are generated so the 12-month trend
indicators (V3, V6) can be tested too.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from build_model import month_ends

PERIOD_END = date(2026, 9, 30)
PULLED_ON = date(2026, 10, 4)
MONTHS = 24


# ---------- the two businesses ----------
# Each returns one dict per month, oldest first. Months run Oct 2024 -> Sep 2026, so
# i % 3 is the month's position in its BAS quarter (0 = first month, 2 = last).

def healthy():
    rows = []
    for i in range(MONTHS):
        sales = 80000 * 1.008 ** i                     # steady growth
        cogs = sales * (0.56 - 0.0008 * i)             # margin edging up
        gst_month = 0.1 * (sales - cogs) * 0.9
        rows.append({
            "sales": sales, "cogs": cogs,
            "wages": 18000 + 100 * i, "rent": 4000, "general": 3000 + 0.02 * sales,
            "depreciation": 1000, "interest": 350 - 5 * i,
            "bank": 15000 + 300 * i, "savings": 40000 + 2500 * i,
            "debtors": sales * 38 / 30.4,              # customers pay in ~38 days
            "plant": 90000, "accum_dep": 20000 + 1000 * i,
            "creditors": (cogs + 3000) * 30 / 30.4,    # suppliers paid in ~30 days
            "gst": gst_month * (i % 3 + 1),            # BAS paid every quarter
            "payg": 3500,                              # PAYG paid monthly
            "loan": 50000 - 1000 * i,                  # equipment loan being repaid
        })
    aged = {
        "ACCREC": [(-15, 0.75), (10, 0.18), (40, 0.07)],
        "ACCPAY": [(-10, 0.90), (5, 0.10)],
    }
    return rows, aged


def stressed():
    rows, gst, payg = [], 0.0, 0.0
    for i in range(MONTHS):
        t = i / (MONTHS - 1)
        sales = 95000 - 40000 * t ** 1.3               # revenue sliding 95k -> 55k a month
        margin = 0.40 - 0.08 * t                       # margin eroding 40% -> 32%
        cogs = sales * (1 - margin)
        gst_month = 0.1 * (sales - cogs) * 0.9
        if i < 14:                                     # BAS paid on time for the first 14 months...
            gst, payg = gst_month * (i % 3 + 1), 4000
        else:                                          # ...then nothing paid to the ATO
            gst, payg = gst + gst_month, payg + 4000
        rows.append({
            "sales": sales, "cogs": cogs,
            "wages": 20000, "rent": 5000, "general": 4000,
            "depreciation": 800, "interest": 600 + 40 * i,
            "bank": 20000 - 50000 * t ** 1.5,          # into overdraft
            "savings": 10000 * (1 - t),
            "debtors": sales * (40 + 55 * t ** 2) / 30.4,        # debtor days 40 -> 95
            "plant": 50000, "accum_dep": 10000 + 800 * i,
            "creditors": (cogs + 4000) * (30 + 150 * t ** 2) / 30.4,  # suppliers stretched
            "gst": gst, "payg": payg,
            "loan": 40000,
        })
    aged = {
        "ACCREC": [(-10, 0.35), (20, 0.20), (50, 0.10), (75, 0.05), (120, 0.30)],
        "ACCPAY": [(-10, 0.25), (20, 0.15), (50, 0.10), (80, 0.10), (130, 0.40)],
    }
    return rows, aged


# ---------- Xero-format writers ----------

def r2(x):
    return round(x, 2)


def row(label, values, summary=False):
    return {"RowType": "SummaryRow" if summary else "Row",
            "Cells": [{"Value": label}] + [{"Value": f"{v:.2f}"} for v in values]}


def section(title, rows):
    return {"RowType": "Section", "Title": title, "Rows": rows}


def report(name, header_ends, sections):
    header = {"RowType": "Header",
              "Cells": [{"Value": ""}] + [{"Value": f"{e:%d %b %Y}"} for e in header_ends]}
    return {"Reports": [{"ReportName": name, "Rows": [header] + sections}]}


def col(months, key):
    """Newest first, to match Xero's column order."""
    return [r2(m[key]) for m in reversed(months)]


def add(*cols):
    return [r2(sum(vals)) for vals in zip(*cols)]


def neg(c):
    return [-v for v in c]


def profit_and_loss(months, ends):
    sales, cogs = col(months, "sales"), col(months, "cogs")
    opex_lines = [("Wages and Salaries", col(months, "wages")), ("Rent", col(months, "rent")),
                  ("General Expenses", col(months, "general")), ("Depreciation", col(months, "depreciation")),
                  ("Interest Expense", col(months, "interest"))]
    opex = add(*[c for _, c in opex_lines])
    gross = add(sales, neg(cogs))
    return report("Profit and Loss", ends, [
        section(" Income", [row("Sales", sales), row("Total Income", sales, True)]),
        section(" Less Cost of Sales", [row("Purchases", cogs), row("Total Cost of Sales", cogs, True)]),
        section("", [row("GROSS PROFIT", gross)]),
        section(" Less Operating Expenses",
                [row(n, c) for n, c in opex_lines] + [row("Total Operating Expenses", opex, True)]),
        section("", [row("NET PROFIT", add(gross, neg(opex)))]),
    ])


def balance_sheet(months, ends):
    bank, savings = col(months, "bank"), col(months, "savings")
    total_bank = add(bank, savings)
    debtors = col(months, "debtors")
    plant, accum = col(months, "plant"), neg(col(months, "accum_dep"))
    fixed = add(plant, accum)
    total_assets = add(total_bank, debtors, fixed)
    creditors, gst, payg = col(months, "creditors"), col(months, "gst"), col(months, "payg")
    current_liab = add(creditors, gst, payg)
    loan = col(months, "loan")
    total_liab = add(current_liab, loan)
    net_assets = add(total_assets, neg(total_liab))
    return report("Balance Sheet", ends, [
        section("Assets", []),
        section("Bank", [row("Business Bank Account", bank), row("Business Savings Account", savings),
                         row("Total Bank", total_bank, True)]),
        section("Current Assets", [row("Accounts Receivable", debtors),
                                   row("Total Current Assets", debtors, True)]),
        section("Fixed Assets", [row("Plant and Equipment", plant),
                                 row("Less Accumulated Depreciation on Plant and Equipment", accum),
                                 row("Total Fixed Assets", fixed, True)]),
        section("", [row("Total Assets", total_assets, True)]),
        section("Liabilities", []),
        section("Current Liabilities", [row("Accounts Payable", creditors), row("GST", gst),
                                        row("PAYG Withholdings Payable", payg),
                                        row("Total Current Liabilities", current_liab, True)]),
        section("Non-Current Liabilities", [row("Bank Loan", loan),
                                            row("Total Non-Current Liabilities", loan, True)]),
        section("", [row("Total Liabilities", total_liab, True)]),
        section("", [row("Net Assets", net_assets)]),
        section("Equity", [row("Retained Earnings", net_assets), row("Total Equity", net_assets, True)]),
    ])


def invoices(total_due, buckets, kind, prefix):
    """Split the month-end balance into unpaid invoices aged by days past due (as at PULLED_ON)."""
    out, n = [], 0
    for days_overdue, share in buckets:
        amount = total_due * share
        for part in (0.6, 0.4):                        # two invoices per bucket
            n += 1
            due = PULLED_ON - timedelta(days=days_overdue)
            ms = int(datetime(due.year, due.month, due.day, tzinfo=timezone.utc).timestamp() * 1000)
            out.append({
                "Type": kind, "Status": "AUTHORISED", "InvoiceNumber": f"{prefix}-{n:03d}",
                "Contact": {"Name": f"{'Customer' if kind == 'ACCREC' else 'Supplier'} {chr(64 + n)}"},
                "Total": r2(amount * part), "AmountDue": r2(amount * part),
                "DueDate": f"/Date({ms}+0000)/", "DueDateString": f"{due.isoformat()}T00:00:00",
            })
    return out


def write_business(folder, org_name, months, aged):
    if folder.name == "data":
        raise SystemExit("[STOPPED] Refusing to overwrite the real data folder.")
    raw = folder / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ends = month_ends(PERIOD_END, MONTHS)              # newest first
    latest = months[-1]
    files = {
        "profit_and_loss": profit_and_loss(months, ends),
        "balance_sheet": balance_sheet(months, ends),
        "invoices": (invoices(r2(latest["debtors"]), aged["ACCREC"], "ACCREC", "INV")
                     + invoices(r2(latest["creditors"]), aged["ACCPAY"], "ACCPAY", "BILL")),
        "accounts": {"Accounts": [
            {"Name": "Business Bank Account", "Type": "BANK"},
            {"Name": "Business Savings Account", "Type": "BANK"},
            {"Name": "Accounts Receivable", "Type": "CURRENT"},
            {"Name": "Accounts Payable", "Type": "CURRLIAB"},
            {"Name": "GST", "Type": "CURRLIAB"},
            {"Name": "PAYG Withholdings Payable", "Type": "CURRLIAB"},
            {"Name": "Bank Loan", "Type": "TERMLIAB"},
        ]},
        "organisation": {"Organisations": [{"Name": org_name}]},
    }
    for name, data in files.items():
        (raw / f"{name}.json").write_text(json.dumps(data, indent=2))
    (raw / "summary.txt").write_text("\n".join([
        f"Organisation: {org_name}",
        f"Pulled on:    {PULLED_ON.isoformat()}",
        f"Period:       {MONTHS} months ending {PERIOD_END.isoformat()}",
        "",
        "SYNTHETIC TEST DATA - made by make_test_data.py, not from Xero",
    ]))
    print(f"  {org_name:<34} -> {raw.resolve()}")


def main():
    print("Creating synthetic test businesses...")
    write_business(Path("data_healthy"), "TEST - Healthy Co (synthetic)", *healthy())
    write_business(Path("data_stressed"), "TEST - Stressed Co (synthetic)", *stressed())
    print("\n[DONE] Next:  py build_model.py data_healthy   and   py build_model.py data_stressed")


if __name__ == "__main__":
    main()
