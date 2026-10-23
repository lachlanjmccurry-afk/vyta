"""
VYTA - Where has the cash gone?
--------------------------------
Breaks the change in cash over the last 12 months into a few plain-English steps, for the
dashboard's Cash page:

    opening cash
  + operating profit        net profit from the P&L for the months in between
  + ATO movement            a rising ATO balance means cash was kept (owed, not yet paid)
  + debt movement           new bank loans bring cash in; repayments take it out
  - change in debtors       customers owing more means cash not yet collected
  + change in creditors     owing suppliers more means cash not yet paid out
  + other                   everything else (drawings, asset purchases, depreciation...) -
                            the balancing figure, so the steps always add up to closing cash
  = closing cash

Opening cash is the month-end before the 12-month window. With only 12 months of data there is
no earlier month-end, so it starts at the first month-end instead (covering 11 months).
Overdrafts are already inside cash (it's the bank total), so debt movement counts loans only.

Read-only and does not affect any score.
"""

import score

STEPS = ("Operating profit", "ATO movement", "Debt movement", "Change in debtors", "Change in creditors",
         "Other")


def cash_bridge(d, months=12):
    """{'opening', 'closing', 'opening_month', 'closing_month', 'months_covered', 'steps': [(label, amount)]}."""
    ms = d["months"]
    if len(ms) < 2:
        return None
    start = ms[-months - 1] if len(ms) > months else ms[0]
    period = ms[ms.index(start) + 1:]
    end = ms[-1]

    def change(key):
        return end[key] - start[key]

    def loans(m):
        return score.bank_debt(d, m["month"])[1]

    steps = {
        "Operating profit": sum(m["net_profit"] for m in period),
        "ATO movement": change("ato_liabilities"),
        "Debt movement": loans(end) - loans(start),
        "Change in debtors": -change("debtors"),
        "Change in creditors": change("creditors"),
    }
    steps["Other"] = change("cash") - sum(steps.values())
    return {"opening": start["cash"], "closing": end["cash"], "opening_month": start["month"],
            "closing_month": end["month"], "months_covered": len(period),
            "steps": [(label, steps[label]) for label in STEPS]}
