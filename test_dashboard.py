"""
VYTA - Tests that every dashboard page loads
---------------------------------------------
Run with:   py -m unittest test_dashboard -v

Uses Streamlit's built-in tester (no browser, no server, no screenshots). For every built data
folder (data, data_healthy, data_stressed) it opens every page and checks there are no errors,
then opens one indicator's Details window. Skipped if no data folders have been built.
"""

import unittest
from datetime import datetime
from unittest import mock

from streamlit.testing.v1 import AppTest

import ui

PAGES = ["views/overview.py", "views/cash.py", "views/indicators.py", "views/whatif.py",
         "views/history.py", "views/owner_questions.py"]
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

    def test_whatif_sliders_recalculate(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                at = app(folder)
                at.switch_page("views/whatif.py").run()
                at.slider(key="wi_overhead").set_value(20).run()
                at.slider(key="wi_debtor_days").set_value(30).run()
                at.toggle(key="wi_ato_plan").set_value(True).run()
                self.check(at, f"{folder} what if")
                text = " ".join(m.value for m in at.markdown)
                self.assertIn("Cutting overhead by 20%, collecting debtors 30 days faster and putting the ATO", text)
                at.button[0].click().run()            # Reset
                self.assertEqual(at.slider(key="wi_overhead").value, 0)

    def test_cash_page_has_waterfall(self):
        at = app(FOLDERS[0])
        at.switch_page("views/cash.py").run()
        self.assertTrue(at.get("plotly_chart"))

    def test_every_page_shows_last_updated(self):
        fake = [snap(datetime(2026, 10, 9, 7, 2), {"D1": "Green"})]
        with mock.patch("snapshots.load", return_value=fake):
            for page in PAGES:
                with self.subTest(page=page):
                    at = app(FOLDERS[0])
                    at.switch_page(page).run()
                    page_text = " ".join(m.value for m in at.main.markdown)
                    self.assertIn("Last updated 9 Oct 2026, 7:02am", page_text)

    def test_history_lists_colour_changes(self):
        fake = [snap(datetime(2026, 10, 8, 7, 0), {"D1": "Green", "D2": "Amber"}, 40.0),
                snap(datetime(2026, 10, 9, 7, 0), {"D1": "Green", "D2": "Red"}, 65.0)]
        with mock.patch("snapshots.load", return_value=fake):
            at = app(FOLDERS[0])
            at.switch_page("views/history.py").run()
            self.check(at, "history")
            text = " ".join(m.value for m in at.markdown)
            self.assertIn("What changed since last time", text)
            self.assertIn("D2", text)
            self.assertIn("65.0 (High)", text)
            self.assertNotIn(">D1<", text)                    # unchanged indicators aren't listed
            self.assertEqual(len(at.get("plotly_chart")), 2)  # one chart per score

    def test_refresh_now_button(self):
        for worked, element in ((True, "success"), (False, "error")):
            with self.subTest(worked=worked), \
                    mock.patch("ui.refresh", return_value=(worked, "TEST message")) as refresh:
                at = app(FOLDERS[0])
                at.run()
                at.sidebar.button(key="refresh").click().run()
                refresh.assert_called_once_with(FOLDERS[0])
                self.assertEqual([e.value for e in getattr(at.sidebar, element)], ["TEST message"])


def snap(when, ratings, distress=50.0):
    return {"taken_at": when.isoformat(), "_taken": when, "pathway": "TEST", "confidence": "High",
            "distress": {"score": distress, "band": "High" if distress >= 60 else "Moderate"},
            "viability": {"score": 70.0, "band": "Strong"},
            "indicators": [{"id": i, "name": i, "score": "distress", "rating": r, "display": "x"}
                           for i, r in ratings.items()]}


if __name__ == "__main__":
    unittest.main()
