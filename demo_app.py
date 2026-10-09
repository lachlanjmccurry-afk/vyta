"""
VYTA - Online demo (for Streamlit Community Cloud)
---------------------------------------------------
On share.streamlit.io, deploy this repo with  Main file path: demo_app.py.
Try it locally with:   py -m streamlit run demo_app.py

Runs the normal dashboard (dashboard.py) in demo mode: only the two made-up test businesses, no
Refresh now, never contacts Xero. See demo.py.
"""

import os
import runpy

import demo

os.environ[demo.FLAG] = "1"
demo.ensure_data()
runpy.run_path("dashboard.py", run_name="__main__")
