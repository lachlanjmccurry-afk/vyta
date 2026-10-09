"""
VYTA - Shared look and helpers for the dashboard pages
-------------------------------------------------------
Palette, styling, the logo mark, result pills and loading the scores. Used by dashboard.py and
every page in views\\. Read-only: never writes files and never contacts Xero.
"""

import contextlib
import html
import io
import json
from datetime import date
from pathlib import Path

import streamlit as st

import score
from charts import INK, MUTED, NAVY, RULE
from report_pdf import RATING_STYLE, rating_key

PAPER = "#F5F3EF"
SERIF = "Georgia, 'Times New Roman', serif"
# Small traffic-light markers next to the score bands (stronger than the pale result-pill backgrounds)
MARKER = {"Red": "#B3261E", "Amber": "#D99A00", "Green": "#3F7D3A", "Not assessed": "#A8A29A"}
CHART_CONFIG = {"displayModeBar": False, "responsive": True}

# One spacing scale for the whole dashboard: --s1 4px ... --s7 40px
CSS = f"""
<style>
  :root {{ --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 40px; }}

  /* Hide Streamlit's own toolbar, menu and Deploy button */
  [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stAppDeployButton"],
  #MainMenu {{ display: none !important; }}
  header[data-testid="stHeader"] {{ background: #fff; border-bottom: 1px solid {RULE}; }}
  .block-container {{ max-width: 1040px; padding-top: calc(var(--s7) + var(--s6)); padding-bottom: var(--s7); }}
  [data-testid="stSidebar"] {{ background: {PAPER}; }}

  /* Logo mark */
  .vy-logo {{ display: flex; align-items: center; gap: var(--s3); margin: 0 0 var(--s5); }}
  .vy-logo .mark {{ width: 34px; height: 34px; border-radius: 6px; background: {NAVY}; color: #fff;
                    font-family: {SERIF}; font-size: 1.35rem; line-height: 34px; text-align: center; }}
  .vy-logo .word {{ font-family: {SERIF}; font-size: 1.6rem; color: {NAVY}; letter-spacing: .02em; }}
  .vy-logo .tag {{ font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: {MUTED};
                   margin-top: 2px; }}

  .vy-eyebrow {{ font-size: .78rem; letter-spacing: .09em; text-transform: uppercase; color: {MUTED};
                 font-weight: 600; }}
  .vy-meta {{ font-size: .85rem; color: {MUTED}; margin-top: var(--s1); }}
  .vy-verdict {{ font-family: {SERIF}; font-size: 2.05rem; line-height: 1.25; color: {INK}; font-weight: 400;
                 margin: var(--s4) 0 var(--s5); max-width: 900px; }}
  h2.vy-title {{ font-family: {SERIF}; font-weight: 400; font-size: 1.9rem; color: {INK};
                 margin: var(--s3) 0 var(--s2); padding: 0; }}
  h3.vy-h {{ font-family: {SERIF}; font-weight: 400; font-size: 1.35rem; color: {INK};
             margin: var(--s6) 0 var(--s1); padding: 0 0 var(--s2); border-bottom: 1px solid {RULE}; }}
  .vy-sub {{ color: {MUTED}; font-size: .9rem; margin: var(--s1) 0 var(--s3); line-height: 1.5; }}

  .vy-card {{ background: #fff; border: 1px solid {RULE}; border-radius: 8px; padding: var(--s4) var(--s5); }}
  .vy-card .label {{ font-size: .78rem; letter-spacing: .09em; text-transform: uppercase; color: {MUTED};
                     font-weight: 600; }}
  .vy-card .num {{ font-family: {SERIF}; font-size: 3.2rem; line-height: 1.05; color: {INK}; margin-top: var(--s2); }}
  .vy-card .num span {{ font-family: inherit; font-size: 1.05rem; color: {MUTED}; }}
  .vy-card .band {{ font-size: 1.05rem; font-weight: 600; color: {INK}; margin-top: var(--s1); }}
  .vy-card .hint {{ font-size: .8rem; color: {MUTED}; margin-top: var(--s2); }}
  .vy-card .num span.arrow, .arrow {{ color: {MUTED}; font-size: inherit; margin: 0 var(--s2); }}
  .vy-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: var(--s2);
             vertical-align: 1px; }}

  .vy-conf {{ margin: var(--s4) 0 0; padding: var(--s3) var(--s4); background: {PAPER}; border-radius: 6px;
              font-size: .92rem; color: {INK}; }}
  .vy-conf b {{ color: {NAVY}; }}

  .vy-item {{ display: grid; grid-template-columns: 28px 1fr; gap: 0 var(--s3); padding: var(--s3) 0;
              border-bottom: 1px solid {RULE}; }}
  .vy-item:last-child {{ border-bottom: none; }}
  .vy-item .n {{ font-family: {SERIF}; font-size: 1.25rem; color: {NAVY}; line-height: 1.3; }}
  .vy-item .t {{ font-weight: 600; color: {INK}; }}
  .vy-item .x {{ color: {INK}; margin-top: var(--s1); line-height: 1.5; }}
  .vy-item .v {{ color: {MUTED}; font-size: .88rem; margin-left: var(--s2); }}
  .vy-pill {{ display: inline-block; border-radius: 4px; padding: 1px 7px; font-size: .78rem; font-weight: 700;
              white-space: nowrap; vertical-align: 1px; }}
  .vy-item .vy-pill {{ margin-left: var(--s2); }}

  .vy-path .label {{ font-weight: 600; color: {NAVY}; font-size: 1.05rem; }}
  .vy-path .x {{ margin-top: var(--s1); line-height: 1.5; }}
  .vy-note {{ color: {MUTED}; font-size: .82rem; margin-top: var(--s3); line-height: 1.5; }}

  /* Indicators page: one row per indicator, built from Streamlit columns */
  .vy-head {{ font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: {MUTED};
              font-weight: 600; }}
  [class*="st-key-vyrows"] [data-testid="stHorizontalBlock"] {{ border-bottom: 1px solid {RULE};
      padding: var(--s1) 0; align-items: center; gap: var(--s3); }}
  [class*="st-key-vyrows"] [data-testid="stHorizontalBlock"]:hover {{ background: {PAPER}; }}
  [class*="st-key-vyrows"] [data-testid="stElementContainer"] {{ margin: 0; }}
  [class*="st-key-vyrows"] [data-testid="stVerticalBlock"] {{ gap: 0; }}
  [class*="st-key-vyrows"] [data-testid="stMarkdownContainer"] p {{ margin: 0; }}
  .vy-cell {{ font-size: .92rem; color: {INK}; line-height: 1.3; }}
  .vy-cell.id, .vy-cell.muted {{ color: {MUTED}; }}
  .vy-cell.small {{ font-size: .8rem; color: {MUTED}; }}
  [class*="st-key-vyrows"] .stButton button {{ color: {NAVY}; font-weight: 600; padding: 0 var(--s1);
      min-height: 0; }}

  /* Drill-down figures */
  .vy-facts {{ display: grid; grid-template-columns: max-content 1fr; gap: var(--s1) var(--s5);
               font-size: .9rem; margin-top: var(--s2); }}
  .vy-facts .k {{ color: {MUTED}; }}

  /* Simple tables (cash steps, owner questions) */
  .vy-table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
  .vy-table th {{ text-align: left; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase;
                  color: {MUTED}; font-weight: 600; padding: var(--s2) var(--s2); border-bottom: 1px solid {RULE}; }}
  .vy-table td {{ padding: var(--s2) var(--s2); border-bottom: 1px solid {RULE}; vertical-align: top;
                  line-height: 1.45; color: {INK}; }}
  .vy-table td.num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .vy-table td.muted {{ color: {MUTED}; }}
  .vy-table tr.total td {{ font-weight: 600; }}
  .vy-scroll {{ overflow-x: auto; }}

  /* Export button: neutral navy outline */
  [data-testid="stDownloadButton"] button {{ background: #fff; color: {NAVY}; border: 1px solid {NAVY}; }}
  [data-testid="stDownloadButton"] button:hover {{ background: {NAVY}; color: #fff; border-color: {NAVY}; }}
  [data-testid="stDownloadButton"] button p {{ font-weight: 600; }}

  [data-testid="stPlotlyChart"] {{ margin: 0; }}
</style>
"""


