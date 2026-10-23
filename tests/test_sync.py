"""
VYTA - Tests for the automatic refresh (sync.py) and score history (snapshots.py)
----------------------------------------------------------------------------------
Run with:   py -m unittest test_sync -v

Works on throw-away copies of the synthetic test businesses in a temporary folder, with the Xero
pull replaced by a copy of their raw files - so it never touches  data\\  or Xero. The end-to-end
tests are skipped unless  data_healthy  and  data_stressed  have been built (py make_test_data.py).
"""

import _setup  # noqa: F401  (code folders + work from the vyta folder)
import paths
import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import score
import snapshots
import sync

HEALTHY, STRESSED = paths.TEST_HEALTHY, paths.TEST_STRESSED
BUILT = (HEALTHY / "raw").exists() and (STRESSED / "raw").exists()


def copy_from(source):
    """A fake pull: the raw files of another folder."""
    return lambda base, raw: [("Fake pull", shutil.copytree, source / "raw", raw)]


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def enabled_indicators():
    return [i["id"] for i in quiet(score.load_config)["indicators"] if i.get("enabled", True)]


@unittest.skipUnless(BUILT, "Run  py make_test_data.py  first")
class TestSync(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "client"
        shutil.copytree(HEALTHY / "raw", self.base / "raw")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def history(self):
        return sorted((self.base / snapshots.HISTORY).glob("*.json"))

    def test_refresh_builds_scores_and_saves_a_snapshot(self):
        worked, message = quiet(sync.run, self.base)
        self.assertTrue(worked, message)
        self.assertTrue(message.startswith("[DONE]"))
        for name in ("monthly_summary.csv", "vyta_model.xlsx", "vyta_score.xlsx"):
            self.assertTrue((self.base / "model" / name).exists(), name)
        self.assertEqual(len(self.history()), 1)
        snap = json.loads(self.history()[0].read_text(encoding="utf-8"))
        self.assertEqual([i["id"] for i in snap["indicators"]], enabled_indicators())
        for kind in ("distress", "viability"):
            self.assertIn("score", snap[kind])
            self.assertIn("band", snap[kind])
        self.assertEqual((snap["distress"]["band"], snap["viability"]["band"]), ("Low", "Strong"))
        # Tidied up, and logged
        self.assertFalse((self.base / sync.STAGE).exists())
        self.assertFalse((self.base / sync.LOCK).exists())
        self.assertIn("[DONE]", (self.base / sync.LOG).read_text(encoding="utf-8"))

    def test_snapshot_matches_the_scoring(self):
        quiet(sync.run, self.base)
        snap = snapshots.load(self.base)[-1]
        run = quiet(score.compute, self.base)
        self.assertEqual(snap["distress"]["score"], round(run["scores"]["distress"][0], 1))
        self.assertEqual({i["id"]: i["rating"] for i in snap["indicators"]},
                         {r["ind"]["id"]: r["rating"] for r in run["results"]})

    def test_new_data_replaces_old_and_history_shows_the_change(self):
        quiet(sync.run, self.base)
        worked, message = quiet(sync.run, self.base, fetch=copy_from(STRESSED))
        self.assertTrue(worked, message)
        self.assertEqual((self.base / "model" / "monthly_summary.csv").read_text(),
                         (STRESSED / "model" / "monthly_summary.csv").read_text())
        snaps = snapshots.load(self.base)
        self.assertEqual(len(snaps), 2)
        self.assertEqual(snaps[-1]["distress"]["band"], "High")
        changed = snapshots.changes(snaps[0], snaps[1])
        self.assertTrue(changed)
        self.assertTrue(all(c["before"] != c["after"] for c in changed))

    def test_failed_pull_keeps_existing_data(self):
        quiet(sync.run, self.base)
        before = {p: p.read_bytes() for p in self.base.glob("*/*") if p.is_file()}

        def half_pull(raw):
            shutil.copytree(STRESSED / "raw", raw)
            (raw / "summary.txt").write_text("Pulled on:    2026-10-09\n\ninvoices: FAILED\n")

        worked, message = quiet(sync.run, self.base, fetch=lambda base, raw: [("Fake pull", half_pull, raw)])
        self.assertFalse(worked)
        self.assertIn("invoices", message)
        self.assertIn("kept", message)
        after = {p: p.read_bytes() for p in self.base.glob("*/*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.base / sync.STAGE).exists())
        self.assertIn("[STOPPED]", (self.base / sync.LOG).read_text(encoding="utf-8"))

    def test_crash_in_a_step_is_reported_not_raised(self):
        def boom(raw):
            raise ConnectionError("no internet")
        worked, message = quiet(sync.run, self.base, fetch=lambda base, raw: [("Fake pull", boom, raw)])
        self.assertFalse(worked)
        self.assertIn("no internet", message)
        self.assertFalse((self.base / sync.LOCK).exists())

    def test_stopped_step_gives_its_reason(self):
        def stops(raw):
            import build_model
            build_model.stop("Run  py connect_xero.py  again.")
        worked, message = quiet(sync.run, self.base, fetch=lambda base, raw: [("Fake pull", stops, raw)])
        self.assertFalse(worked)
        self.assertIn("connect_xero.py", message)

    def test_second_refresh_waits_for_the_first(self):
        (self.base / sync.LOCK).write_text("busy")
        (self.base / sync.STAGE).mkdir()
        worked, message = quiet(sync.run, self.base)
        self.assertFalse(worked)
        self.assertIn("already running", message)
        self.assertTrue((self.base / sync.LOCK).exists())      # the other run's lock and files are left alone
        self.assertTrue((self.base / sync.STAGE).exists())

    def test_last_updated_is_the_newest_snapshot(self):
        # Before any snapshot: the 'Pulled on' date from summary.txt
        pulled = re.search(r"Pulled on:\s*(\S+)", (self.base / "raw" / "summary.txt").read_text()).group(1)
        self.assertEqual(snapshots.last_updated(self.base), date.fromisoformat(pulled))
        quiet(sync.run, self.base)
        self.assertEqual(snapshots.last_updated(self.base), snapshots.load(self.base)[-1]["_taken"])


class TestSnapshots(unittest.TestCase):

    def snap(self, ratings, when="2026-10-09T07:00:00"):
        return {"taken_at": when, "_taken": datetime.fromisoformat(when),
                "distress": {"score": 50.0, "band": "Moderate"}, "viability": {"score": None, "band": "Not enough data"},
                "indicators": [{"id": i, "name": i, "score": "distress", "rating": r, "display": "x"}
                               for i, r in ratings.items()]}

    def test_changes_lists_only_colour_changes(self):
        before = self.snap({"D1": "Green", "D2": "Amber", "D3": "Not assessed"})
        after = self.snap({"D1": "Green", "D2": "Red", "D3": "Not assessed - owner question", "D4": "Green"})
        changed = {c["id"]: (c["before"], c["after"]) for c in snapshots.changes(before, after)}
        self.assertEqual(changed, {"D2": ("Amber", "Red"), "D4": (None, "Green")})

    def test_when_text(self):
        self.assertEqual(snapshots.when_text(datetime(2026, 10, 9, 7, 2)), "9 Oct 2026, 7:02am")
        self.assertEqual(snapshots.when_text(datetime(2026, 10, 9, 13, 30)), "9 Oct 2026, 1:30pm")
        self.assertEqual(snapshots.when_text(date(2026, 10, 9)), "9 Oct 2026")
        self.assertIsNone(snapshots.when_text(None))

    def test_shown(self):
        self.assertEqual(snapshots.shown({"score": 72.04, "band": "High"}), "72.0 (High)")
        self.assertEqual(snapshots.shown({"score": None, "band": "Not enough data"}), "n/a (Not enough data)")

    def test_load_sorts_and_skips_broken_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / snapshots.HISTORY
            folder.mkdir()
            for name, when in (("b", "2026-10-09T07:00:00"), ("a", "2026-10-10T07:00:00")):
                snap = self.snap({"D1": "Green"}, when)
                del snap["_taken"]
                (folder / f"{name}.json").write_text(json.dumps(snap))
            (folder / "broken.json").write_text("{not json")
            loaded = snapshots.load(tmp)
            self.assertEqual([s["taken_at"] for s in loaded], ["2026-10-09T07:00:00", "2026-10-10T07:00:00"])
            self.assertIsNone(snapshots.last_updated(Path(tmp) / "missing"))

    def test_disconnected_business_gives_a_clear_reason(self):
        fake_tokens = {"access_token": "x", "tenant_id": "T1", "tenant_name": "TEST Co"}
        for connected, stops in (([{"tenantId": "T1"}], False), ([{"tenantId": "OTHER"}], True), ([], True)):
            reply = mock.Mock(ok=True, json=mock.Mock(return_value=connected))
            with self.subTest(connected=connected), \
                    mock.patch("pull_data.load_tokens", return_value=fake_tokens), \
                    mock.patch("requests.get", return_value=reply) as get:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    if stops:
                        self.assertRaises(SystemExit, sync.check_connection)
                    else:
                        sync.check_connection()
                self.assertEqual(get.call_args.args[0], sync.CONNECTIONS_URL)
                if stops:
                    self.assertIn("connect_xero.py", out.getvalue())

    def test_only_the_data_folder_uses_xero(self):
        self.assertIs(sync.default_fetch(paths.XERO), sync.xero_steps)
        self.assertIs(sync.default_fetch(paths.TEST_HEALTHY), sync.copy_steps)
        self.assertIs(sync.default_fetch(Path("somewhere") / "client"), sync.copy_steps)


if __name__ == "__main__":
    unittest.main()
