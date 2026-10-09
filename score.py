"""
VYTA - Step 4: Score the business
----------------------------------
Run with:   py score.py                  (scores the data in  data\\ )
       or:  py score.py data_stressed    (scores a different data folder)

Reads:
  <folder>\\model\\monthly_summary.csv   - made by build_model.py
  <folder>\\raw\\*.json + summary.txt    - made by pull_data.py
  scorecard.json                         - thresholds, weights, bands (edit this, not the code)

Creates  <folder>\\model\\vyta_score.xlsx  with:
  - a Distress score (0-100, higher = worse) and a Viability score (0-100, higher = better)
  - their bands, any override applied, and the indicative pathway from the outcome matrix
  - every indicator rated Green / Amber / Red, or "Not assessed" with the reason

Read-only: never touches Xero. Indicative only - not an insolvency determination.
"""

import csv
import json
import re
import sys
import textwrap
from datetime import date
from pathlib import Path

from build_model import (BOLD, FONT, HEAD_FILL, HEAD_FONT, flatten, month_ends, num, parse_xero_date,
                         set_widths, stop, style_header)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

CONFIG = Path("scorecard.json")
WORDING = Path("wording.json")
NOT_ASSESSED = "Not assessed"
OWNER_QUESTION = "Not assessed - owner question"
FILLS = {
    "Red": PatternFill("solid", start_color="F4B6B6"),
    "Amber": PatternFill("solid", start_color="FFE699"),
    "Green": PatternFill("solid", start_color="C6E0B4"),
    NOT_ASSESSED: PatternFill("solid", start_color="E7E6E6"),
    OWNER_QUESTION: PatternFill("solid", start_color="E7E6E6"),
}
WRAP = Alignment(wrap_text=True, vertical="top")

# Lines that count as bank debt (D5, D6) - owner/director loans are not bank debt
LOAN_PATTERN = re.compile(r"loan|overdraft|facility|hire purchase|chattel|equipment finance|"
                          r"finance lease|line of credit", re.I)
NOT_BANK_PATTERN = re.compile(r"owner|director|shareholder|related|drawings|funds introduced|beneficiar", re.I)


# ---------- loading ----------

def load_config():
    if not CONFIG.exists():
        stop("Can't find scorecard.json in this folder.")
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        stop(f"scorecard.json has a typo on line {e.lineno} (often a missing comma or quote). "
             "Fix it and run again.")
    for ind in cfg["indicators"]:
        missing = [k for k in ("id", "score", "direction", "amber", "red", "weight") if k not in ind]
        if missing:
            stop(f"Indicator {ind.get('id', '?')} in scorecard.json is missing: {', '.join(missing)}")
        if ind["direction"] not in ("higher_is_worse", "lower_is_worse"):
            stop(f"Indicator {ind['id']}: direction must be higher_is_worse or lower_is_worse")
    for kind in ("distress", "viability"):
        total = sum(i["weight"] for i in cfg["indicators"] if i["score"] == kind and i.get("enabled", True))
        if abs(total - 100) > 0.01:
            print(f"[NOTE] {kind.title()} weights add up to {total:g}, not 100. "
                  "Scores are still a fair weighted average.")
    return cfg


def load_data(base, cfg):
    raw, model = base / "raw", base / "model"

    csv_path = model / "monthly_summary.csv"
    if not csv_path.exists():
        stop(f"Can't find {csv_path}. Run  py build_model.py  first.")
    months = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            m = {k: num(v) for k, v in row.items() if k not in ("month", "has_activity")}
            m["month"] = date.fromisoformat(row["month"])
            m["has_activity"] = row["has_activity"] == "yes"
            months.append(m)
    if not months:
        stop(f"{csv_path} is empty. Run  py build_model.py  again.")
    months.sort(key=lambda m: m["month"])

    def load(name):
        path = raw / f"{name}.json"
        if not path.exists():
            stop(f"Can't find {path}. Run  py pull_data.py  first.")
        return json.loads(path.read_text())

    summary_path = raw / "summary.txt"
    if not summary_path.exists():
        stop(f"Can't find {summary_path}. Run  py pull_data.py  first.")
    pulled = re.search(r"Pulled on:\s*(\d{4}-\d{2}-\d{2})", summary_path.read_text())

    ends = month_ends(months[-1]["month"], len(months))
    org = (load("organisation").get("Organisations") or [{}])[0].get("Name", "Unknown")
    v5 = next((i for i in cfg["indicators"] if i["id"] == "V5"), {})
    return {
        "base": base,
        "org": org,
        "months": months,
        "pl": flatten(load("profit_and_loss"), ends),
        "bs": flatten(load("balance_sheet"), ends),
        "invoices": load("invoices"),
        "account_types": {a["Name"]: a["Type"] for a in load("accounts").get("Accounts", [])},
        # Unpaid invoice balances are a snapshot from the day the data was pulled
        "as_at": date.fromisoformat(pulled.group(1)) if pulled else date.today(),
        "interest_pattern": v5.get("interest_line_pattern", "interest"),
        "depreciation_pattern": v5.get("depreciation_line_pattern", "depreciation|amortisation|amortization"),
    }


