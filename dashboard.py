"""
VYTA - Dashboard
-----------------
Run with:   py -m streamlit run dashboard.py
            (or, with the .venv not activated:  .venv\\Scripts\\python.exe -m streamlit run dashboard.py)

Opens in your web browser (http://localhost:8501). It runs only on this computer.
Pick a business in the left sidebar. Close the terminal window (or press Ctrl+C) to stop it.

Shows the Distress and Viability scores, the outcome pathway, a traffic-light table of every
indicator and the plain-English summary, with a button to export the report as a PDF.

Read-only: it reads the files already made by build_model.py. It never contacts Xero.
All wording comes from wording.json and scorecard.json.
"""

import contextlib
import html
import io
import json
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import score
from report_pdf import BAND_RATING, KINDS, RATING_STYLE, build_pdf, rating_key

DOTS = {"Red": "🔴", "Amber": "🟠", "Green": "🟢", "Not assessed": "⚪"}

st.set_page_config(page_title="Vyta", page_icon="📊", layout="wide")
st.markdown("""
<style>
  .block-container { max-width: 1150px; padding-top: 2rem; padding-bottom: 3rem; }
  .vy-card { border-radius: 10px; padding: 16px 20px; height: 100%; color: #222; }
  .vy-card .label { font-size: 0.8rem; letter-spacing: .06em; text-transform: uppercase; font-weight: 600; }
  .vy-card .value { font-size: 2.8rem; font-weight: 700; line-height: 1.1; }
  .vy-card .value span { font-size: 1rem; font-weight: 400; }
  .vy-card .band { font-size: 1.15rem; font-weight: 700; }
  .vy-card .hint { font-size: 0.8rem; color: #555; margin-top: 4px; }
  .vy-path { background: #EEF2F8; border-left: 5px solid #1F3864; border-radius: 8px; padding: 14px 18px;
             margin-top: 14px; color: #222; }
  .vy-path .label { font-size: 0.75rem; letter-spacing: .06em; text-transform: uppercase; color: #555; }
  .vy-path .title { font-weight: 700; font-size: 1.05rem; margin: 2px 0 6px; }
  .vy-path .note { font-size: 0.8rem; color: #555; margin-top: 6px; }
  .vy-item { background: #FAFAFA; border-left: 5px solid; border-radius: 6px; padding: 10px 14px;
             margin-bottom: 8px; color: #222; }
  .vy-item .head { font-weight: 700; }
  .vy-pill { display: inline-block; border-radius: 10px; padding: 0 8px; font-size: 0.8rem; font-weight: 700;
             margin-left: 6px; }
</style>
""", unsafe_allow_html=True)


# ---------- loading ----------

def data_folders():
    """Folders that build_model.py has already processed, e.g. data, data_healthy, data_stressed."""
    folders = sorted(p for p in Path(".").iterdir() if (p / "model" / "monthly_summary.csv").exists())
    return sorted(folders, key=lambda p: (p.name != "data", p.name))


def org_name(folder):
    try:
        org = json.loads((folder / "raw" / "organisation.json").read_text())
        return org["Organisations"][0]["Name"]
    except (OSError, KeyError, IndexError, ValueError):
        return folder.name


def run_scoring(folder):
    """score.compute(), with its plain-text messages captured so they can be shown on the page."""
    messages = io.StringIO()
    try:
        with contextlib.redirect_stdout(messages):
            run = score.compute(folder)
    except SystemExit:
        st.error(messages.getvalue().replace("[STOPPED]", "").strip() or "Scoring stopped.")
        st.stop()
    return run, messages.getvalue()


# ---------- page pieces ----------

def score_card(kind, run):
    s, weight, possible, _ = run["scores"][kind]
    band = run["bands"][kind]
    bg, fg = RATING_STYLE[BAND_RATING.get(band, "Not assessed")]
    direction = "higher = worse" if kind == "distress" else "higher = better"
    st.markdown(f"""
    <div class="vy-card" style="background:{bg}">
      <div class="label" style="color:{fg}">{kind.title()} score</div>
      <div class="value" style="color:{fg}">{'n/a' if s is None else f'{s:.0f}'}<span> / 100</span></div>
      <div class="band" style="color:{fg}">{html.escape(band)}</div>
      <div class="hint">0-100, {direction} · based on {weight:g} of {possible:g} weight points</div>
    </div>""", unsafe_allow_html=True)


