"""Cash page: "Where has the cash gone?" waterfall (cashflow.py) and the month-end cash balance."""

import charts
import ui
from cashflow import cash_bridge
from ui import esc, md

run = ui.current_run()
d = run["d"]
text = ui.wording().get("cash_page", {})

ui.page_head("Cash", text.get("title", "Where has the cash gone?"))

bridge = cash_bridge(d)
if bridge is None:
    md("<div class='vy-sub'>At least two month-ends are needed to show how cash moved.</div>")
else:
    fields = dict(start=f"{bridge['opening_month']:%B %Y}", end=f"{bridge['closing_month']:%B %Y}",
                  months=bridge["months_covered"])
    sub = text.get("intro", "").format(**fields)
    if len(d["months"]) <= 12:
        sub += " " + text.get("short_history", "").format(**fields)
    md(f"<div class='vy-sub'>{esc(sub)}</div>")
    ui.chart(charts.waterfall(bridge), key="waterfall")

    explain = text.get("steps", {})
    rows = [f"<tr class='total'><td>Opening cash ({bridge['opening_month']:%b %Y})</td><td></td>"
            f"<td class='num'>{charts.money(bridge['opening'])}</td></tr>"]
    for label, amount in bridge["steps"]:
        rows.append(f"<tr><td>{esc(label)}</td><td class='muted'>{esc(explain.get(label, ''))}</td>"
                    f"<td class='num'>{'+' if amount >= 0 else ''}{charts.money(amount)}</td></tr>")
    rows.append(f"<tr class='total'><td>Closing cash ({bridge['closing_month']:%b %Y})</td><td></td>"
                f"<td class='num'>{charts.money(bridge['closing'])}</td></tr>")
    md("<div class='vy-scroll'><table class='vy-table'><tr><th>Step</th><th>What it means</th>"
       f"<th style='text-align:right'>Amount</th></tr>{''.join(rows)}</table></div>")

    start = d["months"].index(next(m for m in d["months"] if m["month"] == bridge["opening_month"]))
    ui.heading(text.get("cash_balance_title", "Month-end cash balance"))
    ui.chart(charts.cash_line(d["months"][start:]), key="cash_line")
