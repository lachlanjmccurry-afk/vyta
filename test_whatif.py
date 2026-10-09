"""
VYTA - Tests for the What if? calculations (whatif.py)
-------------------------------------------------------
Run with:   py -m unittest test_whatif -v

Checks that each lever changes the figures as described, that the balance sheet still balances,
that no levers gives exactly the real scores, and the plain-English sentence. Uses made-up numbers;
the real-business checks are skipped unless the data folders have been built.
"""

import contextlib
import io
import unittest
from pathlib import Path

import score
import whatif
from test_score import CFG, IND, business, series

WORDING = score.load_wording()
TEXT = WORDING["whatif_page"]
FOLDERS = [f for f in ("data", "data_healthy", "data_stressed") if (Path(f) / "model" / "monthly_summary.csv").exists()]


def scored(d):
    return score.score_data(d, CFG, WORDING)


def result(run, ind_id):
    return next(r for r in run["results"] if r["ind"]["id"] == ind_id)


def balance_gap(m):
    return m["total_assets"] - m["total_liabilities"] - m["net_assets"]


class TestAdjust(unittest.TestCase):

    def setUp(self):
        # DEFAULTS in test_score: assets 30,000 - liabilities 10,000 = net assets 20,000 (balanced)
        self.d = business(series(12))

    def test_no_levers_changes_nothing(self):
        self.assertEqual(whatif.adjust(self.d, {})["months"], self.d["months"])

    def test_original_untouched(self):
        before = [dict(m) for m in self.d["months"]]
        whatif.adjust(self.d, dict(price=0.1, overhead=0.2, debtor_days=30, ato_plan=True))
        self.assertEqual(self.d["months"], before)

    def test_overhead_cut(self):
        adj = whatif.adjust(self.d, {"overhead": 0.1})["months"]
        self.assertAlmostEqual(adj[0]["operating_expenses"], 4500)
        self.assertAlmostEqual(adj[0]["net_profit"], 1500)          # 1,000 + 10% of 5,000
        self.assertAlmostEqual(adj[-1]["cash"], 10000 + 12 * 500)   # a year of savings arrives as cash

    def test_price_increase_lifts_gross_margin(self):
        run = scored(whatif.adjust(self.d, {"price": 0.1}))
        self.assertAlmostEqual(result(run, "V2")["value"], (11000 - 4000) / 11000)

    def test_volume_moves_cost_of_sales_too(self):
        m = whatif.adjust(self.d, {"revenue": -0.2})["months"][-1]
        self.assertAlmostEqual(m["revenue"], 8000)
        self.assertAlmostEqual(m["cost_of_sales"], 3200)
        self.assertAlmostEqual(m["gross_profit"], 4800)

    def test_cost_of_sales_cut(self):
        m = whatif.adjust(self.d, {"cost_of_sales": 0.25})["months"][-1]
        self.assertAlmostEqual(m["cost_of_sales"], 3000)
        self.assertAlmostEqual(m["gross_profit"], 7000)

    def test_faster_collection_cuts_debtor_days_exactly(self):
        before = scored(self.d)
        after = scored(whatif.adjust(self.d, {"debtor_days": 15}))
        self.assertAlmostEqual(result(after, "D9")["value"], result(before, "D9")["value"] - 15)
        m = whatif.adjust(self.d, {"debtor_days": 15})["months"][-1]
        self.assertAlmostEqual(m["cash"] + m["debtors"], 15000)     # debtors turned into cash
        self.assertAlmostEqual(m["current_assets"], 15000)

    def test_collection_never_below_zero_debtors(self):
        m = whatif.adjust(self.d, {"debtor_days": 10000})["months"][-1]
        self.assertEqual(m["debtors"], 0)

    def test_ato_plan_stops_ato_rising(self):
        d = business(series(12, ato_liabilities=[1000 * (i + 1) for i in range(12)]))
        self.assertEqual(result(scored(d), "D4")["value"], 11)
        adj = whatif.adjust(d, {"ato_plan": True})
        self.assertEqual(result(scored(adj), "D4")["value"], 0)
        self.assertAlmostEqual(adj["months"][-1]["ato_liabilities"], 12000 * 11 / 12)
        self.assertAlmostEqual(adj["months"][-1]["cash"], 10000 - 1000)

    def test_ato_credit_left_alone(self):
        d = business(series(12, ato_liabilities=-500))
        self.assertEqual(whatif.adjust(d, {"ato_plan": True})["months"], d["months"])

    def test_balance_sheet_still_balances(self):
        levers = dict(price=0.07, revenue=-0.15, cost_of_sales=0.1, overhead=0.2, debtor_days=25, ato_plan=True)
        for m in whatif.adjust(self.d, levers)["months"]:
            self.assertAlmostEqual(balance_gap(m), 0, places=6)


