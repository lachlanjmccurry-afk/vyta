"""
VYTA - Shared look and helpers for the dashboard pages
-------------------------------------------------------
Palette, styling (Plus Jakarta Sans, navy sidebar, white top bar, white cards on a light grey page),
the logo, the sidebar navigation, the top bar (business picker, Last updated, Refresh now, Export PDF),
result pills, page headings and loading the scores. Used by dashboard.py and every page in views\\.
Never writes files itself: Refresh now runs sync.py in a separate process (which, for the data folder
only, reads from Xero).
"""

import base64
import contextlib
import functools
import html
import io
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import streamlit as st

import demo
import score
import snapshots
import sync
from charts import INK, MUTED, NAVY, RULE
from report_pdf import BAND_RATING, RATING_STYLE, build_pdf, rating_key

BG = "#F5F6F8"
TEAL = "#0E7C6B"          # links on white
TEAL_ON_DARK = "#5CC9AE"  # eyebrows on navy
SIDEBAR_W = 240
LOGO = Path("assets") / "vyta_logo_dark.png"
# Strong traffic-light dots (list bullets, What if? bands); pills use the paler RATING_STYLE
MARKER = {"Red": "#D92D20", "Amber": "#F79009", "Green": "#12B76A", "Not assessed": "#98A2B3"}
# Pale segments of the score band bars
BAR = {"Red": "#F5C9C0", "Amber": "#F8E3B6", "Green": "#CDEBE2", "Not assessed": "#E4E7EC"}
FONT_URL = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
CHART_CONFIG = {"displayModeBar": False, "responsive": True}

