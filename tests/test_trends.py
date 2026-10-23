"""
VYTA - Tests for indicator trends (trends.py)
----------------------------------------------
Run with:   py -m unittest test_trends -v

The key check: the latest point of every trend equals the value the scoring engine used,
so the sparklines can never disagree with the scores. The real-business checks are skipped
unless data, data_healthy and data_stressed have been built.
"""

import _setup  # noqa: F401  (code folders + work from the vyta folder)
import paths
import contextlib
import io
import unittest
from pathlib import Path

import score
import trends
from test_score import CFG, IND, business, series


def scored(folder):
    with contextlib.redirect_stdout(io.StringIO()):
        return score.compute(folder)


class TestSeries(unittest.TestCase):

    def test_twelve_points_oldest_first(self):
        d = business(series(24))
        s = trends.indicator_series(d, IND["D1"])
        self.assertEqual(len(s["points"]), 12)
        self.assertEqual(s["points"][-1][0], d["months"][-1]["month"])
        self.assertLess(s["points"][0][0], s["points"][-1][0])

    def test_follows_the_data(self):
        cash = [1000 * (i + 1) for i in range(12)]
        s = trends.indicator_series(business(series(12, cash=cash, debtors=0, current_liabilities=1000)),
                                    IND["D2"])
        self.assertEqual([v for _, v in s["points"]], [c / 1000 for c in cash])

    def test_snapshot_indicators_have_no_trend(self):
        for ind_id in trends.NO_TREND:
            s = trends.indicator_series(business(series(12)), IND[ind_id])
            self.assertEqual(s["points"], [])
            self.assertTrue(s["reason"])

    def test_rule_based_months_are_gaps(self):
        liab = [0] * 6 + [5000] * 6        # "No debts due" for the first 6 months
        s = trends.indicator_series(business(series(12, current_liabilities=liab)), IND["D1"])
        values = [v for _, v in s["points"]]
        self.assertEqual(values[:6], [None] * 6)
        self.assertTrue(all(v is not None for v in values[6:]))

    def test_needs_owner_input_has_reason(self):
        s = trends.indicator_series(business(series(12)), IND["D6"])
        self.assertTrue(s["reason"])

    def test_does_not_change_the_data(self):
        d = business(series(12))
        before = len(d["months"])
        for ind in CFG["indicators"]:
            trends.indicator_series(d, ind)
        self.assertEqual(len(d["months"]), before)


class TestMatchesScores(unittest.TestCase):

    def test_latest_point_is_the_scored_value(self):
        folders = [f for f in (paths.XERO.as_posix(), paths.TEST_HEALTHY.as_posix(), paths.TEST_STRESSED.as_posix())
                   if (Path(f) / "model" / "monthly_summary.csv").exists()]
        if not folders:
            self.skipTest("No built data folders")
        for folder in folders:
            run = scored(folder)
            for r in run["results"]:
                s = trends.indicator_series(run["d"], r["ind"])
                if not s["points"]:
                    continue
                with self.subTest(folder=folder, indicator=r["ind"]["id"]):
                    self.assertEqual(s["points"][-1][1], r.get("value"))


if __name__ == "__main__":
    unittest.main()