# ---------- helpers ----------

def money(x):
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def mon(m):
    return m["month"].strftime("%b %Y")


def fmt(value, unit):
    if value is None:
        return ""
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit == "percentage_points":
        return f"{value * 100:+.1f} pts"
    if unit == "months":
        return f"{value:.1f} months"
    if unit == "days":
        return f"{value:.0f} days"
    if unit == "count":
        return f"{value:.0f}"
    return f"{value:.2f}"


def value(v, note="", case=None, **facts):
    """A calculated result. `facts` are the working figures the wording.json sentences can quote;
    `case` picks a special sentence if one exists (e.g. case="negative" -> "red_negative")."""
    return {"value": v, "note": note, "case": case, "facts": facts}


def forced(rating, display, note="", case=None, **facts):
    """Edge case where the formula can't run (e.g. divide by zero) - rating set by a rule in scorecard.json.
    `case` picks a special sentence in wording.json, e.g. case="overdrawn" -> "red_overdrawn"."""
    return {"rating": rating, "display": display, "note": note, "case": case, "facts": facts}


def not_assessed(reason, owner=False):
    return {"rating": OWNER_QUESTION if owner else NOT_ASSESSED, "display": "", "note": reason}


def last12(d, key):
    return sum(m[key] for m in d["months"][-12:])


def active_months(d):
    return [m for m in d["months"][-12:] if m["has_activity"]]


def pl_lines(d, pattern):
    """Sum of P&L expense lines matching a pattern over the last 12 months (income sections excluded)."""
    period = {m["month"] for m in d["months"][-12:]}
    return sum(r["value"] for r in d["pl"]
               if r["month"] in period and not r["is_total"]
               and not re.search(r"income", r["section"], re.I)
               and re.search(pattern, r["line"], re.I))


def bank_debt(d, month):
    """(overdraft, loans) at a month-end. Overdraft = bank accounts below zero."""
    overdraft = loans = 0.0
    for r in d["bs"]:
        if r["month"] != month or r["is_total"]:
            continue
        if re.search(r"^bank$", r["section"], re.I) and r["value"] < 0:
            overdraft += -r["value"]
        elif (re.search(r"liabilit", r["section"], re.I) and not NOT_BANK_PATTERN.search(r["line"])
              and (d["account_types"].get(r["line"]) == "TERMLIAB" or LOAN_PATTERN.search(r["line"]))):
            loans += r["value"]
    return overdraft, loans


def unpaid_invoices(d, kind, days=90):
    """(total unpaid, unpaid more than `days` past due) for ACCREC (sales) or ACCPAY (bills)."""
    total = over = 0.0
    for inv in d["invoices"]:
        amount = num(inv.get("AmountDue"))
        if inv.get("Type") != kind or inv.get("Status") != "AUTHORISED" or amount <= 0:
            continue
        total += amount
        due = parse_xero_date(inv, "DueDate")
        if due and (d["as_at"] - due).days > days:
            over += amount
    return total, over


def need_history(d, n):
    if len(d["months"]) < n:
        return not_assessed(f"Needs {n} months of history (have {len(d['months'])}). "
                            "pull_data.py currently pulls 12 months.")
    return None


# ---------- distress indicators ----------

def d1_current_ratio(d, ind):
    m = d["months"][-1]
    if m["current_liabilities"] <= 0:
        return forced("Green", "No current liabilities", case="no_liabilities")
    return value(m["current_assets"] / m["current_liabilities"],
                 f"Current assets {money(m['current_assets'])} / current liabilities "
                 f"{money(m['current_liabilities'])} at {mon(m)}",
                 current_assets=money(m["current_assets"]), current_liabilities=money(m["current_liabilities"]),
                 month=mon(m))


def d2_quick_ratio(d, ind):
    m = d["months"][-1]
    if m["current_liabilities"] <= 0:
        return forced("Green", "No current liabilities", case="no_liabilities")
    return value((m["cash"] + m["debtors"]) / m["current_liabilities"],
                 f"(Cash {money(m['cash'])} + debtors {money(m['debtors'])}) / current liabilities "
                 f"{money(m['current_liabilities'])}",
                 cash=money(m["cash"]), debtors=money(m["debtors"]),
                 cash_and_debtors=money(m["cash"] + m["debtors"]), current_liabilities=money(m["current_liabilities"]))


