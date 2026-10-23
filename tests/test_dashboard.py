"""
VYTA - Tests that every dashboard page loads and behaves
---------------------------------------------------------
Run with:   py -m unittest test_dashboard -v

Uses Streamlit's built-in tester (no browser, no server, no screenshots). For every built data
folder (data, data_healthy, data_stressed) it opens every page and checks there are no errors, then
checks the Overview numbers match score.py, the Details tabs and rows, the Get help filters and
windows, What if?, History, Last updated and Refresh now. Skipped if no data folders have been built.
"""

import _setup  # noqa: F401  (code folders + work from the vyta folder)
import paths
import contextlib
import io
import unittest
from datetime import datetime
from unittest import mock

from streamlit.testing.v1 import AppTest

import firms
import score
import ui

PAGES = ["app/views/overview.py", "app/views/details.py", "app/views/get_help.py", "app/views/cash.py", "app/views/whatif.py",
         "app/views/history.py", "app/views/owner_questions.py"]
FOLDERS = ui.data_folders()


def app(folder):
    at = AppTest.from_file(str(paths.ROOT / "dashboard.py"), default_timeout=60)
    at.session_state["folder"] = folder
    return at


def scored(folder):
    with contextlib.redirect_stdout(io.StringIO()):
        return score.compute(folder)


def page_text(at):
    return " ".join(m.value for m in at.markdown)


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
                    self.assertEqual(at.selectbox(key="folder").value, folder)

    def test_sidebar_has_logo_and_xero_box(self):
        at = app(FOLDERS[0])
        at.run()
        sidebar = " ".join(m.value for m in at.sidebar.markdown)
        self.assertIn("data:image/png;base64,", sidebar)
        self.assertIn("vy-connected", sidebar)

    def test_overview_numbers_come_from_score(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                run = scored(folder)
                at = app(folder)
                at.run()
                self.check(at, folder)
                text = page_text(at)
                self.assertIn(ui.esc(run["verdict"]), text)
                self.assertIn(ui.esc(run["pathway_label"]), text)
                for kind in ("distress", "viability"):
                    value = run["scores"][kind][0]
                    if value is not None:
                        self.assertIn(f"{value:.0f}<span>/ 100</span>", text)
                    self.assertIn(ui.esc(run["bands"][kind]), text)
                for r in score.top_issues(run["results"]) + score.whats_working(run["results"]):
                    self.assertIn(ui.esc(r["ind"]["name"]), text)
                self.assertIn(f"{run['confidence']['level']} data confidence.", text)

    def test_details_tabs_and_rows(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                run = scored(folder)
                at = app(folder)
                at.switch_page("app/views/details.py").run()
                self.check(at, folder)
                for kind in ("distress", "viability"):
                    if kind == "viability":
                        at.segmented_control(key="details_kind").set_value("viability").run()
                        self.check(at, f"{folder} viability tab")
                    text = page_text(at)
                    for r in (r for r in run["results"] if r["ind"]["score"] == kind):
                        self.assertIn(f"id='row-{r['ind']['id']}'", text)
                        if r["points"] is not None:
                            self.assertIn(ui.esc(r["display"]), text)
                    other = "viability" if kind == "distress" else "distress"
                    first_other = next(r for r in run["results"] if r["ind"]["score"] == other)
                    self.assertNotIn(f"id='row-{first_other['ind']['id']}'", text)
                latest = run["d"]["months"][-1]
                self.assertIn(score.money(abs(latest["cash"])), page_text(at))

    def test_get_help_filters_and_windows(self):
        folder = FOLDERS[0]
        run = scored(folder)
        data = firms.load()
        at = app(folder)
        at.switch_page("app/views/get_help.py").run()
        self.check(at, "get help")
        text = page_text(at)
        everyone = firms.matches(run, data)
        self.assertTrue(everyone, "the demo firms should cover every pathway")
        for f in everyone:
            self.assertIn(ui.esc(f["name"]), text)
        self.assertIn("Listed partner", text)
        for kind in data["types"]:
            at.pills(key="help_filter").set_value(kind).run()
            self.check(at, f"filter {kind}")
            text = page_text(at)
            for f in data["firms"]:
                shown = ui.esc(f["name"]) in text
                expected = f["type"] == kind and any(m["id"] == f["id"] for m in everyone)
                self.assertEqual(shown, expected, f"{kind}: {f['name']}")
        at.pills(key="help_filter").set_value("all").run()
        at.button(key=f"contact-{everyone[0]['id']}").click().run()
        self.check(at, "contact window")
        self.assertIn(ui.esc(everyone[0]["phone"]), page_text(at))

    def test_whatif_sliders_recalculate(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                at = app(folder)
                at.switch_page("app/views/whatif.py").run()
                at.slider(key="wi_overhead").set_value(20).run()
                at.slider(key="wi_debtor_days").set_value(30).run()
                at.toggle(key="wi_ato_plan").set_value(True).run()
                self.check(at, f"{folder} what if")
                self.assertIn("Cutting overhead by 20%, collecting debtors 30 days faster and putting the ATO",
                              page_text(at))
                at.button(key="wi_reset").click().run()
                self.assertEqual(at.slider(key="wi_overhead").value, 0)

    def test_cash_page_has_waterfall(self):
        at = app(FOLDERS[0])
        at.switch_page("app/views/cash.py").run()
        self.assertTrue(at.get("plotly_chart"))

    def test_every_page_shows_last_updated(self):
        fake = [snap(datetime(2026, 10, 9, 7, 2), {"D1": "Green"})]
        with mock.patch("snapshots.load", return_value=fake):
            for page in PAGES:
                with self.subTest(page=page):
                    at = app(FOLDERS[0])
                    at.switch_page(page).run()
                    self.assertIn("Last updated 9 Oct 2026, 7:02am", " ".join(m.value for m in at.main.markdown))

    def test_history_lists_colour_changes(self):
        fake = [snap(datetime(2026, 10, 8, 7, 0), {"D1": "Green", "D2": "Amber"}, 40.0),
                snap(datetime(2026, 10, 9, 7, 0), {"D1": "Green", "D2": "Red"}, 65.0)]
        with mock.patch("snapshots.load", return_value=fake):
            at = app(FOLDERS[0])
            at.switch_page("app/views/history.py").run()
            self.check(at, "history")
            text = page_text(at)
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
                at.button(key="refresh").click().run()
                refresh.assert_called_once_with(FOLDERS[0])
                self.assertEqual([e.value for e in getattr(at, element)], ["TEST message"])


def snap(when, ratings, distress=50.0):
    return {"taken_at": when.isoformat(), "_taken": when, "pathway": "TEST", "confidence": "High",
            "distress": {"score": distress, "band": "High" if distress >= 60 else "Moderate"},
            "viability": {"score": 70.0, "band": "Strong"},
            "indicators": [{"id": i, "name": i, "score": "distress", "rating": r, "display": "x"}
                           for i, r in ratings.items()]}


if __name__ == "__main__":
    unittest.main()
