"""Details page: key month-end balances, then every indicator in Distress / Viability tabs. Each row opens
(plain HTML <details>, no reload) to show the explanation, the 12-month trend with the warning levels, the
figures used and how it's calculated. Every number comes from score.py (via ui.current_run())."""

import streamlit as st

import charts
import score
import trends
import ui
from ui import esc, md

run = ui.current_run()
d, results = run["d"], run["results"]
text = ui.wording().get("details_page", {})
latest = d["months"][-1]


def key_figures():
    cards = []
    for field, label in text.get("figures", {}).items():
        if field not in latest:
            continue
        v = latest[field]
        cards.append(f"<div class='vy-fig'><div class='l'>{esc(label)}</div>"
                     f"<div class='n{' neg' if v < 0 else ''}'>{esc(score.money(v).replace('-', '−'))}</div></div>")
    return f"<div class='vy-figs'>{''.join(cards)}</div>"


def levels(ind):
    unit, sign = ind.get("unit", "ratio"), "≥" if ind["direction"] == "higher_is_worse" else "≤"
    return f"Amber {sign} {score.fmt(ind['amber'], unit)} · Red {sign} {score.fmt(ind['red'], unit)}"


def body(r):
    ind = r["ind"]
    assessed = r["points"] is not None
    parts = [f"<div>{esc(r.get('explanation') if assessed and r.get('explanation') else r.get('note', ''))}</div>"]
    meta = []
    s = trends.indicator_series(d, ind)
    if s["reason"]:
        meta.append(f"<div><div class='k'>{esc(text.get('trend_title', 'Last 12 months'))}</div>"
                    f"<div class='lv'>{esc(text.get('no_trend', 'No trend: {reason}.').format(reason=s['reason']))}</div></div>")
    else:
        months = [m for m, _ in s["points"]]
        meta.append(f"<div><div class='k'>{esc(text.get('trend_title', 'Last 12 months'))}</div>"
                    f"{charts.svg_trend(s['points'], ind)}"
                    f"<div class='lv'>{months[0]:%b %y} – {months[-1]:%b %y}</div></div>")
    facts = r.get("facts") or {}
    if assessed and (facts or r.get("note")):
        pairs = "".join(f"<span class='f'>{esc(k.replace('_', ' ').capitalize())}</span><span>{esc(v)}</span>"
                        for k, v in facts.items())
        note = f"<div class='lv' style='margin-bottom:4px'>{esc(r['note'])}</div>" if r.get("note") else ""
        meta.append(f"<div><div class='k'>{esc(text.get('figures_title', 'Figures used'))}</div>{note}"
                    f"<div class='vy-facts'>{pairs}</div></div>")
    parts.append(f"<div class='meta'>{''.join(meta)}</div>")
    how = [text.get("weight", "Weight in the score: {weight}").format(weight=f"{ind['weight']:g}")]
    if ind.get("calculation"):
        how.append(f"{text.get('how', 'How it is calculated:')} {ind['calculation']}")
    parts.append(f"<div class='how'>{esc(' · '.join(how))}</div>")
    return "".join(parts).replace("\n", " ")


def rows(kind):
    cols = text.get("columns", ["ID", "Indicator", "Value", "Warning levels", "Result"])
    head = "".join(f"<span>{esc(c)}</span>" for c in cols) + "<span></span>"
    out = []
    for r in (r for r in results if r["ind"]["score"] == kind):
        ind = r["ind"]
        value = r.get("display") if r["points"] is not None else "—"
        out.append(f"<details class='vy-row' id='row-{esc(ind['id'])}'><summary>"
                   f"<span class='id'>{esc(ind['id'])}</span><span class='nm'>{esc(score.short_name(ind))}</span>"
                   f"<span class='val'>{esc(value or '—')}</span><span class='lv'>{esc(levels(ind))}</span>"
                   f"<span>{ui.pill(r)}</span><span class='chev'></span></summary>"
                   f"<div class='body'>{body(r)}</div></details>")
    return f"<div class='vy-scroll'><div class='vy-rows'><div class='vy-rowhead'>{head}</div>{''.join(out)}</div></div>"


ui.page_head(text.get("eyebrow", "Details"), text.get("title", "The numbers behind the scores"), text.get("intro"))
md(key_figures())

counts = {kind: sum(1 for r in results if r["ind"]["score"] == kind) for kind in ("distress", "viability")}
tabs = text.get("tabs", {})
with st.container(key="card-indicators"):
    left, right = st.columns([1, 1.4], vertical_alignment="center")
    with left:
        kind = st.segmented_control("Score", list(counts), default="distress", key="details_kind",
                                    format_func=lambda k: f"{tabs.get(k, k.title())} · {counts[k]}",
                                    label_visibility="collapsed") or "distress"
    with right:
        md(f"<div class='vy-q'>{esc(text.get('questions', {}).get(kind, ''))}</div>")
    md(rows(kind))

end = latest["month"]
md(f"<div class='vy-foot'>{esc(text.get('figures_note', '').format(date=f'{end.day} {end:%B %Y}'))} "
   f"{esc(run['cfg'].get('disclaimer', ''))}</div>")