def d3_cash_runway(d, ind):
    lb = ind.get("lookback_months", 3)
    ms = d["months"]
    if len(ms) < lb + 1:
        return not_assessed(f"Needs {lb + 1} month-end cash balances")
    cash, before = ms[-1]["cash"], ms[-1 - lb]["cash"]
    outflow = (before - cash) / lb
    trend = f"falling {money(outflow)}/month" if outflow > 0 else f"rising {money(-outflow)}/month"
    note = (f"Cash {money(cash)} at {mon(ms[-1])}, up from {money(before)} at {mon(ms[-1 - lb])}" if outflow < 0
            else f"Cash {money(cash)} at {mon(ms[-1])}, down from {money(before)} at {mon(ms[-1 - lb])}")
    note += f" (on average {trend})"
    facts = dict(cash=money(cash), cash_before=money(before), month=mon(ms[-1]), month_before=mon(ms[-1 - lb]),
                 monthly_outflow=money(outflow))
    if cash <= 0:
        return forced(ind.get("if_cash_zero_or_negative", "Red"), "No cash / overdrawn", note, case="overdrawn",
                      **facts)
    if outflow <= 0:
        return forced(ind.get("if_cash_not_falling", "Green"), "Cash not falling", note, case="not_falling",
                      **facts)
    return value(cash / outflow, note, **facts)


def d4_ato_rising(d, ind):
    ms = d["months"]
    min_rise = ind.get("min_increase_dollars", 0) or 0
    count = 0
    for i in range(len(ms) - 1, 0, -1):
        if ms[i]["ato_liabilities"] - ms[i - 1]["ato_liabilities"] > min_rise:
            count += 1
        else:
            break
    trail = ", ".join(f"{mon(m)} {money(m['ato_liabilities'])}" for m in ms[-4:])
    start = ms[-1 - count]["ato_liabilities"]
    now = ms[-1]["ato_liabilities"]
    return value(count, f"ATO balance at month-end: {trail}",
                 ato_start=money(start), ato_now=money(now), ato_increase=money(now - start), month=mon(ms[-1]))


def d5_bank_debt_growth(d, ind):
    lb = ind.get("lookback_months", 6)
    ms = d["months"]
    if len(ms) < lb + 1:
        return not_assessed(f"Needs {lb + 1} months of balances")
    now, then = sum(bank_debt(d, ms[-1]["month"])), sum(bank_debt(d, ms[-1 - lb]["month"]))
    note = f"Loans + overdraft {money(then)} at {mon(ms[-1 - lb])} -> {money(now)} at {mon(ms[-1])}"
    facts = dict(debt_before=money(then), debt_now=money(now), month_before=mon(ms[-1 - lb]), month=mon(ms[-1]))
    if then <= 0:
        if now > 0:
            return forced(ind.get("if_no_debt_before_but_debt_now", "Red"), "New bank debt", note, case="new_debt",
                          **facts)
        return forced("Green", "No bank debt", note, case="no_debt", **facts)
    return value((now - then) / then, note, **facts)


def d6_facility_utilisation(d, ind):
    limit = ind.get("approved_limit_dollars")
    if not limit:
        return not_assessed("Needs the approved overdraft/facility limit - add it to scorecard.json "
                            "(approved_limit_dollars)", owner=True)
    overdraft, _ = bank_debt(d, d["months"][-1]["month"])
    return value(overdraft / limit, f"Overdraft drawn {money(overdraft)} / approved limit {money(limit)}",
                 overdraft=money(overdraft), limit=money(limit))


def d7_creditor_days(d, ind):
    active = active_months(d)
    if not active:
        return not_assessed("No trading activity in the last 12 months")
    costs = sum(m["cost_of_sales"] + m["operating_expenses"] for m in active) * 12 / len(active)
    if costs <= 0:
        return not_assessed("No expenses recorded")
    creditors = d["months"][-1]["creditors"]
    return value(creditors / costs * 365,
                 f"Trade creditors {money(creditors)} / yearly costs {money(costs)} "
                 f"(annualised from {len(active)} month(s) of activity) x 365",
                 creditors=money(creditors), yearly_costs=money(costs), active_months=len(active))


def overdue_share(d, kind, label):
    total, over = unpaid_invoices(d, kind)
    if total <= 0:
        return forced("Green", f"No unpaid {label}", case="nothing_unpaid")
    return value(over / total, f"{money(over)} of {money(total)} unpaid {label} is >90 days past due "
                               f"(as at {d['as_at']:%d %b %Y})",
                 case="none_overdue" if over == 0 else None, overdue_90=money(over), total_unpaid=money(total), as_at=f"{d['as_at']:%d %b %Y}")