CSS = f"""
<style>
  @import url('{FONT_URL}');
  :root {{ --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 40px;
          --navy: {NAVY}; --ink: {INK}; --muted: {MUTED}; --line: {RULE}; --bg: {BG}; --teal: {TEAL};
          --sbw: {SIDEBAR_W}px; --font: 'Plus Jakarta Sans', 'Segoe UI', sans-serif; }}

  /* ---- Streamlit chrome: hide toolbar, menu, Deploy button and the default header ---- */
  [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stAppDeployButton"],
  #MainMenu {{ display: none !important; }}
  header[data-testid="stHeader"] {{ display: none; }}
  .block-container {{ max-width: 1180px; padding: calc(64px + var(--s6)) var(--s6) var(--s7); }}
  .vy-h1, .vy-panel, .vy-eyebrow, .vy-lead, .vy-li, .vy-rows, .vy-fig, .vy-firm, .vy-score {{ font-family: var(--font); }}

  /* ---- Sidebar: dark navy, fixed width, logo + page links + Xero box at the bottom ---- */
  section[data-testid="stSidebar"] {{ width: var(--sbw) !important; min-width: var(--sbw) !important;
      max-width: var(--sbw) !important; }}
  [data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
  [data-testid="stSidebarUserContent"] {{ padding: var(--s5) var(--s3) var(--s4); }}
  [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 2px; }}
  .vy-logo {{ display: block; padding: 0 var(--s2) var(--s5); }}
  .vy-logo img {{ height: 30px; width: auto; }}
  [data-testid="stSidebar"] [data-testid="stPageLink"] a {{ padding: 9px 12px; border-radius: 8px; gap: 10px;
      color: #C3CBD6; text-decoration: none; }}
  [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{ background: rgba(255,255,255,.06); }}
  [data-testid="stSidebar"] [data-testid="stPageLink"] a p,
  [data-testid="stSidebar"] [data-testid="stPageLink"] a span {{ color: inherit; font-size: .9rem; font-weight: 500; }}
  [class*="st-key-nav-on"] [data-testid="stPageLink"] a {{ background: #1C2838; color: #FFFFFF; }}
  [class*="st-key-nav-on"] [data-testid="stPageLink"] a p {{ font-weight: 600; }}
  .vy-navgroup {{ font-size: .68rem; letter-spacing: .09em; text-transform: uppercase; color: #7D8A9C;
      font-weight: 600; padding: var(--s5) 12px var(--s2); }}
  .vy-connected {{ position: fixed; bottom: var(--s4); left: var(--s3); width: calc(var(--sbw) - 2 * var(--s3));
      box-sizing: border-box; background: #1A2636; border-radius: 10px; padding: var(--s3) var(--s3);
      font-size: .76rem; line-height: 1.45; color: #AAB4C3; font-family: var(--font); }}
  .vy-connected b {{ display: block; color: #FFFFFF; font-weight: 700; margin-bottom: 2px; }}

  /* ---- Top bar: white, fixed across the top of the page area ---- */
  .st-key-vy-topbar {{ position: fixed; top: 0; left: var(--sbw); right: 0; z-index: 999;
      background: #FFFFFF; border-bottom: 1px solid var(--line); padding: 12px var(--s6); min-height: 64px;
      box-sizing: border-box; justify-content: center; }}
  .st-key-vy-topbar [data-testid="stHorizontalBlock"] {{ gap: var(--s3); }}
  .st-key-vy-topbar [data-baseweb="select"] > div {{ border-radius: 10px; background: #FFFFFF; min-height: 38px;
      font-weight: 600; font-size: .86rem; }}
  .vy-badge {{ width: 34px; height: 34px; border-radius: 8px; background: #E3F4EF; color: {TEAL};
      font-weight: 700; font-size: .78rem; display: flex; align-items: center; justify-content: center;
      font-family: var(--font); }}
  .vy-period {{ color: var(--muted); font-size: .8rem; font-family: var(--font); white-space: nowrap; }}
  .vy-sync {{ text-align: right; font-size: .8rem; color: var(--muted); line-height: 1.35; font-family: var(--font); }}
  .vy-sync .dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #12B76A;
      margin-right: 6px; vertical-align: 1px; }}
  .vy-sync small {{ display: block; font-size: .72rem; }}
  .vy-link {{ color: var(--teal) !important; font-weight: 600; font-size: .85rem; text-decoration: none;
      font-family: var(--font); white-space: nowrap; }}
  .vy-link:hover {{ text-decoration: underline; }}
  @media (max-width: 768px) {{
    header[data-testid="stHeader"] {{ display: block; }}
    .st-key-vy-topbar {{ position: static; padding: var(--s3); border: 1px solid var(--line); border-radius: 12px; }}
    .block-container {{ padding-top: var(--s7); padding-left: var(--s4); padding-right: var(--s4); }}
    .vy-connected {{ position: static; width: auto; margin-top: var(--s5); }}
    .vy-sync {{ text-align: left; }}
  }}

  /* ---- Buttons ---- */
  .stButton button, [data-testid="stDownloadButton"] button {{ border-radius: 10px; font-weight: 600;
      min-height: 38px; }}
  [data-testid="stBaseButton-secondary"] {{ background: #FFFFFF; border: 1px solid var(--line); color: var(--ink); }}
  [data-testid="stBaseButton-secondary"]:hover {{ border-color: var(--navy); color: var(--navy); }}
  [data-testid="stBaseButton-primary"] {{ background: var(--navy); border-color: var(--navy); color: #FFFFFF; }}
  [data-testid="stBaseButton-primary"]:hover {{ background: #22314A; border-color: #22314A; }}
  .stButton button p, [data-testid="stDownloadButton"] button p {{ font-weight: 600; font-size: .86rem; }}

  /* Segmented control (Details tabs): grey track, white selected chip */
  [data-testid="stButtonGroup"]:has([data-testid^="stBaseButton-segmented_control"]) > div {{ background: #F2F4F7;
      border-radius: 10px; padding: 4px; gap: 2px; display: inline-flex; width: auto; }}
  [data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"] {{
      border: none !important; border-radius: 8px !important; background: transparent; color: var(--muted);
      min-height: 32px; padding: 4px 14px; box-shadow: none; }}
  [data-testid="stBaseButton-segmented_controlActive"] {{ background: #FFFFFF !important; color: var(--ink) !important;
      box-shadow: 0 1px 2px rgba(16,24,40,.12) !important; }}
  [data-testid^="stBaseButton-segmented_control"] p {{ font-weight: 600; font-size: .82rem; }}
  /* Pills (Get help filters): white chips, navy when selected */
  [data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {{ border-radius: 999px !important;
      border: 1px solid var(--line) !important; background: #FFFFFF; color: var(--ink); padding: 6px 14px; min-height: 34px; }}
  [data-testid="stBaseButton-pillsActive"] {{ background: var(--navy) !important; border-color: var(--navy) !important;
      color: #FFFFFF !important; }}
  [data-testid^="stBaseButton-pills"] p {{ font-weight: 600; font-size: .82rem; }}

  /* ---- Page heading ---- */
  .vy-eyebrow {{ font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--muted);
      font-weight: 600; }}
  .vy-h1 {{ font-size: 2rem; line-height: 1.25; font-weight: 700; color: var(--ink); letter-spacing: -.015em;
      margin: var(--s2) 0 var(--s2); max-width: 780px; }}
  .vy-lead {{ color: var(--muted); font-size: .92rem; line-height: 1.55; max-width: 640px; margin-bottom: var(--s5); }}
  h3.vy-h {{ font-family: var(--font); font-weight: 700; font-size: 1.05rem; color: var(--ink);
      margin: var(--s6) 0 var(--s1); padding: 0; }}
  .vy-sub {{ color: var(--muted); font-size: .88rem; margin: var(--s1) 0 var(--s3); line-height: 1.5; }}
  .vy-foot {{ color: var(--muted); font-size: .74rem; margin-top: var(--s6); line-height: 1.5; }}

  /* ---- Cards ---- */
  .vy-panel, [class*="st-key-card-"] {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px;
      padding: 20px 24px; box-sizing: border-box; }}
  [class*="st-key-card-"] {{ gap: var(--s3); }}
  .vy-banner {{ display: flex; gap: 10px; align-items: flex-start; border-radius: 12px; padding: 12px var(--s4);
      font-size: .86rem; line-height: 1.5; margin: var(--s2) 0 var(--s4); font-family: var(--font); }}
  .vy-banner .i {{ flex: none; width: 16px; height: 16px; border-radius: 50%; border: 1.6px solid currentColor;
      font-size: .66rem; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 2px; }}
  .vy-banner.Low, .vy-banner.Medium {{ background: #FFF8EB; border: 1px solid #F6DDAE; color: #7A4B00; }}
  .vy-banner.High {{ background: #EEF8F4; border: 1px solid #CDEBE2; color: #075E4F; }}

  /* Score cards */
  .vy-score .top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: var(--s3); }}
  .vy-score .q {{ font-weight: 600; font-size: .95rem; color: var(--ink); }}
  .vy-score .s {{ font-size: .78rem; color: var(--muted); margin-top: 2px; }}
  .vy-score .big {{ font-size: 3rem; font-weight: 700; color: var(--ink); line-height: 1; margin: var(--s5) 0 var(--s4);
      letter-spacing: -.02em; }}
  .vy-score .big span {{ font-size: 1rem; font-weight: 500; color: var(--muted); margin-left: 6px; letter-spacing: 0; }}
  .vy-bar {{ position: relative; display: flex; gap: 3px; height: 6px; }}
  .vy-bar b {{ display: block; height: 6px; border-radius: 3px; }}
  .vy-bar i {{ position: absolute; top: -5px; width: 3px; height: 16px; margin-left: -1.5px; background: var(--ink);
      border-radius: 2px; }}
  .vy-ticks {{ display: flex; gap: 3px; font-size: .74rem; color: var(--muted); margin-top: 8px; }}
  .vy-ticks span {{ text-align: center; }}
  .vy-ticks span:first-child {{ text-align: left; }}
  .vy-ticks span:last-child {{ text-align: right; }}

  /* Pathway banner (navy) */
  .st-key-vy-pathway {{ background: var(--navy); border-radius: 14px; padding: 24px 28px; margin: var(--s4) 0; }}
  .vy-path .e {{ color: {TEAL_ON_DARK}; font-size: .7rem; letter-spacing: .09em; text-transform: uppercase; font-weight: 700; }}
  .vy-path .t {{ color: #FFFFFF; font-size: 1.3rem; font-weight: 700; margin: 6px 0 6px; font-family: var(--font); }}
  .vy-path .x {{ color: #C3CBD6; font-size: .88rem; line-height: 1.55; max-width: 560px; font-family: var(--font); }}
  .vy-path .o {{ color: #8D99AB; font-size: .76rem; margin-top: var(--s2); }}
  .st-key-vy-pathway [data-testid="stPageLink"] a {{ background: #FFFFFF; border-radius: 10px; padding: 10px 18px;
      justify-content: center; text-decoration: none; }}
  .st-key-vy-pathway [data-testid="stPageLink"] a p {{ color: var(--navy); font-weight: 700; font-size: .86rem; }}

  /* Lists in cards (top issues, what's working) */
  .vy-cardhead {{ font-weight: 700; font-size: 1rem; color: var(--ink); font-family: var(--font); }}
  [class*="st-key-card-"] [data-testid="stPageLink"] a {{ justify-content: flex-end; padding: 0; text-decoration: none; }}
  [class*="st-key-card-"] [data-testid="stPageLink"] a p {{ color: var(--teal); font-weight: 600; font-size: .82rem; }}
  .vy-li {{ display: grid; grid-template-columns: 14px 1fr; gap: 0 10px; padding: 14px 0; border-top: 1px solid var(--line); }}
  .vy-li:first-child {{ border-top: none; padding-top: 4px; }}
  .vy-li .d {{ width: 7px; height: 7px; border-radius: 50%; margin-top: 7px; }}
  .vy-li .t {{ font-weight: 600; font-size: .9rem; color: var(--ink); }}
  .vy-li .v {{ font-weight: 500; color: var(--muted); }}
  .vy-li .x {{ font-size: .84rem; color: var(--muted); line-height: 1.5; margin-top: 2px; }}

  /* ---- Details: key figures and indicator rows ---- */
  .vy-figs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: var(--s3);
      margin-bottom: var(--s4); }}
  .vy-fig {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; padding: 16px 20px; }}
  .vy-fig .l {{ font-size: .78rem; color: var(--muted); }}
  .vy-fig .n {{ font-size: 1.55rem; font-weight: 700; color: var(--ink); margin-top: 6px; letter-spacing: -.01em; }}
  .vy-fig .n.neg {{ color: #B42318; }}
  .vy-q {{ text-align: right; color: var(--muted); font-size: .82rem; padding-top: 10px; }}
  .vy-scroll {{ overflow-x: auto; }}
  .vy-rows {{ min-width: 680px; }}
  .vy-rowhead, .vy-row > summary {{ display: grid; grid-template-columns: 56px minmax(150px, 1.6fr) minmax(90px, 1fr)
      minmax(150px, 1.35fr) 112px 20px; align-items: center; gap: var(--s3); padding: 11px var(--s4); }}
  .vy-rowhead {{ background: #F9FAFB; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
      font-size: .7rem; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); font-weight: 600;
      padding-top: 9px; padding-bottom: 9px; }}
  .vy-row {{ border-bottom: 1px solid var(--line); }}
  .vy-row > summary {{ list-style: none; cursor: pointer; font-size: .88rem; color: var(--ink); }}
  .vy-row > summary::-webkit-details-marker {{ display: none; }}
  .vy-row > summary:hover, .vy-row[open] {{ background: #F9FAFB; }}
  .vy-row .id {{ color: var(--muted); font-size: .8rem; }}
  .vy-row .nm {{ font-weight: 600; }}
  .vy-row .val {{ font-weight: 500; }}
  .vy-row .lv {{ color: var(--muted); font-size: .76rem; }}
  .vy-row .chev {{ width: 7px; height: 7px; border-right: 1.6px solid var(--muted); border-bottom: 1.6px solid var(--muted);
      transform: rotate(45deg); margin-top: -4px; transition: transform .15s; }}
  .vy-row[open] .chev {{ transform: rotate(-135deg); margin-top: 4px; }}
  .vy-row .body {{ padding: 0 var(--s4) var(--s4) calc(56px + var(--s4) + var(--s3)); font-size: .86rem;
      line-height: 1.6; color: #344054; }}
  .vy-row .body .meta {{ display: flex; flex-wrap: wrap; gap: var(--s5); margin-top: var(--s3); align-items: flex-start; }}
  .vy-row .body .k {{ font-size: .7rem; letter-spacing: .07em; text-transform: uppercase; color: var(--muted);
      font-weight: 600; margin-bottom: 4px; }}
  .vy-facts {{ display: grid; grid-template-columns: max-content 1fr; gap: 2px var(--s4); font-size: .8rem; }}
  .vy-facts .f {{ color: var(--muted); }}
  .vy-row .body .how {{ color: var(--muted); font-size: .78rem; margin-top: var(--s3); }}

  /* ---- Get help ---- */
  .vy-yourpath {{ display: inline-flex; align-items: center; gap: 10px; background: #FFFFFF; border: 1px solid var(--line);
      border-radius: 12px; padding: 8px 10px 8px 14px; font-size: .78rem; color: var(--muted); float: right;
      font-family: var(--font); }}
  .vy-yourpath b {{ background: var(--navy); color: #FFFFFF; border-radius: 8px; padding: 4px 10px; font-size: .76rem; }}
  .vy-firm .head {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .vy-firm .av {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: .85rem; }}
  .vy-firm .tag {{ font-size: .62rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 700; color: var(--muted);
      border: 1px solid var(--line); border-radius: 6px; padding: 3px 7px; }}
  .vy-firm .nm {{ font-weight: 700; font-size: 1rem; color: var(--ink); margin-top: var(--s4); }}
  .vy-firm .ty {{ font-size: .82rem; color: var(--muted); margin-top: 2px; }}
  .vy-firm .badge {{ font-size: .8rem; color: var(--teal); font-weight: 600; margin-top: var(--s3); }}
  .vy-firm .p {{ font-size: .82rem; color: var(--muted); line-height: 1.5; margin-top: var(--s3); }}
  .vy-firm .p b {{ color: #344054; font-weight: 600; }}
  .vy-firm .why {{ background: #F5F6F8; border-radius: 10px; padding: 10px 12px; font-size: .8rem; color: #344054;
      line-height: 1.45; margin-top: var(--s3); }}
  .vy-firm .why b {{ font-weight: 700; color: var(--ink); }}
  .st-key-vy-adviser {{ background: var(--navy); border-radius: 14px; padding: 20px 24px; height: 100%; }}
  .vy-adv .t {{ color: #FFFFFF; font-weight: 700; font-size: 1rem; font-family: var(--font); }}
  .vy-adv .x {{ color: #C3CBD6; font-size: .84rem; line-height: 1.5; margin-top: 6px; font-family: var(--font); }}
  .st-key-vy-adviser [data-testid="stBaseButton-secondary"] {{ border-color: #FFFFFF; }}
  .vy-how {{ display: grid; grid-template-columns: 22px 1fr; gap: 0 12px; }}
  .vy-how .t {{ font-weight: 700; font-size: 1rem; color: var(--ink); }}
  .vy-how .x {{ font-size: .84rem; color: var(--muted); line-height: 1.5; margin-top: 6px; }}

  /* ---- Pills, tables and bits shared with the other pages ---- */
  .vy-pill {{ display: inline-block; border-radius: 6px; padding: 2px 9px; font-size: .74rem; font-weight: 600;
      white-space: nowrap; font-family: var(--font); }}
  .vy-card {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px; padding: var(--s4) var(--s5); }}
  .vy-card .label {{ font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }}
  .vy-card .num {{ font-size: 2.6rem; font-weight: 700; line-height: 1.05; color: var(--ink); margin-top: var(--s2); }}
  .vy-card .num span {{ font-size: 1rem; font-weight: 500; color: var(--muted); }}
  .vy-card .band {{ font-size: .95rem; font-weight: 600; color: var(--ink); margin-top: var(--s1); }}
  .vy-card .hint {{ font-size: .78rem; color: var(--muted); margin-top: var(--s2); }}
  .vy-card .num span.arrow, .arrow {{ color: var(--muted); font-size: inherit; margin: 0 var(--s2); }}
  .vy-dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: var(--s2); vertical-align: 1px; }}
  .vy-conf {{ margin: var(--s4) 0 0; padding: var(--s3) var(--s4); background: #FFFFFF; border: 1px solid var(--line);
      border-radius: 12px; font-size: .9rem; color: var(--ink); }}
  .vy-verdict {{ font-size: 1.5rem; line-height: 1.3; color: var(--ink); font-weight: 700; margin: var(--s4) 0 var(--s5); }}
  .vy-item {{ display: grid; grid-template-columns: 36px 1fr; gap: 0 var(--s3); padding: var(--s3) 0; border-bottom: 1px solid var(--line); }}
  .vy-item:last-child {{ border-bottom: none; }}
  .vy-item .n {{ font-weight: 700; color: var(--muted); font-size: .85rem; line-height: 1.6; }}
  .vy-item .t {{ font-weight: 600; color: var(--ink); }}
  .vy-item .x {{ color: var(--ink); margin-top: var(--s1); line-height: 1.5; }}
  .vy-item .v {{ color: var(--muted); font-size: .85rem; margin-left: var(--s2); }}
  .vy-note {{ color: var(--muted); font-size: .8rem; margin-top: var(--s3); line-height: 1.5; }}
  .vy-cell {{ font-size: .9rem; color: var(--ink); line-height: 1.3; }}
  .vy-table {{ width: 100%; border-collapse: collapse; font-size: .88rem; background: #FFFFFF; border-radius: 12px; }}
  .vy-table th {{ text-align: left; font-size: .7rem; letter-spacing: .07em; text-transform: uppercase; color: var(--muted);
      font-weight: 600; padding: var(--s2) var(--s3); border-bottom: 1px solid var(--line); background: #F9FAFB; }}
  .vy-table td {{ padding: var(--s2) var(--s3); border-bottom: 1px solid var(--line); vertical-align: top; line-height: 1.45; color: var(--ink); }}
  .vy-table td.num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .vy-table td.muted {{ color: var(--muted); }}
  .vy-table tr.total td {{ font-weight: 600; }}
  [data-testid="stPlotlyChart"] {{ margin: 0; }}
</style>
"""