class TestScoring(unittest.TestCase):

    def test_better_figures_lower_distress(self):
        d = business(series(12, cash=[20000 - 1500 * i for i in range(12)], net_profit=-1000,
                            ato_liabilities=[1000 * (i + 1) for i in range(12)]))
        before = scored(d)
        after = scored(whatif.adjust(d, dict(overhead=0.3, ato_plan=True, debtor_days=30)))
        self.assertLess(after["scores"]["distress"][0], before["scores"]["distress"][0])

    def test_changed_indicators_only_lists_colour_changes(self):
        d = business(series(12, ato_liabilities=[1000 * (i + 1) for i in range(12)]))
        before, after = scored(d), scored(whatif.adjust(d, {"ato_plan": True}))
        changes = whatif.changed_indicators(before, after)
        self.assertIn("D4", [r0["ind"]["id"] for r0, _ in changes])
        for r0, r1 in changes:
            self.assertNotEqual(r0["rating"], r1["rating"])

    def test_real_businesses_unchanged_with_no_levers(self):
        if not FOLDERS:
            self.skipTest("No built data folders")
        for folder in FOLDERS:
            with contextlib.redirect_stdout(io.StringIO()):
                real = score.compute(folder)
            same = whatif.run(real, {})
            with self.subTest(folder=folder):
                self.assertEqual(same["scores"], real["scores"])
                self.assertEqual(same["bands"], real["bands"])
                self.assertEqual(same["pathway"], real["pathway"])
                self.assertEqual([r["rating"] for r in same["results"]], [r["rating"] for r in real["results"]])
                self.assertFalse(whatif.changed_indicators(real, same))

    def test_overhead_cut_never_raises_distress(self):
        for folder in FOLDERS:
            with contextlib.redirect_stdout(io.StringIO()):
                real = score.compute(folder)
            after = whatif.run(real, {"overhead": 0.2})
            with self.subTest(folder=folder):
                self.assertLessEqual(after["scores"]["distress"][0], real["scores"]["distress"][0])
                self.assertGreaterEqual(after["scores"]["viability"][0], real["scores"]["viability"][0])


def fake(distress, viability, pathway="X"):
    return {"bands": {"distress": distress, "viability": viability}, "pathway": pathway}


class TestSentence(unittest.TestCase):

    def test_example_from_spec(self):
        self.assertEqual(
            whatif.describe({"overhead": 0.1, "debtor_days": 15}, fake("High", "Uncertain"),
                            fake("Moderate", "Uncertain"), TEXT),
            "Cutting overhead by 10% and collecting debtors 15 days faster moves this business "
            "from High to Moderate distress.")

    def test_both_bands_and_pathway(self):
        s = whatif.describe({"price": 0.05}, fake("High", "Weak", "LIKELY LIQUIDATION: x"),
                            fake("Moderate", "Uncertain", "TURNAROUND CANDIDATE: y"), TEXT)
        self.assertEqual(s, "Raising prices by 5% moves this business from High to Moderate distress and from "
                            "Weak to Uncertain viability. The recommended pathway changes from Likely liquidation "
                            "to Turnaround candidate.")

    def test_three_levers_listed(self):
        s = whatif.describe({"revenue": -0.1, "cost_of_sales": 0.05, "ato_plan": True}, fake("Low", "Strong"),
                            fake("Low", "Strong"), TEXT)
        self.assertTrue(s.startswith("A 10% fall in sales volume, cutting cost of sales by 5% and putting the "
                                     "ATO debt on a 12-month payment plan doesn't change either band"), s)

    def test_pathway_names_are_short(self):
        for row in (r for r in CFG["outcome_matrix"].values() if isinstance(r, dict)):
            for pathway in row.values():
                name = whatif.pathway_name(pathway)
                self.assertTrue(name and len(name) <= 40 and not name.endswith((".", ":")), name)
        self.assertEqual(whatif.pathway_name("Likely liquidation / exit pathway (CVL, sale of business)."),
                         "Likely liquidation / exit pathway")
        self.assertEqual(whatif.pathway_name("RESTRUCTURE CANDIDATE: SBR, VA"), "Restructure candidate")

    def test_no_levers(self):
        self.assertEqual(whatif.describe({}, fake("Low", "Strong"), fake("Low", "Strong"), TEXT), TEXT["no_levers"])

    def test_every_template_fills_in(self):
        fields = dict(levers="x", d_before="a", d_after="b", v_before="c", v_after="d", before="e", after="f",
                      pct="5%", days=10)
        for key in ("moves_both", "moves_distress", "moves_viability", "no_change", "pathway_change"):
            TEXT[key].format(**fields)
        for t in TEXT["levers"].values():
            t.format(**fields)


if __name__ == "__main__":
    unittest.main()