def d8_creditors_overdue(d, ind):
    return overdue_share(d, "ACCPAY", "bills")


def d9_debtor_days_trend(d, ind):
    lb = ind.get("lookback_months", 3)
    ms = d["months"]
    if len(ms) < lb + 1:
        return not_assessed(f"Needs {lb + 1} months of balances")
    now, then = ms[-1], ms[-1 - lb]
    if now["revenue"] <= 0 or then["revenue"] <= 0:
        return not_assessed(f"Needs revenue in both {mon(then)} and {mon(now)} to work out debtor days")
    dd_now = now["debtors"] / (now["revenue"] * 12) * 365
    dd_then = then["debtors"] / (then["revenue"] * 12) * 365
    return value(dd_now - dd_then, f"Debtor days {dd_then:.0f} at {mon(then)} -> {dd_now:.0f} at {mon(now)}",
                 days_before=f"{dd_then:.0f} days", days_now=f"{dd_now:.0f} days",
                 month_before=mon(then), month=mon(now))


def d10_debtors_overdue(d, ind):
    return overdue_share(d, "ACCREC", "sales invoices")


def d11_sales_up_cash_down(d, ind):
    ms = d["months"]
    rolling = lambda i: sum(m["revenue"] for m in ms[i - 2:i + 1])
    count = 0
    for i in range(len(ms) - 1, 2, -1):
        if rolling(i) > rolling(i - 1) and ms[i]["cash"] < ms[i - 1]["cash"]:
            count += 1
        else:
            break
    return value(count, "Months in a row (to the latest month) where 3-month revenue rose while cash fell",
                 cash=money(ms[-1]["cash"]), month=mon(ms[-1]))


def d12_operating_cash_flow(d, ind):
    ms = d["months"][-12:]
    first, last = ms[0], ms[-1]
    profit = last12(d, "net_profit")
    dep = pl_lines(d, d["depreciation_pattern"])
    working_capital = (-(last["debtors"] - first["debtors"]) + (last["creditors"] - first["creditors"])
                       + (last["ato_liabilities"] - first["ato_liabilities"]))
    ocf = profit + dep + working_capital
    if last["current_liabilities"] <= 0:
        return forced("Green", "No current liabilities", case="no_liabilities")
    return value(ocf / last["current_liabilities"],
                 f"Estimated operating cash flow {money(ocf)} (profit {money(profit)} + depreciation {money(dep)} "
                 f"+ working capital {money(working_capital)}) / current liabilities "
                 f"{money(last['current_liabilities'])}",
                 case="negative" if ocf <= 0 else None, ocf=money(ocf), profit=money(profit), depreciation=money(dep),
                 working_capital=money(working_capital), current_liabilities=money(last["current_liabilities"]))


def d13_debt_to_assets(d, ind):
    m = d["months"][-1]
    facts = dict(total_liabilities=money(m["total_liabilities"]), total_assets=money(m["total_assets"]))
    if m["total_assets"] <= 0:
        return forced(ind.get("if_assets_zero_or_negative", "Red"), "No assets",
                      f"Total liabilities {money(m['total_liabilities'])}", case="no_assets", **facts)
    return value(m["total_liabilities"] / m["total_assets"],
                 f"Total liabilities {money(m['total_liabilities'])} / total assets {money(m['total_assets'])}",
                 **facts)


# ---------- viability indicators ----------

def v1_equity_ratio(d, ind):
    m = d["months"][-1]
    facts = dict(net_assets=money(m["net_assets"]), total_assets=money(m["total_assets"]))
    if m["total_assets"] <= 0:
        return forced("Red", "No assets", f"Net assets {money(m['net_assets'])}", case="no_assets", **facts)
    return value(m["net_assets"] / m["total_assets"],
                 f"Net assets {money(m['net_assets'])} / total assets {money(m['total_assets'])}", **facts)


def v2_gross_margin(d, ind):
    revenue = last12(d, "revenue")
    if revenue <= 0:
        return not_assessed("No revenue in the last 12 months")
    gp = last12(d, "gross_profit")
    note = f"Gross profit {money(gp)} / revenue {money(revenue)} (last 12 months)"
    if last12(d, "cost_of_sales") == 0:
        note += ". No cost of sales recorded, so gross margin is 100%"
    return value(gp / revenue, note, gross_profit=money(gp), revenue=money(revenue))


