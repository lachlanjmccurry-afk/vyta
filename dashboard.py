"""
VYTA - Dashboard
-----------------
Run with:   py -m streamlit run dashboard.py
            (or, with the .venv not activated:  .venv\\Scripts\\python.exe -m streamlit run dashboard.py)

Opens in your web browser (http://localhost:8501). It runs only on this computer.
Pick a client in the left sidebar. Close the terminal window (or press Ctrl+C) to stop it.

Laid out as an adviser's one-page memo: a one-sentence verdict, the two scores, data confidence,
the top 3 issues, what's working and the recommended pathway, with every indicator under
"Full detail" (click a row to see its explanation). The Export button saves the PDF report.

Read-only: it reads the files already made by build_model.py and never contacts Xero.
All wording comes from wording.json and scorecard.json; colours and theme are in .streamlit\\config.toml.
"""

import contextlib
import html
import io
import json
from datetime import date
from pathlib import Path

import streamlit as st

import score
from report_pdf import BAND_RATING, KINDS, RATING_STYLE, build_pdf, rating_key

NAVY = "#1F3864"
INK = "#2B2B2B"
MUTED = "#6B665F"      # warm grey
RULE = "#E4E0DA"
PAPER = "#F5F3EF"
SERIF = "Georgia, 'Times New Roman', serif"
# Small traffic-light markers next to the score bands (stronger than the pale result-pill backgrounds)
MARKER = {"Red": "#B3261E", "Amber": "#D99A00", "Green": "#3F7D3A", "Not assessed": "#A8A29A"}

st.set_page_config(page_title="Vyta", layout="wide", menu_items={})
st.markdown(f"""
<style>
  /* Hide Streamlit's own toolbar, menu and Deploy button */
  [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stAppDeployButton"],
  #MainMenu {{ display: none !important; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  .block-container {{ max-width: 1040px; padding-top: 2.2rem; padding-bottom: 3rem; }}
  [data-testid="stSidebar"] {{ background: {PAPER}; }}
  .vy-brand {{ font-family: {SERIF}; font-size: 1.7rem; color: {NAVY}; margin: 0 0 18px; letter-spacing: .01em; }}

  .vy-eyebrow {{ font-size: .78rem; letter-spacing: .09em; text-transform: uppercase; color: {MUTED};
                 font-weight: 600; }}
  .vy-meta {{ font-size: .85rem; color: {MUTED}; margin-top: 2px; }}
  .vy-verdict {{ font-family: {SERIF}; font-size: 2.05rem; line-height: 1.25; color: {INK}; font-weight: 400;
                 margin: 14px 0 22px; max-width: 900px; }}
  h3.vy-h {{ font-family: {SERIF}; font-weight: 400; font-size: 1.35rem; color: {INK}; margin: 30px 0 4px;
             padding-bottom: 6px; border-bottom: 1px solid {RULE}; }}
  .vy-sub {{ color: {MUTED}; font-size: .9rem; margin: 2px 0 10px; }}

  .vy-card {{ background: #fff; border: 1px solid {RULE}; border-radius: 8px; padding: 18px 22px; }}
  .vy-card .label {{ font-size: .78rem; letter-spacing: .09em; text-transform: uppercase; color: {MUTED};
                     font-weight: 600; }}
  .vy-card .num {{ font-family: {SERIF}; font-size: 3.2rem; line-height: 1.05; color: {INK}; margin-top: 6px; }}
  .vy-card .num span {{ font-family: inherit; font-size: 1.05rem; color: {MUTED}; }}
  .vy-card .band {{ font-size: 1.05rem; font-weight: 600; color: {INK}; margin-top: 4px; }}
  .vy-card .hint {{ font-size: .8rem; color: {MUTED}; margin-top: 8px; }}
  .vy-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;
             vertical-align: 1px; }}

  .vy-conf {{ margin: 16px 0 0; padding: 10px 14px; background: {PAPER}; border-radius: 6px; font-size: .92rem;
              color: {INK}; }}
  .vy-conf b {{ color: {NAVY}; }}

  .vy-item {{ display: grid; grid-template-columns: 28px 1fr; gap: 0 10px; padding: 12px 0;
              border-bottom: 1px solid {RULE}; }}
  .vy-item:last-child {{ border-bottom: none; }}
  .vy-item .n {{ font-family: {SERIF}; font-size: 1.25rem; color: {NAVY}; line-height: 1.3; }}
  .vy-item .t {{ font-weight: 600; color: {INK}; }}
  .vy-item .x {{ color: {INK}; margin-top: 3px; line-height: 1.5; }}
  .vy-pill {{ display: inline-block; border-radius: 4px; padding: 1px 7px; font-size: .78rem; font-weight: 700;
              margin-left: 8px; white-space: nowrap; vertical-align: 1px; }}

  .vy-path .label {{ font-weight: 600; color: {NAVY}; font-size: 1.05rem; }}
  .vy-path .x {{ margin-top: 4px; line-height: 1.5; }}
  .vy-note {{ color: {MUTED}; font-size: .82rem; margin-top: 10px; }}

  /* Full detail: table rows that expand to show the explanation */
  .vy-table {{ border-top: 1px solid {RULE}; margin-bottom: 8px; }}
  .vy-row, .vy-table summary {{ display: grid; align-items: center; gap: 0 12px;
      grid-template-columns: 16px 108px 44px minmax(150px, 1.5fr) 138px 92px 92px 58px; padding: 8px 6px; }}
  .vy-row.head {{ font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: {MUTED};
                  font-weight: 600; border-bottom: 1px solid {RULE}; }}
  .vy-table details {{ border-bottom: 1px solid {RULE}; }}
  .vy-table summary {{ cursor: pointer; list-style: none; font-size: .92rem; }}
  .vy-table summary::-webkit-details-marker {{ display: none; }}
  .vy-table summary:hover {{ background: {PAPER}; }}
  .vy-table .chev {{ color: {MUTED}; transition: transform .15s; display: inline-block; }}
  .vy-table details[open] .chev {{ transform: rotate(90deg); }}
  .vy-table .id {{ color: {MUTED}; }}
  .vy-table .body {{ padding: 4px 6px 14px 34px; line-height: 1.55; color: {INK}; max-width: 860px; }}
  .vy-table .body .name {{ font-weight: 600; }}
  .vy-table .body .work {{ color: {MUTED}; font-size: .83rem; margin-top: 6px; }}

  /* Export button: neutral navy outline */
  [data-testid="stDownloadButton"] button {{ background: #fff; color: {NAVY}; border: 1px solid {NAVY}; }}
  [data-testid="stDownloadButton"] button:hover {{ background: {NAVY}; color: #fff; border-color: {NAVY}; }}
  [data-testid="stDownloadButton"] button p {{ font-weight: 600; }}

  .stTabs [data-baseweb="tab-list"] {{ gap: 24px; border-bottom: 1px solid {RULE}; }}
  .stTabs [data-baseweb="tab"] p {{ font-size: .95rem; }}
</style>
""", unsafe_allow_html=True)


