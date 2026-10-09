"""History page: both scores across the snapshots saved by sync.py, and the indicators that changed
colour since the previous snapshot. Read-only."""

import streamlit as st

import charts
import snapshots
import ui
from ui import esc, md

run = ui.current_run()
text = ui.wording().get("history_page", {})
snaps = snapshots.load(run["base"])

ui.masthead(run, text.get("title", "History"))
md(f"<div class='vy-sub'>{esc(text.get('intro', ''))}</div>")

if not snaps:
    md(f"<div class='vy-conf'>{esc(text.get('none', 'No history yet.'))}</div>")
elif len(snaps) == 1:
    md(f"<div class='vy-conf'>{esc(text.get('one', '').format(date=snapshots.when_text(snaps[0]['_taken'])))}</div>")

if len(snaps) >= 2:
    latest, previous = snaps[-1], snaps[-2]
    dates = {"before": snapshots.when_text(previous["_taken"]), "after": snapshots.when_text(latest["_taken"])}

    ui.heading(text.get("changes_title", "What changed since last time"))
    rows = []
    for kind in ("distress", "viability"):
        rows.append(f"<tr><td>{esc(text.get(kind + '_chart', kind.title()))}</td>"
                    f"<td class='num'>{esc(snapshots.shown(previous[kind]))}</td><td class='muted'>→</td>"
                    f"<td class='num'><b>{esc(snapshots.shown(latest[kind]))}</b></td></tr>")
    md(f"<div class='vy-scroll'><table class='vy-table'>{''.join(rows)}</table></div>")

    changed = snapshots.changes(previous, latest)
    if changed:
        md(f"<div class='vy-sub' style='margin-top:var(--s4)'>{esc(text.get('changes_sub', '').format(**dates))}</div>")
        items = []
        for c in changed:
            before = (ui.pill({"rating": c["before"]}) + f"<span class='v'>{esc(c['display_before'])}</span>"
                      if c["before"] else f"<span class='v'>{esc(text.get('new_indicator', 'New'))}</span>")
            after = ui.pill({"rating": c["after"]}) + f"<span class='v'>{esc(c['display_after'])}</span>"
            items.append(f"<div class='vy-item'><div class='n'>{esc(c['id'])}</div><div>"
                         f"<span class='t'>{esc(c['name'])}</span>"
                         f"<div class='x'>{before}<span class='arrow'>→</span>{after}</div></div></div>")
        md("".join(items))
    else:
        md(f"<div class='vy-sub' style='margin-top:var(--s4)'>{esc(text.get('changes_none', '').format(**dates))}</div>")

    left, right = st.columns(2)
    for col, kind in ((left, "distress"), (right, "viability")):
        with col:
            ui.heading(text.get(kind + "_chart", kind.title()), text.get(kind + "_sub"))
            ui.chart(charts.score_history(snaps, kind, run["cfg"]["bands"][kind]), key=f"history-{kind}")

if snaps:
    ui.heading(text.get("snapshots_title", "Every snapshot"))
    rows = [f"<tr><td>{esc(snapshots.when_text(s['_taken']))}</td>"
            f"<td class='num'>{esc(snapshots.shown(s['distress']))}</td>"
            f"<td class='num'>{esc(snapshots.shown(s['viability']))}</td>"
            f"<td class='muted'>{esc(s.get('pathway', ''))}</td><td class='muted'>{esc(s.get('confidence', ''))}</td></tr>"
            for s in reversed(snaps)]
    md("<div class='vy-scroll'><table class='vy-table'><tr><th>Taken</th><th>Distress</th><th>Viability</th>"
       f"<th>Pathway</th><th>Confidence</th></tr>{''.join(rows)}</table></div>")