def indicator_table(results, kind):
    rows = []
    for r in results:
        if r["ind"]["score"] != kind:
            continue
        ind, unit = r["ind"], r["ind"].get("unit", "ratio")
        key = rating_key(r["rating"])
        rows.append({"": DOTS[key], "ID": ind["id"], "Indicator": ind.get("name", ""),
                     "Result": r["rating"], "Value": r.get("display", "") or "-",
                     "Amber at": score.fmt(ind["amber"], unit), "Red at": score.fmt(ind["red"], unit),
                     "Weight": ind["weight"]})
    df = pd.DataFrame(rows)

    def colour(rating):
        bg, fg = RATING_STYLE[rating_key(rating)]
        return f"background-color: {bg}; color: {fg}; font-weight: 600"

    st.dataframe(df.style.map(colour, subset=["Result"]), hide_index=True, width="stretch",
                 height=35 * (len(df) + 1) + 3,
                 column_config={"": st.column_config.TextColumn(width=30),
                                "ID": st.column_config.TextColumn(width=50),
                                "Indicator": st.column_config.TextColumn(width="large"),
                                "Weight": st.column_config.NumberColumn(width=70)})


def explanation(r):
    bg, fg = RATING_STYLE[rating_key(r["rating"])]
    ind = r["ind"]
    st.markdown(f"""
    <div class="vy-item" style="border-left-color:{fg}">
      <span class="head">{html.escape(ind['id'])} · {html.escape(ind.get('name', ''))}</span>
      <span class="vy-pill" style="background:{bg};color:{fg}">{html.escape(r['rating'])} ·
        {html.escape(r.get('display', ''))}</span>
      <div style="margin-top:4px">{html.escape(r.get('explanation') or r.get('note', ''))}</div>
    </div>""", unsafe_allow_html=True)


# ---------- the page ----------

folders = data_folders()
if not folders:
    st.error("No scored data found. Run  py pull_data.py  and  py build_model.py  first.")
    st.stop()

with st.sidebar:
    st.header("Vyta")
    folder = st.selectbox("Business", folders, format_func=lambda p: f"{org_name(p)}  ({p.name})")
    st.caption("Read-only. Scores come from the files on this computer; Xero is never contacted.")
    st.caption("To refresh after new data: run  py pull_data.py  and  py build_model.py, "
               "then reload this page.")

run, messages = run_scoring(folder)
d, results = run["d"], run["results"]

# Header + export
head, export = st.columns([3, 1], vertical_alignment="bottom")
with head:
    st.title(d["org"])
    st.caption(f"12 months ending {d['months'][-1]['month']:%d %B %Y} · "
               f"{len(score.active_months(d))} of {len(d['months'][-12:])} months with trading activity · "
               f"unpaid invoices as at {d['as_at']:%d %b %Y}")
with export:
    slug = "".join(c if c.isalnum() else "_" for c in d["org"]).strip("_").lower()
    st.download_button("Export report as PDF", data=build_pdf(run), type="primary", icon=":material/download:",
                       file_name=f"vyta_report_{slug}_{date.today():%Y-%m-%d}.pdf", mime="application/pdf")

if d["org"].startswith("TEST"):
    st.info("This is synthetic test data made by make_test_data.py, not a real business.")
for problem in run["problems"]:
    st.warning(f"wording.json: {problem}")

# Scores + pathway
left, right = st.columns(2, gap="medium")
with left:
    score_card("distress", run)
with right:
    score_card("viability", run)

applied = [n for n in run["override_notes"] if n.startswith("APPLIED")]
override = " ".join(applied or run["override_notes"]) or "none set up"
st.markdown(f"""
<div class="vy-path">
  <div class="label">Outcome pathway</div>
  <div class="title">{html.escape(run['pathway'])}</div>
  <div>{html.escape(run['summary'])}</div>
  <div class="note">Statutory demand override: {html.escape(override)}</div>
</div>""", unsafe_allow_html=True)

# Traffic-light tables
st.subheader("Indicators", divider="gray")
for kind, title, question in KINDS:
    st.markdown(f"**{title}** · <span style='color:#666'>{question}</span>", unsafe_allow_html=True)
    indicator_table(results, kind)

# Plain-English summary
st.subheader("What the results mean", divider="gray")
tabs = st.tabs([title.split()[0] for _, title, _ in KINDS])
for tab, (kind, title, _) in zip(tabs, KINDS):
    with tab:
        mine = [r for r in results if r["ind"]["score"] == kind]
        flagged = [r for rating in ("Red", "Amber") for r in mine if r["rating"] == rating]
        greens = [r for r in mine if r["rating"] == "Green"]
        attention, going_well = st.columns(2, gap="medium")
        with attention:
            st.markdown(f"##### Needs attention ({len(flagged)})")
            for r in flagged:
                explanation(r)
            if not flagged:
                st.caption("Nothing flagged Red or Amber.")
        with going_well:
            st.markdown(f"##### Going well ({len(greens)})")
            for r in greens:
                explanation(r)
            if not greens:
                st.caption("Nothing rated Green yet.")

skipped = [r for r in results if r["points"] is None]
if skipped:
    with st.expander(f"Not assessed ({len(skipped)}): left out of the scores"):
        for r in skipped:
            st.markdown(f"**{r['ind']['id']}** {r['ind'].get('name', '')}: {r.get('note', '')}")

st.divider()
st.caption(run["cfg"].get("disclaimer", ""))