# ---------- loading ----------

def data_folders():
    """Folders that build_model.py has already processed, e.g. data, data_healthy, data_stressed."""
    folders = [p.name for p in Path(".").iterdir() if (p / "model" / "monthly_summary.csv").exists()]
    return sorted(folders, key=lambda name: (name != "data", name))


def org_name(folder):
    try:
        return json.loads((Path(folder) / "raw" / "organisation.json").read_text())["Organisations"][0]["Name"]
    except (OSError, KeyError, IndexError, ValueError):
        return str(folder)


def run_scoring(folder):
    """score.compute(), with its plain-text messages captured so problems can be shown on the page."""
    messages = io.StringIO()
    try:
        with contextlib.redirect_stdout(messages):
            return score.compute(folder)
    except SystemExit:
        st.error(messages.getvalue().replace("[STOPPED]", "").strip() or "Scoring stopped.")
        st.stop()


def current_run():
    """The scored business picked in the sidebar (set by dashboard.py on every run)."""
    return st.session_state["vy_run"]


def wording():
    with contextlib.redirect_stdout(io.StringIO()):
        return score.load_wording()


# ---------- small pieces ----------

def esc(text):
    return html.escape(str(text or ""))


def md(markup):
    st.markdown(markup, unsafe_allow_html=True)


def logo():
    md("""<div class="vy-logo"><div class="mark">V</div>
          <div><div class="word">Vyta</div><div class="tag">Financial health check</div></div></div>""")


def pill(r):
    bg, fg = RATING_STYLE[rating_key(r["rating"])]
    label = r["rating"] if r["rating"] in ("Red", "Amber", "Green") else "Not assessed"
    return f'<span class="vy-pill" style="background:{bg};color:{fg}">{esc(label)}</span>'


def masthead(run, title=None):
    d = run["d"]
    sample = " · sample data" if d["org"].startswith("TEST") else ""
    md(f"""<div class="vy-eyebrow">Financial health check · {esc(d['org'])}{esc(sample)}</div>
    <div class="vy-meta">12 months to {d['months'][-1]['month']:%d %B %Y} · prepared {date.today():%d %B %Y}</div>
    {f'<h2 class="vy-title">{esc(title)}</h2>' if title else ''}""")


def heading(text, sub=None):
    md(f"<h3 class='vy-h'>{esc(text)}</h3>" + (f"<div class='vy-sub'>{esc(sub)}</div>" if sub else ""))


def chart(fig, key=None):
    """Show a Plotly figure in the Vyta style (Streamlit's own chart theme switched off)."""
    st.plotly_chart(fig, theme=None, config=CHART_CONFIG, width="stretch", key=key)