# ---------- loading ----------

def data_folders():
    """Folders that build_model.py has already processed, e.g. data, data_healthy, data_stressed."""
    folders = [p.name for p in Path(".").iterdir() if (p / "model" / "monthly_summary.csv").exists()]
    if demo.is_demo():                          # online demo: only the made-up test businesses
        folders = [f for f in folders if f in demo.FOLDERS]
    return sorted(folders, key=lambda name: (name != "data", name))


def org_name(folder):
    try:
        return json.loads((Path(folder) / "raw" / "organisation.json").read_text())["Organisations"][0]["Name"]
    except (OSError, KeyError, IndexError, ValueError):
        return str(folder)


def initials(name):
    """'Demo Company (AU)' -> 'DC'."""
    words = [w for w in re.split(r"[^A-Za-z]+", name) if w]
    return "".join(w[0] for w in words[:2]).upper() or "?"


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
    """The scored business picked in the top bar (set by dashboard.py on every run)."""
    return st.session_state["vy_run"]


def wording():
    with contextlib.redirect_stdout(io.StringIO()):
        return score.load_wording()


def is_xero(folder):
    return Path(folder).name == sync.XERO_FOLDER


# ---------- small pieces ----------

def esc(text):
    return html.escape(str(text or ""))


def md(markup):
    st.markdown(markup, unsafe_allow_html=True)


