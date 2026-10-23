"""Imported first by every test file: makes the code folders importable and works from the vyta folder,
so the tests run the same way from  py vyta.py test  or  python -m unittest discover -s tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import paths  # noqa: E402

paths.setup()
