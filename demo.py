"""
VYTA - Online demo mode
------------------------
Used by demo_app.py, the file Streamlit Community Cloud runs. In demo mode the dashboard shows only the
two made-up test businesses (data_healthy, data_stressed), hides Refresh now and never touches Xero
or the  data  folder. The test businesses aren't in GitHub (data folders are never committed), so
ensure_data() builds them the first time the demo starts: make_test_data.py, then sync.py's offline
rebuild for each (which also saves a History snapshot).
"""

import contextlib
import io
import os
import threading
from pathlib import Path

FLAG = "VYTA_DEMO"
FOLDERS = ("data_healthy", "data_stressed")
_lock = threading.Lock()


def is_demo():
    return os.environ.get(FLAG) == "1"


def ensure_data():
    """Build the test businesses if they aren't there yet. Safe if several visitors arrive at once."""
    with _lock:
        if all((Path(f) / "model" / "monthly_summary.csv").exists() for f in FOLDERS):
            return
        import make_test_data
        import sync
        with contextlib.redirect_stdout(io.StringIO()):
            make_test_data.main()
            for folder in FOLDERS:
                worked, message = sync.run(Path(folder))
                if not worked:
                    raise RuntimeError(f"Couldn't build the demo business {folder}: {message}")