def pill(r):
    """Result pill for an indicator result (anything with a 'rating')."""
    key = rating_key(r["rating"])
    bg, fg = RATING_STYLE[key]
    return f'<span class="vy-pill" style="background:{bg};color:{fg}">{esc(key)}</span>'


def band_pill(band):
    bg, fg = RATING_STYLE[BAND_RATING.get(band, "Not assessed")]
    return f'<span class="vy-pill" style="background:{bg};color:{fg}">{esc(band)}</span>'


def first_sentence(text):
    """The first sentence of an explanation (the full text is on the Details page)."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", (text or "").strip(), maxsplit=1)
    return parts[0]


def page_head(eyebrow, title, lead=None):
    md(f"<div class='vy-eyebrow'>{esc(eyebrow)}</div><div class='vy-h1' role='heading' aria-level='1'>{esc(title)}</div>"
       + (f"<div class='vy-lead'>{esc(lead)}</div>" if lead else ""))


def heading(text, sub=None):
    md(f"<h3 class='vy-h'>{esc(text)}</h3>" + (f"<div class='vy-sub'>{esc(sub)}</div>" if sub else ""))


def chart(fig, key=None):
    """Show a Plotly figure in the Vyta style (Streamlit's own chart theme switched off)."""
    st.plotly_chart(fig, theme=None, config=CHART_CONFIG, width="stretch", key=key)


# ---------- sidebar ----------

@functools.lru_cache(maxsize=1)
def logo_src():
    try:
        return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    except OSError:
        return None


def sidebar(main_pages, more_pages, current, folder):
    """Logo, the page links (the current one highlighted) and the 'Connected to Xero' box."""
    text = wording().get("shell", {})
    with st.sidebar:
        src = logo_src()
        md(f"<div class='vy-logo'><img src='{src}' alt='Vyta'></div>" if src
           else "<div class='vy-logo' style='color:#fff;font-weight:800;font-size:1.4rem'>vyta</div>")
        for group, pages in ((None, main_pages), (text.get("more", "More tools"), more_pages)):
            if group:
                md(f"<div class='vy-navgroup'>{esc(group)}</div>")
            for p in pages:
                state = "on" if p.url_path == current.url_path else "off"
                with st.container(key=f"nav-{state}-{p.url_path or 'home'}"):
                    st.page_link(p, label=p.title, icon=p.icon)
        if demo.is_demo():
            title, body = text.get("demo_title"), text.get("demo_text")
        elif is_xero(folder):
            title, body = text.get("connected_title"), text.get("connected_text")
        else:
            title, body = text.get("sample_title"), text.get("sample_text")
        md(f"<div class='vy-connected'><b>{esc(title)}</b>{esc(body)}</div>")


# ---------- top bar ----------

def topbar():
    """The white bar across the top. Returns its columns: badge, picker, period, sync status, two buttons."""
    with st.container(key="vy-topbar"):
        return st.columns([0.45, 2.4, 2.0, 3.0, 1.45, 1.45], vertical_alignment="center", gap="small")


def fill_topbar(cols, run, folder, on_help_page):
    text = wording().get("shell", {})
    d = run["d"]
    with cols[0]:
        md(f"<div class='vy-badge'>{esc(initials(d['org']))}</div>")
    with cols[2]:
        end = d["months"][-1]["month"]
        md(f"<div class='vy-period'>{esc(text.get('period', '12 months to {end}').format(end=f'{end.day} {end:%b %Y}'))}</div>")
    with cols[3]:
        status = text.get("synced_xero" if is_xero(folder) else "synced_sample", "")
        md(f"<div class='vy-sync'><span class='dot'></span>{esc(status)}<small>{esc(last_updated_text(folder))}</small></div>")
    with cols[4]:
        if not demo.is_demo():                  # the online demo has nothing to refresh
            refresh_button(folder)
    with cols[5]:
        if on_help_page:
            md(f"<div style='text-align:right'><a class='vy-link' href='#get-listed' target='_self'>"
               f"{esc(text.get('get_listed', 'Get listed'))}</a></div>")
        else:
            slug = "".join(c if c.isalnum() else "_" for c in d["org"]).strip("_").lower()
            st.download_button(text.get("export", "Export PDF"), data=build_pdf(run), width="stretch",
                               file_name=f"vyta_report_{slug}_{date.today():%Y-%m-%d}.pdf", mime="application/pdf",
                               on_click="ignore", key="export")


# ---------- refreshing ----------

def last_updated_text(folder):
    text = wording().get("refresh", {})
    when = snapshots.when_text(snapshots.last_updated(folder))
    return f"{text.get('last_updated', 'Last updated')} {when}" if when else text.get("never", "Not refreshed yet")


def refresh(folder):
    """Run sync.py for one folder in its own process (so a crash can't take the dashboard down).
    Returns (worked, plain-English message)."""
    try:
        done = subprocess.run([sys.executable, "sync.py", str(folder)], cwd=sync.HERE, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=900,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        return False, "The refresh took more than 15 minutes and was stopped. Your existing data has been kept."
    ends = [l for l in done.stdout.splitlines() if l.startswith(("[DONE]", "[STOPPED]"))]
    message = ends[-1] if ends else f"The refresh stopped unexpectedly. See {Path(folder) / sync.LOG}."
    return done.returncode == 0, message.replace("[DONE]", "").replace("[STOPPED]", "").strip()


def refresh_button(folder):
    text = wording().get("refresh", {})
    help_text = text.get("help_xero" if is_xero(folder) else "help_offline")
    if st.button(text.get("button", "Refresh now"), key="refresh", help=help_text, width="stretch",
                 icon=":material/refresh:"):
        with st.spinner(text.get("running", "Refreshing...")):
            st.session_state["vy_flash"] = refresh(folder)
        st.rerun()


def show_flash():
    """The result of the last Refresh now, shown once at the top of the page."""
    flash = st.session_state.pop("vy_flash", None)
    if flash:
        (st.success if flash[0] else st.error)(flash[1])