def v3_gross_margin_trend(d, ind):
    missing = need_history(d, ind.get("needs_history_months", 24))
    if missing:
        return missing
    now, before = d["months"][-12:], d["months"][-24:-12]
    rev_now, rev_before = sum(m["revenue"] for m in now), sum(m["revenue"] for m in before)
    if rev_now <= 0 or rev_before <= 0:
        return not_assessed("Needs revenue in both 12-month periods")
    gm_now = sum(m["gross_profit"] for m in now) / rev_now
    gm_before = sum(m["gross_profit"] for m in before) / rev_before
    return value(gm_now - gm_before, f"Gross margin {gm_before:.1%} -> {gm_now:.1%}",
                 margin_before=f"{gm_before:.1%}", margin_now=f"{gm_now:.1%}")


def v4_overhead_to_gp(d, ind):
    gp, opex = last12(d, "gross_profit"), last12(d, "operating_expenses")
    note = f"Operating expenses {money(opex)} / gross profit {money(gp)} (last 12 months)"
    facts = dict(opex=money(opex), gross_profit=money(gp))
    if gp <= 0:
        return forced(ind.get("if_gross_profit_zero_or_negative", "Red"), "No gross profit", note,
                      case="no_gross_profit", **facts)
    return value(opex / gp, note, **facts)


def v5_underlying_margin(d, ind):
    revenue = last12(d, "revenue")
    if revenue <= 0:
        return not_assessed("No revenue in the last 12 months")
    profit = last12(d, "net_profit")
    interest = pl_lines(d, d["interest_pattern"])
    dep = pl_lines(d, d["depreciation_pattern"])
    one_off = ind.get("one_off_costs_dollars") or 0
    underlying = profit + interest + dep + one_off
    return value(underlying / revenue,
                 f"(Net profit {money(profit)} + interest {money(interest)} + depreciation {money(dep)} "
                 f"+ one-off costs {money(one_off)}) / revenue {money(revenue)}"
                 + ("" if one_off else ". No one-off costs entered by owner"),
                 underlying_profit=money(underlying), revenue=money(revenue), profit=money(profit),
                 interest=money(interest), depreciation=money(dep), one_off=money(one_off))


def v6_revenue_trend(d, ind):
    missing = need_history(d, ind.get("needs_history_months", 24))
    if missing:
        return missing
    now = sum(m["revenue"] for m in d["months"][-12:])
    before = sum(m["revenue"] for m in d["months"][-24:-12])
    if before <= 0:
        return not_assessed("No revenue in the earlier 12-month period")
    return value((now - before) / before, f"Revenue {money(before)} -> {money(now)}",
                 revenue_before=money(before), revenue_now=money(now))


def v7_pipeline(d, ind):
    return not_assessed("Needs Xero Quotes - not pulled yet (would need an extra read-only Xero permission)")


def v8_long_term_cover(d, ind):
    m = d["months"][-1]
    nca = m["total_assets"] - m["current_assets"]
    ncl = m["total_liabilities"] - m["current_liabilities"]
    note = f"Non-current assets {money(nca)} / non-current liabilities {money(ncl)}"
    facts = dict(nca=money(nca), ncl=money(ncl))
    if ncl <= 0:
        return forced(ind.get("if_no_long_term_liabilities", "Green"), "No long-term liabilities", note,
                      case="no_long_term_liabilities", **facts)
    return value(nca / ncl, note, **facts)


CALCS = {
    "D1": d1_current_ratio, "D2": d2_quick_ratio, "D3": d3_cash_runway, "D4": d4_ato_rising,
    "D5": d5_bank_debt_growth, "D6": d6_facility_utilisation, "D7": d7_creditor_days,
    "D8": d8_creditors_overdue, "D9": d9_debtor_days_trend, "D10": d10_debtors_overdue,
    "D11": d11_sales_up_cash_down, "D12": d12_operating_cash_flow, "D13": d13_debt_to_assets,
    "V1": v1_equity_ratio, "V2": v2_gross_margin, "V3": v3_gross_margin_trend, "V4": v4_overhead_to_gp,
    "V5": v5_underlying_margin, "V6": v6_revenue_trend, "V7": v7_pipeline, "V8": v8_long_term_cover,
}


# ---------- scoring ----------

def rate(v, ind):
    """A value exactly on a threshold counts as reaching it (with a tiny allowance for rounding noise)."""
    amber, red = ind["amber"], ind["red"]
    reached = lambda t: (v >= t - 1e-9 * max(1, abs(t))) if ind["direction"] == "higher_is_worse" \
        else (v <= t + 1e-9 * max(1, abs(t)))
    return "Red" if reached(red) else "Amber" if reached(amber) else "Green"


