"""
VYTA - Where everything lives
------------------------------
One place for every folder and settings file, so the code never hard-codes a location.
Paths are relative to the vyta folder: vyta.py, dashboard.py and demo_app.py always start there.

  settings\\     scorecard.json (thresholds, weights), wording.json (all text), firms.json (adviser listings)
  businesses\\   one folder per business (private, never uploaded to GitHub):
                  xero\\           the live Xero business (pull_data.py / sync.py)
                  test_healthy\\   test_stressed\\    made-up test businesses (make_test_data.py, online demo)
                  business_a\\ ... real figures imported from Excel (import_exports.py), anonymised
                  Data Exports\\   drop Xero Excel exports here for import_exports.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_FOLDERS = ("engine", "app", "xero", "tools")

SETTINGS = Path("settings")
SCORECARD = SETTINGS / "scorecard.json"
WORDING = SETTINGS / "wording.json"
FIRMS = SETTINGS / "firms.json"

BUSINESSES = Path("businesses")
XERO = BUSINESSES / "xero"
TEST_HEALTHY = BUSINESSES / "test_healthy"
TEST_STRESSED = BUSINESSES / "test_stressed"
EXPORTS = BUSINESSES / "Data Exports"


def imported(letter):
    """Folder for an imported business, e.g. imported("A") -> businesses/business_a."""
    return BUSINESSES / f"business_{letter.lower()}"


def same(a, b):
    """True if two folder paths point at the same place (however they were written)."""
    return Path(a).resolve() == Path(b).resolve()


def setup():
    """Make every code folder importable by plain name and work from the vyta folder."""
    for folder in reversed(CODE_FOLDERS):
        path = str(ROOT / folder)
        if path not in sys.path:
            sys.path.insert(0, path)
    os.chdir(ROOT)
