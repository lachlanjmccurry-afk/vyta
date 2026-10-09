"""Indicators page: every indicator with a 12-month sparkline. Details opens the full trend chart with the
Amber and Red zones shaded, the plain-English explanation and the figures used."""

import streamlit as st

import charts
import score
import trends
import ui
from report_pdf import KINDS
from ui import esc, md

run = ui.current_run()
d, results = run["d"], run["results"]
text = ui.wording().get("indicators_page", {})
WIDTHS = [0.95, 0.5, 2.1, 1.6, 1.35, 1.05, 1.05, 0.6, 0.85]
HEAD = ["Result", "ID", "Indicator", "Last 12 months", "Value", "Amber at", "Red at", "Weight", ""]

series = {r["ind"]["id"]: trends.indicator_series(d, r["ind"]) for r in results}


def cell(content, cls=""):
    md(f"<div class='vy-cell {cls}'>{content}</div>")


def no_trend(reason):
    return text.get("no_trend", "No trend: {reason}.").format(reason=reason)


def detail(r):
    ind, unit = r["ind"], r["ind"].get("unit", "ratio")
    s = series[ind["id"]]
    md(f"{ui.pill(r)} <span class='vy-cell' style='margin-left:var(--s2)'><b>{esc(r.get('display', '')) or '-'}</b>"
       f"</span> <span class='vy-cell muted' style='margin-left:var(--s3)'>Amber at "
       f"{esc(score.fmt(ind['amber'], unit))} · Red at {esc(score.fmt(ind['red'], unit))} · "
       f"weight {ind['weight']:g}</span>")
    if s["reason"]:
        md(f"<div class='vy-sub' style='margin-top:var(--s3)'>{esc(no_trend(s['reason']))}</div>")
    else:
        ui.chart(charts.trend_chart(s["points"], ind), key=f"trend-{ind['id']}")
    ui.heading("What this means")
    md(f"<div class='vy-cell' style='line-height:1.55'>"
       f"{esc(r.get('explanation') if r['points'] is not None else r.get('note', ''))}</div>")
    facts = r.get("facts") or {}
    if r["points"] is not None and (r.get("note") or facts):
        ui.heading("Figures used")
        if r.get("note"):
            md(f"<div class='vy-cell muted'>{esc(r['note'])}</div>")
        if facts:
            pairs = "".join(f"<div class='k'>{esc(k.replace('_', ' ').capitalize())}</div><div>{esc(v)}</div>"
                            for k, v in facts.items())
            md(f"<div class='vy-facts'>{pairs}</div>")
    if ind.get("calculation"):
        md(f"<div class='vy-note'>How it's calculated: {esc(ind['calculation'])}</div>")


def show_detail(r):
    st.dialog(f"{r['ind']['id']} · {r['ind'].get('name', '')}", width="large")(detail)(r)


ui.masthead(run, "Indicators")
intro = text.get("intro", "")
if len(d["months"]) <= 12:
    intro += " " + text.get("short_history", "")
md(f"<div class='vy-sub'>{esc(intro)}</div>")

for kind, title, question in KINDS:
    ui.heading(title, question)
    with st.container(key=f"vyrows-{kind}"):
        for col, label in zip(st.columns(WIDTHS, vertical_alignment="center"), HEAD):
            with col:
                md(f"<div class='vy-head'>{label}</div>")
        for r in (r for r in results if r["ind"]["score"] == kind):
            ind, unit = r["ind"], r["ind"].get("unit", "ratio")
            s = series[ind["id"]]
            c = st.columns(WIDTHS, vertical_alignment="center")
            with c[0]:
                cell(ui.pill(r))
            with c[1]:
                cell(esc(ind["id"]), "id")
            with c[2]:
                cell(esc(score.short_name(ind)))
            with c[3]:
                if s["reason"]:
                    cell(esc(s["reason"]), "small")
                else:
                    ui.chart(charts.sparkline(s["points"]), key=f"spark-{ind['id']}")
            with c[4]:
                cell(esc(r.get("display", "")) or "-")
            with c[5]:
                cell(esc(score.fmt(ind["amber"], unit)), "muted")
            with c[6]:
                cell(esc(score.fmt(ind["red"], unit)), "muted")
            with c[7]:
                cell(f"{ind['weight']:g}", "muted")
            with c[8]:
                if st.button("Details", key=f"details-{ind['id']}", type="tertiary"):
                    show_detail(r)