def assess(d, cfg):
    results = []
    for ind in cfg["indicators"]:
        if not ind.get("enabled", True):
            continue
        calc = CALCS.get(ind["id"])
        res = calc(d, ind) if calc else not_assessed("No calculation written for this indicator yet")
        unit = ind.get("unit", "ratio")
        if "value" in res:
            res["rating"] = rate(res["value"], ind)
            res["display"] = fmt(res["value"], unit)
        res["ind"] = ind
        res["points"] = cfg["points"][ind["score"]].get(res["rating"])
        results.append(res)
    return results


def total_score(results, kind):
    scored = [r for r in results if r["ind"]["score"] == kind and r["points"] is not None]
    possible = sum(r["ind"]["weight"] for r in results if r["ind"]["score"] == kind)
    weight = sum(r["ind"]["weight"] for r in scored)
    if not weight:
        return None, 0, possible, scored
    return sum(r["ind"]["weight"] * r["points"] for r in scored) / weight, weight, possible, scored


def band_for(score, kind, cfg):
    if score is None:
        return "Not enough data"
    for b in sorted(cfg["bands"][kind], key=lambda b: -b["from"]):
        if score >= b["from"]:
            return b["band"]
    return "Not enough data"


def apply_overrides(cfg, bands):
    answers = {q["id"]: q.get("answer") for q in cfg.get("owner_questions", [])}
    notes = []
    for o in cfg.get("overrides", []):
        answer = answers.get(o["when_owner_answer"])
        if answer in (None, ""):
            notes.append(f"Not checked: owner question {o['when_owner_answer']} not answered yet")
        elif str(answer).strip().lower() == str(o["equals"]).strip().lower():
            if "set_distress_band" in o:
                bands["distress"] = o["set_distress_band"]
            if "set_viability_band" in o:
                bands["viability"] = o["set_viability_band"]
            notes.append(f"APPLIED: {o['reason']}")
        else:
            notes.append(f"Checked, not triggered (owner question {o['when_owner_answer']} = {answer})")
    return notes


# ---------- plain-English wording ----------

