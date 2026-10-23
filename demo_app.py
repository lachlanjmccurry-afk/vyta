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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import paths  # noqa: E402  (sets up the code folders and works from the vyta folder)

paths.setup()

import demo  # noqa: E402

os.environ[demo.FLAG] = "1"
demo.ensure_data()
runpy.run_path("dashboard.py", run_name="__main__")