# ---------- loading ----------

def data_folders():
    """Folders that build_model.py has already processed, e.g. data, data_healthy, data_stressed."""
    folders = [p for p in Path(".").iterdir() if (p / "model" / "monthly_summary.csv").exists()]
    return sorted(folders, key=lambda p: (p.name != "data", p.name))


def org_name(folder):
    try:
        return json.loads((folder / "raw" / "organisation.json").read_text())["Organisations"][0]["Name"]
    except (OSError, KeyError, IndexError, ValueError):
        return folder.name


def run_scoring(folder):
    """score.compute(), with its plain-text messages captured so problems can be shown on the page."""
    messages = io.StringIO()
    try:
        with contextlib.redirect_stdout(messages):
            return score.compute(folder)
    except SystemExit:
        st.error(messages.getvalue().replace("[STOPPED]", "").strip() or "Scoring stopped.")
        st.stop()


# ---------- small pieces ----------

def esc(text):
    return html.escape(str(text or ""))


def pill(r):
    bg, fg = RATING_STYLE[rating_key(r["rating"])]
    label = r["rating"] if r["rating"] in ("Red", "Amber", "Green") else "Not assessed"
    return f'<span class="vy-pill" style="background:{bg};color:{fg}">{esc(label)}</span>'


def score_card(kind, run):
    s, weight, possible, _ = run["scores"][kind]
    band = run["bands"][kind]
    marker = MARKER[BAND_RATING.get(band, "Not assessed")]
    meaning = "Higher means more distress" if kind == "distress" else "Higher means more viable"
    noun = "distress" if kind == "distress" else "viability"
    return f"""
    <div class="vy-card">
      <div class="label">{kind.title()}</div>
      <div class="num">{'n/a' if s is None else f'{s:.0f}'}<span> / 100</span></div>
      <div class="band"><span class="vy-dot" style="background:{marker}"></span>{esc(band)} {noun}</div>
      <div class="hint">{meaning} · {weight:g} of {possible:g} weight points assessed</div>
    </div>"""


def memo_list(items, numbered):
    rows = []
    for i, r in enumerate(items, start=1):
        ind = r["ind"]
        rows.append(f"""
        <div class="vy-item">
          <div class="n">{i if numbered else '&#10003;'}</div>
          <div><span class="t">{esc(ind.get('name', ''))}</span>{pill(r)}
            <span style="color:{MUTED};font-size:.88rem;margin-left:6px">{esc(r.get('display', ''))}</span>
            <div class="x">{esc(r.get('explanation') or r.get('note', ''))}</div></div>
        </div>""")
    return "".join(rows)