def load_wording():
    """The sentences in wording.json. Scoring still works without it - the report just has no explanations."""
    if not WORDING.exists():
        print("[NOTE] wording.json not found - the report will have no plain-English explanations.")
        return {}
    try:
        return json.loads(WORDING.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        stop(f"wording.json has a typo on line {e.lineno} (often a missing comma or quote). Fix it and run again.")


class Fields(dict):
    """Fills in {placeholders}. Unknown ones are left as-is and remembered so we can warn."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unknown = set()

    def __missing__(self, key):
        self.unknown.add(key)
        return "{" + key + "}"


def explain(res, wording, problems):
    """Plain-English sentence for a Red, Amber or Green result ('' if not assessed).
    In a Green sentence, {threshold} is the Amber line the business is staying clear of."""
    rating = res["rating"]
    if rating not in ("Red", "Amber", "Green") or not wording:
        return ""
    ind = res["ind"]
    entry = wording.get("indicators", {}).get(ind["id"], {})
    key = rating.lower()
    if res.get("case") and f"{key}_{res['case']}" in entry:
        key = f"{key}_{res['case']}"
    template = entry.get(key) or wording.get("fallback", "{name} is {value}.")
    unit = ind.get("unit", "ratio")
    threshold = ind["amber" if rating == "Green" else rating.lower()]
    v = res.get("value")
    fields = Fields(name=ind.get("name", ind["id"]), rating=rating, value=res.get("display", ""),
                    amber=fmt(ind["amber"], unit), red=fmt(ind["red"], unit), threshold=fmt(threshold, unit),
                    value_pct=f"{v * 100:.0f}%" if v is not None else res.get("display", ""),
                    threshold_pct=f"{threshold * 100:.0f}%", **res.get("facts", {}))
    try:
        text = template.format_map(fields)
    except (ValueError, IndexError, KeyError) as e:
        problems.append(f"{ind['id']} '{key}': the {{curly brackets}} don't match up ({e})")
        return template
    for name in sorted(fields.unknown):
        problems.append(f"{ind['id']} '{key}' uses {{{name}}}, which isn't available for this indicator")
    return text


def pathway_summary(wording, bands):
    return (wording.get("pathways", {}).get(bands["distress"], {}).get(bands["viability"])
            or wording.get("pathway_not_enough_data", ""))


# ---------- Excel output ----------

def write_report_sheet(ws, d, cfg, results, scores, bands, pathway, summary):
    """The plain-English page: overall result, then each Red/Amber indicator with its explanation underneath."""
    ws.title = "Report"

    def add(text="", font=FONT, fill=None):
        ws.append([text])
        cell = ws.cell(row=ws.max_row, column=1)
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
        if fill:
            cell.fill = fill

    def heading(text):
        add(text, HEAD_FONT, HEAD_FILL)

    def score_text(kind):
        s = scores[kind][0]
        return f"{kind.title()} {'n/a' if s is None else f'{s:.0f}'} / 100 ({bands[kind]})"

    add(f"Vyta report: {d['org']}", Font(name="Arial", size=14, bold=True))
    add(f"12 months ending {d['months'][-1]['month']:%d %B %Y}. Scored on {date.today():%d %B %Y}.")
    add()
    add(f"{score_text('distress')}     |     {score_text('viability')}", BOLD)
    add(pathway, BOLD)
    if summary:
        add(summary)
    add()

    sections = (("distress", "Distress warning signs: how much financial trouble is the business in right now?"),
                ("viability", "Viability: if the cash problem were fixed, would the business make money?"))
    for kind, title in sections:
        heading(title)
        mine = [r for r in results if r["ind"]["score"] == kind]
        flagged = [r for rating in ("Red", "Amber") for r in mine if r["rating"] == rating]
        greens = [r for r in mine if r["rating"] == "Green"]
        for label, group, empty in (("Needs attention", flagged, "Nothing flagged Red or Amber."),
                                    ("Going well", greens, "Nothing rated Green yet.")):
            add(label, Font(name="Arial", size=11, bold=True))
            if not group:
                add(empty)
            for r in group:
                ind = r["ind"]
                add(f"{r['rating'].upper()}   {ind['id']}  {ind.get('name', '')}: {r.get('display', '')}",
                    BOLD, FILLS[r["rating"]])
                add(r.get("explanation") or r.get("note", ""))
            add()

    skipped = [r for r in results if r["points"] is None]
    if skipped:
        heading("Not assessed (left out of the scores)")
        for r in skipped:
            add(f"{r['ind']['id']}  {r['ind'].get('name', '')}: {r.get('note', '')}")
        add()
    add(cfg.get("disclaimer", ""), Font(name="Arial", size=9, italic=True))
    set_widths(ws, [120])


def write_workbook(path, d, cfg, results, scores, bands, override_notes, pathway, summary):
    wb = Workbook()
    ms = d["months"]

    write_report_sheet(wb.active, d, cfg, results, scores, bands, pathway, summary)

    # Sheet 2: Summary
    ws = wb.create_sheet("Summary")
    rows = [
        ("Vyta score", ""),
        ("Organisation", d["org"]),
        ("Period", f"12 months ending {ms[-1]['month']:%d %b %Y}"),
        ("Months with activity", f"{len(active_months(d))} of {len(ms[-12:])}"),
        ("Unpaid invoices as at", f"{d['as_at']:%d %b %Y}"),
        ("Scored on", date.today().strftime("%d %b %Y")),
        ("", ""),
    ]
    result_start = len(rows) + 1
    for kind in ("distress", "viability"):
        score, weight, possible, scored = scores[kind]
        label = "Distress score (0-100, higher = worse)" if kind == "distress" else \
            "Viability score (0-100, higher = better)"
        rows += [
            (label, "" if score is None else round(score, 1)),
            (f"{kind.title()} band", bands[kind]),
            (f"{kind.title()} coverage", f"Based on {weight:g} of {possible:g} weight points "
                                         f"({len(scored)} of {sum(1 for r in results if r['ind']['score'] == kind)} "
                                         "indicators had data)"),
        ]
    rows += [
        ("Indicative pathway", pathway),
        ("What this means", summary),
        ("Overrides", "\n".join(override_notes) or "None set up"),
        ("", ""),
    ]
    for kind in ("distress", "viability"):
        mine = [r for r in results if r["ind"]["score"] == kind]
        counts = {c: sum(1 for r in mine if r["rating"] == c) for c in ("Red", "Amber", "Green")}
        other = len(mine) - sum(counts.values())
        rows.append((f"{kind.title()} indicators",
                     f"{counts['Red']} Red, {counts['Amber']} Amber, {counts['Green']} Green, {other} not assessed"))
    rows += [("", ""), ("Important", cfg.get("disclaimer", ""))]
    for label, val in rows:
        ws.append([label, val])
    for row in ws.iter_rows():
        row[0].font = BOLD
        row[1].font = FONT
        row[1].alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    ws["A1"].font = Font(name="Arial", size=12, bold=True)
    for r in range(result_start, result_start + 6, 3):
        ws.cell(row=r, column=2).font = Font(name="Arial", size=12, bold=True)
    set_widths(ws, [30, 100])

    # Sheet 2: Indicators
    ind_ws = wb.create_sheet("Indicators")
    headers = ["ID", "Score", "Indicator", "Result", "Value", "Amber at", "Red at", "Weight", "Points",
               "What this means", "How it's calculated", "Working / notes", "Spec status"]
    ind_ws.append(headers)
    style_header(ind_ws, 1, len(headers))
    for r in results:
        ind = r["ind"]
        unit = ind.get("unit", "ratio")
        ind_ws.append([ind["id"], ind["score"].title(), ind.get("name", ""), r["rating"], r.get("display", ""),
                       fmt(ind["amber"], unit), fmt(ind["red"], unit), ind["weight"],
                       "" if r["points"] is None else r["points"], r.get("explanation", ""),
                       ind.get("calculation", ""), r.get("note", ""), ind.get("status", "")])
        for cell in ind_ws[ind_ws.max_row]:
            cell.font = FONT
            cell.alignment = WRAP
        ind_ws.cell(row=ind_ws.max_row, column=4).fill = FILLS.get(r["rating"], FILLS[NOT_ASSESSED])
    ind_ws.freeze_panes = "D2"
    set_widths(ind_ws, [6, 10, 30, 16, 16, 10, 10, 8, 8, 60, 45, 60, 26])

    # Sheet 3: Owner questions
    q_ws = wb.create_sheet("Owner questions")
    q_ws.append(["#", "Question", "Feeds into", "Answer"])
    style_header(q_ws, 1, 4)
    for q in cfg.get("owner_questions", []):
        answer = q.get("answer")
        q_ws.append([q["id"], q["question"], q.get("feeds", ""),
                     OWNER_QUESTION if answer in (None, "") else answer])
        for cell in q_ws[q_ws.max_row]:
            cell.font = FONT
            cell.alignment = WRAP
    set_widths(q_ws, [6, 70, 18, 30])

    wb.save(path)


# ---------- main ----------

def compute(base):
    """Score one data folder. Used by main() below and by dashboard.py, so both always agree."""
    base = Path(base)
    if not base.exists():
        stop(f"Can't find the folder {base}.")
    cfg = load_config()
    wording = load_wording()
    d = load_data(base, cfg)

    results = assess(d, cfg)
    problems = []
    for r in results:
        r["explanation"] = explain(r, wording, problems)
    scores = {kind: total_score(results, kind) for kind in ("distress", "viability")}
    bands = {kind: band_for(scores[kind][0], kind, cfg) for kind in ("distress", "viability")}
    override_notes = apply_overrides(cfg, bands)
    pathway = cfg.get("outcome_matrix", {}).get(bands["distress"], {}).get(bands["viability"],
                                                                          "Not enough data for a pathway")
    return {"base": base, "d": d, "cfg": cfg, "results": results, "scores": scores, "bands": bands,
            "override_notes": override_notes, "pathway": pathway, "summary": pathway_summary(wording, bands),
            "problems": list(dict.fromkeys(problems))}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    run = compute(base)
    d, cfg, results, scores, bands = run["d"], run["cfg"], run["results"], run["scores"], run["bands"]
    override_notes, pathway, summary, problems = (run["override_notes"], run["pathway"], run["summary"],
                                                  run["problems"])

    out = base / "model" / "vyta_score.xlsx"
    try:
        write_workbook(out, d, cfg, results, scores, bands, override_notes, pathway, summary)
    except PermissionError:
        stop("vyta_score.xlsx is open in Excel. Close it and run again.")

    # Terminal summary
    print(f"Organisation: {d['org']}   (data folder: {base})")
    print(f"Period:       12 months ending {d['months'][-1]['month']:%d %b %Y} "
          f"- {len(active_months(d))} month(s) with activity\n")
    for r in results:
        ind = r["ind"]
        print(f"  {ind['id']:<4} {ind.get('name', '')[:36]:<36} {r['rating']:<30} {r.get('display', '')}")
        if r["explanation"]:
            print(textwrap.fill(r["explanation"], width=100, initial_indent=" " * 7, subsequent_indent=" " * 7))
    print()
    for kind in ("distress", "viability"):
        score, weight, possible, _ = scores[kind]
        shown = "n/a" if score is None else f"{score:.1f}"
        print(f"{kind.title() + ' score:':<17} {shown:>5} -> {bands[kind]:<10} "
              f"(based on {weight:g} of {possible:g} weight points)")
    print(f"Pathway:          {pathway}")
    if summary:
        print(textwrap.fill(summary, width=100, initial_indent="What this means:  ", subsequent_indent=" " * 18))
    for note in override_notes:
        print(f"Override:         {note}")
    for problem in problems:
        print(f"[NOTE] wording.json: {problem}")
    print(f"\n[DONE] Saved:\n  {out.resolve()}")


if __name__ == "__main__":
    main()
