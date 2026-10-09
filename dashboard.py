"""
VYTA - Dashboard
-----------------
Run with:   py -m streamlit run dashboard.py
            (or, with the .venv not activated:  .venv\\Scripts\\python.exe -m streamlit run dashboard.py)

Opens in your web browser (http://localhost:8501). It runs only on this computer.
Pick a client in the left sidebar and a page in the bar along the top. Close the terminal window
(or press Ctrl+C) to stop it.

Pages (in views\\):
  Overview         - the adviser's memo: verdict, the two scores, top issues, pathway, PDF export
  Cash             - "Where has the cash gone?" waterfall (worked out in cashflow.py)
  Indicators       - every indicator with a 12-month sparkline; Details opens the full trend chart
  What if?         - sliders for price, revenue, costs, overhead, debtor collection and an ATO plan;
                     both scores re-worked live by whatif.py (scored by score.score_data)
  Owner questions  - the questions only the owner can answer, and what they feed into

This file sets up the shared look, the logo and the client picker, scores the chosen client once,
then shows the chosen page. Shared pieces are in ui.py, charts in charts.py.

Read-only: it reads the files already made by build_model.py and never contacts Xero.
All wording comes from wording.json and scorecard.json; colours and theme are in .streamlit\\config.toml.
"""

import streamlit as st

import ui

st.set_page_config(page_title="Vyta", layout="wide", menu_items={})
st.markdown(ui.CSS, unsafe_allow_html=True)

folders = ui.data_folders()
if not folders:
    st.error("No scored data found yet.")
    st.stop()

with st.sidebar:
    ui.logo()
    folder = st.selectbox("Client", folders, format_func=ui.org_name, key="folder")

st.session_state["vy_run"] = ui.run_scoring(folder)

page = st.navigation([
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/cash.py", title="Cash"),
    st.Page("views/indicators.py", title="Indicators"),
    st.Page("views/whatif.py", title="What if?"),
    st.Page("views/owner_questions.py", title="Owner questions"),
], position="top")
page.run()