def detail_table(results, kind):
    head = ("<div class='vy-row head'><span></span><span>Result</span><span>ID</span><span>Indicator</span>"
            "<span>Value</span><span>Amber at</span><span>Red at</span><span>Weight</span></div>")
    rows = []
    for r in (r for r in results if r["ind"]["score"] == kind):
        ind, unit = r["ind"], r["ind"].get("unit", "ratio")
        assessed = r["points"] is not None
        body = (f"<div><span class='name'>{esc(ind.get('name', ''))}.</span> "
                f"{esc(r.get('explanation') if assessed else r.get('note', ''))}</div>")
        if assessed and r.get("note"):
            body += f"<div class='work'>Working: {esc(r['note'])}</div>"
        rows.append(f"""
        <details><summary>
          <span class="chev">&#9656;</span><span>{pill(r)}</span><span class="id">{esc(ind['id'])}</span>
          <span>{esc(score.short_name(ind))}</span><span>{esc(r.get('display', '')) or '-'}</span>
          <span>{esc(score.fmt(ind['amber'], unit))}</span><span>{esc(score.fmt(ind['red'], unit))}</span>
          <span>{ind['weight']:g}</span>
        </summary><div class="body">{body}</div></details>""")
    return f"<div class='vy-table'>{head}{''.join(rows)}</div>"


# ---------- the page ----------

folders = data_folders()
if not folders:
    st.error("No scored data found yet.")
    st.stop()

with st.sidebar:
    st.markdown("<div class='vy-brand'>Vyta</div>", unsafe_allow_html=True)
    folder = st.selectbox("Client", folders, format_func=org_name)

run = run_scoring(folder)
d, results = run["d"], run["results"]

# Masthead
left, right = st.columns([4, 1], vertical_alignment="top")
with left:
    sample = " · sample data" if d["org"].startswith("TEST") else ""
    st.markdown(f"""
    <div class="vy-eyebrow">Financial health check · {esc(d['org'])}{esc(sample)}</div>
    <div class="vy-meta">12 months to {d['months'][-1]['month']:%d %B %Y} · prepared {date.today():%d %B %Y}</div>
    """, unsafe_allow_html=True)
with right:
    slug = "".join(c if c.isalnum() else "_" for c in d["org"]).strip("_").lower()
    st.download_button("Export PDF", data=build_pdf(run), icon=":material/download:", width="stretch",
                       file_name=f"vyta_report_{slug}_{date.today():%Y-%m-%d}.pdf", mime="application/pdf")

st.markdown(f"<div class='vy-verdict'>{esc(run['verdict'])}</div>", unsafe_allow_html=True)
for problem in run["problems"]:
    st.warning(f"wording.json: {problem}")

summary_tab, detail_tab = st.tabs(["Summary", "Full detail"])

with summary_tab:
    a, b = st.columns(2, gap="medium")
    a.markdown(score_card("distress", run), unsafe_allow_html=True)
    b.markdown(score_card("viability", run), unsafe_allow_html=True)

    conf = run["confidence"]
    st.markdown(f"<div class='vy-conf'><b>Data confidence: {esc(conf['level'])}.</b> {esc(conf['text'])}</div>",
                unsafe_allow_html=True)

    issues = score.top_issues(results)
    st.markdown("<h3 class='vy-h'>Top 3 issues</h3>", unsafe_allow_html=True)
    st.markdown(memo_list(issues, numbered=True) if issues else
                "<div class='vy-sub'>No indicators are flagged Red or Amber.</div>", unsafe_allow_html=True)

    working = score.whats_working(results)
    st.markdown("<h3 class='vy-h'>What's working</h3>", unsafe_allow_html=True)
    st.markdown(memo_list(working, numbered=False) if working else
                "<div class='vy-sub'>Nothing is rated Green yet.</div>", unsafe_allow_html=True)

    applied = [n for n in run["override_notes"] if n.startswith("APPLIED")]
    override = " ".join(applied or run["override_notes"]) or "none set up"
    st.markdown(f"""
    <h3 class='vy-h'>Recommended pathway</h3>
    <div class="vy-path">
      <div class="label">{esc(score.sentence_case(run['pathway']))}</div>
      <div class="x">{esc(run['summary'])}</div>
    </div>
    <div class="vy-note">Statutory demand override: {esc(override)}</div>""", unsafe_allow_html=True)

    flagged = sum(1 for r in results if r["rating"] in score.SEVERITY)
    skipped = sum(1 for r in results if r["points"] is None)
    st.markdown(f"<div class='vy-note' style='margin-top:26px'>{flagged} indicators are Red or Amber and "
                f"{skipped} couldn't be assessed. See Full detail for every indicator.<br>"
                f"{esc(run['cfg'].get('disclaimer', ''))}</div>", unsafe_allow_html=True)

with detail_tab:
    st.markdown("<div class='vy-sub' style='margin-top:6px'>Click a row to see what it means and how it was "
                "worked out.</div>", unsafe_allow_html=True)
    for kind, title, question in KINDS:
        st.markdown(f"<h3 class='vy-h'>{esc(title)}</h3><div class='vy-sub'>{esc(question)}</div>",
                    unsafe_allow_html=True)
        st.markdown(detail_table(results, kind), unsafe_allow_html=True)
