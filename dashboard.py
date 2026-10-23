"""
VYTA - Dashboard
-----------------
Run with:   py -m streamlit run dashboard.py
            (or, with the .venv not activated:  .venv\\Scripts\\python.exe -m streamlit run dashboard.py)

Opens in your web browser (http://localhost:8501). It runs only on this computer.
Pick a business in the white bar along the top and a page in the navy sidebar. Close the terminal window
(or press Ctrl+C) to stop it.

Pages (in views\\):
  Overview         - verdict, data confidence, the two scores with their bands, the recommended pathway,
                     top 3 issues and what's working
  Details          - key balances, then every indicator (Distress / Viability tabs); click a row for the
                     explanation, 12-month trend and figures used
  Get help         - advisers from firms.json (fictional demo listings) matched to the pathway
  More tools:
  Cash             - "Where has the cash gone?" waterfall (worked out in cashflow.py)
  What if?         - sliders that re-score the business live (whatif.py)
  History          - both scores across the saved snapshots, and which indicators changed colour
  Owner questions  - the questions only the owner can answer, and what they feed into

This file draws the sidebar and the top bar (business picker, Last updated, Refresh now, Export PDF),
scores the chosen business once, then shows the chosen page. Shared pieces are in ui.py, charts in charts.py.

The pages only read the files made by build_model.py and sync.py. Refresh now runs sync.py, which
(for the data folder only) reads from Xero - never writes to it.
All wording comes from wording.json, scorecard.json and firms.json; the theme is in .streamlit\\config.toml.
The online demo (demo_app.py) runs this same file in demo mode: test businesses only, no Refresh now.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import paths  # noqa: E402  (sets up the code folders and works from the vyta folder)

paths.setup()

import streamlit as st  # noqa: E402

import ui  # noqa: E402

st.set_page_config(page_title="Vyta", page_icon="assets/vyta_mark.png", layout="wide",
                   initial_sidebar_state="expanded", menu_items={})
st.markdown(ui.CSS, unsafe_allow_html=True)

folders = ui.data_folders()
if not folders:
    st.error("No scored data found yet.")
    st.stop()

MAIN = [
    st.Page("app/views/overview.py", title="Overview", icon=":material/grid_view:", default=True),
    st.Page("app/views/details.py", title="Details", icon=":material/notes:"),
    st.Page("app/views/get_help.py", title="Get help", icon=":material/group:"),
]
MORE = [
    st.Page("app/views/cash.py", title="Cash", icon=":material/payments:"),
    st.Page("app/views/whatif.py", title="What if?", icon=":material/tune:"),
    st.Page("app/views/history.py", title="History", icon=":material/history:"),
    st.Page("app/views/owner_questions.py", title="Owner questions", icon=":material/help:"),
]
page = st.navigation(MAIN + MORE, position="hidden")

bar = ui.topbar()
with bar[1]:
    folder = st.selectbox("Business", folders, format_func=ui.org_name, key="folder", label_visibility="collapsed")
st.session_state["vy_run"] = run = ui.run_scoring(folder)
ui.fill_topbar(bar, run, folder, on_help_page=page.title == "Get help")
ui.sidebar(MAIN, MORE, page, folder)
ui.show_flash()

page.run()
