"""
VYTA - Tests that every dashboard page loads
---------------------------------------------
Run with:   py -m unittest test_dashboard -v

Uses Streamlit's built-in tester (no browser, no server, no screenshots). For every built data
folder (data, data_healthy, data_stressed) it opens every page and checks there are no errors,
then opens one indicator's Details window. Skipped if no data folders have been built.
"""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

import ui

PAGES = ["views/overview.py", "views/cash.py", "views/indicators.py", "views/owner_questions.py"]
FOLDERS = ui.data_folders()


def app(folder):
    at = AppTest.from_file("dashboard.py", default_timeout=60)
    at.session_state["folder"] = folder
    return at


class TestPagesLoad(unittest.TestCase):

    def setUp(self):
        if not FOLDERS:
            self.skipTest("No built data folders")

    def check(self, at, where):
        self.assertFalse(at.exception, f"{where}: {[e.message for e in at.exception]}")
        self.assertFalse(at.error, f"{where}: {[e.value for e in at.error]}")

    def test_every_page_for_every_business(self):
        for folder in FOLDERS:
            for page in PAGES:
                with self.subTest(folder=folder, page=page):
                    at = app(folder)
                    at.switch_page(page).run()
                    self.check(at, f"{folder} {page}")
                    self.assertEqual(at.sidebar.selectbox(key="folder").value, folder)

    def test_indicator_details_open(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                at = app(folder)
                at.switch_page("views/indicators.py").run()
                at.button(key="details-D1").click().run()
                self.check(at, f"{folder} D1 details")

    def test_cash_page_has_waterfall(self):
        at = app(FOLDERS[0])
        at.switch_page("views/cash.py").run()
        self.assertTrue(at.get("plotly_chart"))


if __name__ == "__main__":
    unittest.main()
