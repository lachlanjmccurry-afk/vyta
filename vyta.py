"""
VYTA - one command for everything
----------------------------------
Run from anywhere:   py vyta.py <command>        (or  .venv\\Scripts\\python.exe vyta.py <command>)

  dashboard                 open the dashboard in your browser (all businesses)
  demo                      open the online-demo version locally (made-up businesses only)
  refresh [folder]          update a business: Xero for businesses/xero (default), saved files for the rest
  connect                   sign in to Xero again (when the refresh says the connection has expired)
  test                      run every automated check
  benchmark                 how early Vyta warned on the closed jobs
  import                    import Xero Excel exports from businesses/Data Exports
  test-data                 rebuild the two made-up test businesses
  report [folder]           save a PDF report for a business
  logos                     remake the logo files from assets/vyta_logo.png
  run <script> [args]       run any script by name, e.g.  py vyta.py run score businesses/test_stressed

Folders: engine\\ (scoring), app\\ (dashboard), xero\\ (Xero connection), tools\\, tests\\, settings\\ (edit
these to change thresholds and wording), businesses\\ (private data), docs\\. See README.md.
"""

import runpy
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import paths  # noqa: E402

paths.setup()

SCRIPTS = {  # command -> script (module) name
    "refresh": "sync", "connect": "connect_xero", "benchmark": "benchmark", "import": "import_exports",
    "test-data": "make_test_data", "report": "report_pdf", "logos": "make_logo_assets",
}


def run_script(name, args):
    """Run a script exactly as if it had been started on its own, with the given arguments."""
    sys.argv = [name] + list(args)
    runpy.run_module(name, run_name="__main__", alter_sys=True)


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    command, args = argv[0], argv[1:]
    if command in ("dashboard", "demo"):
        app = "dashboard.py" if command == "dashboard" else "demo_app.py"
        return subprocess.call([sys.executable, "-m", "streamlit", "run", app, *args], cwd=paths.ROOT)
    if command == "test":
        suite = unittest.defaultTestLoader.discover(str(paths.ROOT / "tests"), top_level_dir=str(paths.ROOT / "tests"))
        return 0 if unittest.TextTestRunner(verbosity=1 if "-q" in args else 2).run(suite).wasSuccessful() else 1
    if command == "run":
        if not args:
            print("Say which script, e.g.  py vyta.py run score businesses/test_stressed")
            return 1
        run_script(Path(args[0]).stem, args[1:])
        return 0
    if command in SCRIPTS:
        run_script(SCRIPTS[command], args)
        return 0
    print(f"Unknown command '{command}'.\n{__doc__}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
