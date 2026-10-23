"""
VYTA - Indicator trends
------------------------
Each indicator's value at each of the last 12 month-ends, for the dashboard's sparklines and
drill-down charts. It re-runs the calculation in score.py on the data up to each month-end, so a
trend always uses the same formula as the score (and its last point is the scored value).

A month shows as a gap (None) when the formula gives a rule-based rating instead of a number
(e.g. "No debts due") or isn't assessed. Some indicators have no trend at all - see NO_TREND.

Read-only and does not affect any score.
"""

import score

# Indicators that can't be traced back month by month
NO_TREND = {
    "D8": "Snapshot only",    # unpaid bills are as at the day the data was pulled
    "D10": "Snapshot only",   # unpaid sales invoices, same
}


def as_at(d, i):
    """The business as it looked at month-end i (data after that month dropped)."""
    return dict(d, months=d["months"][:i + 1])


def indicator_series(d, ind, n=12):
    """{'points': [(month, value or None), ...] oldest first, 'reason': None or why there's no trend}."""
    calc = score.CALCS.get(ind["id"])
    if ind["id"] in NO_TREND or calc is None:
        return {"points": [], "reason": NO_TREND.get(ind["id"], "No calculation")}
    ms = d["months"]
    points = []
    for i in range(max(0, len(ms) - n), len(ms)):
        res = calc(as_at(d, i), ind)
        points.append((ms[i]["month"], res.get("value")))
    if sum(v is not None for _, v in points) < 2:
        latest = calc(d, ind)
        reason = latest.get("display") if "value" not in latest else None
        return {"points": points, "reason": reason or "Needs more history"}
    return {"points": points, "reason": None}
