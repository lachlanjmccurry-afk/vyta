"""
VYTA - Tests for the online demo (demo_app.py / demo.py)
---------------------------------------------------------
Run with:   py -m unittest test_demo -v

Checks the demo builds the made-up businesses from nothing (in a throw-away folder, as on Streamlit
Community Cloud), shows only those businesses, hides Refresh now, and that every page loads.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

import demo

HERE = Path(__file__).resolve().parent
PAGES = ["views/overview.py", "views/details.py", "views/get_help.py", "views/cash.py", "views/whatif.py",
         "views/history.py", "views/owner_questions.py"]


class TestDemoData(unittest.TestCase):

    def test_builds_the_test_businesses_from_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        for name in ("scorecard.json", "wording.json"):
            shutil.copy(HERE / name, tmp / name)
        try:
            os.chdir(tmp)
            demo.ensure_data()
            for folder in demo.FOLDERS:
                self.assertTrue((tmp / folder / "model" / "monthly_summary.csv").exists(), folder)
                self.assertEqual(len(list((tmp / folder / "history").glob("*.json"))), 1, folder)
            self.assertFalse((tmp / "data").exists())          # never creates or touches the real data folder
            demo.ensure_data()                                  # second call: nothing to do
            self.assertEqual(len(list((tmp / "data_healthy" / "history").glob("*.json"))), 1)
        finally:
            os.chdir(HERE)
            shutil.rmtree(tmp, ignore_errors=True)


class TestDemoApp(unittest.TestCase):

    def tearDown(self):
        os.environ.pop(demo.FLAG, None)                         # don't leave demo mode on for other tests

    def app(self, page=None):
        at = AppTest.from_file("demo_app.py", default_timeout=120)
        if page:
            at.switch_page(page)
        return at.run()

    def test_only_test_businesses_and_no_refresh(self):
        at = self.app()
        self.assertFalse(at.exception, [e.message for e in at.exception])
        self.assertEqual(list(at.selectbox(key="folder").options),
                         ["TEST - Healthy Co (synthetic)", "TEST - Stressed Co (synthetic)"])
        self.assertNotIn("refresh", [b.key for b in at.button])
        self.assertIn("Demo version", " ".join(m.value for m in at.sidebar.markdown))

    def test_every_page_loads(self):
        for page in PAGES:
            with self.subTest(page=page):
                at = self.app(page)
                self.assertFalse(at.exception, f"{page}: {[e.message for e in at.exception]}")
                self.assertFalse(at.error, f"{page}: {[e.value for e in at.error]}")


if __name__ == "__main__":
    unittest.main()
