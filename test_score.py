"""
VYTA - Tests for the scoring engine
------------------------------------
Run with:   py -m unittest test_score -v

What's checked:
  1. Thresholds - for every indicator, small made-up businesses are built so the indicator lands
     clearly Green, exactly on the Amber threshold, between Amber and Red, exactly on the Red
     threshold, and beyond Red. Thresholds are read from scorecard.json, so if you change a
     threshold the tests follow it automatically.
  2. Edge cases - the special rules in scorecard.json (overdrawn, no debt, divide-by-zero...)
     and the "Not assessed" reasons.
  3. Scoring - weighted average, bands, statutory demand override.
  4. Config - weights add to 100 and every indicator in SCORECARD.md is in scorecard.json and
     has a calculation.
  5. Wording - every indicator has Amber and Red sentences in wording.json, every pathway has a
     summary, and every sentence fills in all its {placeholders}.
  6. Test businesses - if data_healthy / data_stressed exist (py make_test_data.py), they
     still land in the expected bands.

Uses only made-up numbers and local files. Never touches Xero.
"""

import copy
import re
import unittest
from datetime import date
from pathlib import Path

import score
from build_model import month_ends

CFG = score.load_config()
IND = {i["id"]: i for i in CFG["indicators"]}
AS_AT = date(2026, 10, 4)

DEFAULTS = dict(revenue=10000, cost_of_sales=4000, operating_expenses=5000, gross_profit=6000,
                net_profit=1000, cash=10000, debtors=5000, current_assets=15000, creditors=3000,
                current_liabilities=5000, total_assets=30000, total_liabilities=10000,
                net_assets=20000, ato_liabilities=1000, has_activity=True)


# ---------- building made-up businesses ----------

def series(n=12, **cols):
    """n months (oldest first). Each column is a single value for every month, or a list of n values."""
    ends = list(reversed(month_ends(date(2026, 9, 30), n)))
    months = []
    for i, end in enumerate(ends):
        m = dict(DEFAULTS, month=end)
        for k, v in cols.items():
            m[k] = v[i] if isinstance(v, list) else v
        months.append(m)
    return months


def business(months, pl=(), bs=(), invoices=()):
    return {"base": Path("test"), "org": "Test", "months": months, "pl": list(pl), "bs": list(bs),
            "invoices": list(invoices), "account_types": {}, "as_at": AS_AT,
            "interest_pattern": "interest", "depreciation_pattern": "depreciation|amortisation|amortization"}


def line(month, section, name, value):
    return {"section": section, "line": name, "is_total": False, "month": month, "value": value}


def invoice(kind, amount, days_overdue):
    due = date.fromordinal(AS_AT.toordinal() - days_overdue)
    return {"Type": kind, "Status": "AUTHORISED", "AmountDue": amount,
            "DueDateString": f"{due.isoformat()}T00:00:00"}


def aged(kind, share_over_90):
    total = 10000
    return business(series(), invoices=[invoice(kind, total * share_over_90, 120),
                                        invoice(kind, total * (1 - share_over_90), -10)])


def consecutive(n, rise):
    """12 values: flat, then rising by `rise` in each of the last n months."""
    return [1000 + max(0, i - (12 - n) + 1) * rise for i in range(12)]


# One builder per indicator: given a target value, build a business that should produce exactly
# that value. Returns None if the value can't occur through the normal formula.

def b_d3(v, ind):
    if v <= 0:
        return None
    lb = ind.get("lookback_months", 3)
    cash = 12000.0
    values = [cash + cash / v * lb] * (12 - lb) + [cash + cash / v * (lb - k) for k in range(1, lb + 1)]
    return business(series(cash=values))


def b_d5(v, ind):
    lb = ind.get("lookback_months", 6)
    ms = series()
    loans = [10000.0] * 12
    loans[-1] = 10000 * (1 + v)
    return business(ms, bs=[line(m["month"], "Non-Current Liabilities", "Bank Loan", loans[i])
                            for i, m in enumerate(ms) if i in (11, 11 - lb)])


def b_d6(v, ind):
    ms = series()
    return business(ms, bs=[line(ms[-1]["month"], "Bank", "Business Bank Account", -v * 100000)])


def b_d9(v, ind):
    lb = ind.get("lookback_months", 3)
    to_debtors = lambda days: days * 10000 * 12 / 365
    debtors = [to_debtors(30)] * 12
    debtors[-1] = to_debtors(30 + v)
    return business(series(debtors=debtors))


def b_d11(n, ind):
    revenue = [10000 + max(0, i - (12 - n) + 1) * 1000 for i in range(12)]
    cash = [50000 - max(0, i - (12 - n) + 1) * 1000 for i in range(12)]
    return business(series(revenue=revenue, cash=cash))


def b_v3(v, ind):
    gp = [4000] * 12 + [(0.4 + v) * 10000] * 12
    return business(series(24, gross_profit=gp))


def b_v6(v, ind):
    return business(series(24, revenue=[10000] * 12 + [10000 * (1 + v)] * 12))


def b_v8(v, ind):
    if v <= 0:
        return None
    return business(series(total_assets=30000, current_assets=10000, current_liabilities=5000,
                           total_liabilities=5000 + 20000 / v))


BUILDERS = {
    "D1": lambda v, ind: business(series(current_assets=v * 5000, current_liabilities=5000)),
    "D2": lambda v, ind: business(series(cash=v * 5000, debtors=0, current_liabilities=5000)),
    "D3": b_d3,
    "D4": lambda n, ind: business(series(ato_liabilities=consecutive(n, (ind.get("min_increase_dollars") or 0) + 500))),
    "D5": b_d5,
    "D6": b_d6,
    "D7": lambda v, ind: business(series(creditors=v * 108000 / 365)),   # costs = (4000 + 5000) x 12
    "D8": lambda v, ind: aged("ACCPAY", v) if 0 <= v <= 1 else None,
    "D9": b_d9,
    "D10": lambda v, ind: aged("ACCREC", v) if 0 <= v <= 1 else None,
    "D11": b_d11,
    "D12": lambda v, ind: business(series(net_profit=v * 5000 / 12, current_liabilities=5000)),
    "D13": lambda v, ind: business(series(total_liabilities=v * 30000, total_assets=30000)),
    "V1": lambda v, ind: business(series(net_assets=v * 30000, total_assets=30000)),
    "V2": lambda v, ind: business(series(gross_profit=v * 10000)),
    "V3": b_v3,
    "V4": lambda v, ind: business(series(gross_profit=10000, operating_expenses=v * 10000)),
    "V5": lambda v, ind: business(series(net_profit=v * 10000)),
    "V6": b_v6,
    "V8": b_v8,
}


def threshold_cases(ind):
    """(value, expected rating) pairs around the thresholds from scorecard.json."""
    amber, red = ind["amber"], ind["red"]
    worse = 1 if ind["direction"] == "higher_is_worse" else -1
    if ind.get("unit") == "count":
        return [(amber - 1, "Green"), (amber, "Amber"), (red, "Red"), (red + 1, "Red")]
    gap = abs(red - amber)
    return [(amber - worse * gap, "Green"), (amber, "Amber"), ((amber + red) / 2, "Amber"),
            (red, "Red"), (red + worse * gap, "Red")]


def run_one(ind, d):
    """Score a single indicator through the same path score.py uses."""
    return score.assess(d, {"indicators": [ind], "points": CFG["points"]})[0]


# ---------- 1. thresholds ----------

class TestThresholds(unittest.TestCase):
    """One test per indicator: Green / on Amber / between / on Red / beyond Red."""


def make_threshold_test(iid):
    def test(self):
        ind = copy.deepcopy(IND[iid])
        if iid == "D6":
            ind["approved_limit_dollars"] = 100000
        tested = 0
        for target, expected in threshold_cases(ind):
            d = BUILDERS[iid](target, ind)
            if d is None:
                continue
            with self.subTest(indicator=iid, value=target, expected=expected):
                res = run_one(ind, d)
                self.assertIn("value", res, f"{iid} didn't calculate a value: {res.get('note')}")
                self.assertAlmostEqual(res["value"], target, places=6)
                self.assertEqual(res["rating"], expected)
                tested += 1
        self.assertGreaterEqual(tested, 3, f"{iid}: too few threshold cases could be built")
    test.__doc__ = f"{iid} {IND[iid].get('name', '')}: ratings match scorecard.json thresholds"
    return test


for _iid in BUILDERS:
    if _iid in IND:
        setattr(TestThresholds, f"test_{_iid}", make_threshold_test(_iid))


# ---------- 2. edge cases and "Not assessed" ----------

class TestEdgeCases(unittest.TestCase):

    def test_D3_overdrawn_uses_config_rule(self):
        res = run_one(IND["D3"], business(series(cash=-500)))
        self.assertEqual(res["rating"], IND["D3"].get("if_cash_zero_or_negative", "Red"))

    def test_D3_cash_not_falling_uses_config_rule(self):
        res = run_one(IND["D3"], business(series(cash=[1000 * i for i in range(1, 13)])))
        self.assertEqual(res["rating"], IND["D3"].get("if_cash_not_falling", "Green"))

    def test_D4_counts_only_the_latest_run(self):
        ato = [1000, 2000, 3000, 4000, 5000, 1000, 1000, 1000, 1000, 1500, 2000, 2500]
        res = run_one(IND["D4"], business(series(ato_liabilities=ato)))
        self.assertEqual(res["value"], 3)

    def test_D5_new_debt_uses_config_rule(self):
        ms = series()
        d = business(ms, bs=[line(ms[-1]["month"], "Non-Current Liabilities", "Bank Loan", 20000)])
        self.assertEqual(run_one(IND["D5"], d)["rating"], IND["D5"].get("if_no_debt_before_but_debt_now", "Red"))

    def test_D5_no_debt_is_green(self):
        self.assertEqual(run_one(IND["D5"], business(series()))["rating"], "Green")

    def test_D5_ignores_owner_loans(self):
        ms = series()
        d = business(ms, bs=[line(ms[-1]["month"], "Current Liabilities", "Owner A Loan", 50000)])
        self.assertEqual(run_one(IND["D5"], d)["rating"], "Green")

    def test_D5_counts_overdraft(self):
        ms = series()
        d = business(ms, bs=[line(ms[5]["month"], "Bank", "Business Bank Account", -10000),
                             line(ms[11]["month"], "Bank", "Business Bank Account", -20000)])
        self.assertAlmostEqual(run_one(IND["D5"], d)["value"], 1.0)

    def test_D6_without_limit_is_owner_question(self):
        ind = dict(IND["D6"], approved_limit_dollars=None)
        self.assertEqual(run_one(ind, business(series()))["rating"], score.OWNER_QUESTION)

    def test_D8_D10_nothing_unpaid_is_green(self):
        for iid in ("D8", "D10"):
            self.assertEqual(run_one(IND[iid], business(series()))["rating"], "Green")

    def test_D8_ignores_paid_and_draft_invoices(self):
        inv = [dict(invoice("ACCPAY", 5000, 200), Status="PAID"),
               dict(invoice("ACCPAY", 5000, 200), Status="DRAFT"),
               invoice("ACCPAY", 1000, -5)]
        self.assertEqual(run_one(IND["D8"], business(series(), invoices=inv))["value"], 0)

    def test_D9_no_revenue_is_not_assessed(self):
        revenue = [10000] * 12
        revenue[-4] = 0
        self.assertEqual(run_one(IND["D9"], business(series(revenue=revenue)))["rating"], score.NOT_ASSESSED)

    def test_D11_falling_sales_is_green(self):
        d = business(series(revenue=[20000 - 1000 * i for i in range(12)],
                            cash=[50000 - 1000 * i for i in range(12)]))
        self.assertEqual(run_one(IND["D11"], d)["value"], 0)

    def test_D12_includes_working_capital_and_depreciation(self):
        ms = series(net_profit=0, debtors=[5000] * 11 + [8000], creditors=[3000] * 11 + [4000],
                    ato_liabilities=[1000] * 11 + [1500], current_liabilities=5000)
        pl = [line(m["month"], "Less Operating Expenses", "Depreciation", 100) for m in ms]
        # 0 profit + 1,200 depreciation - 3,000 debtors + 1,000 creditors + 500 ATO = -300
        self.assertAlmostEqual(run_one(IND["D12"], business(ms, pl=pl))["value"], -300 / 5000)

    def test_D13_no_assets_uses_config_rule(self):
        res = run_one(IND["D13"], business(series(total_assets=0)))
        self.assertEqual(res["rating"], IND["D13"].get("if_assets_zero_or_negative", "Red"))

    def test_V3_V6_need_24_months(self):
        for iid in ("V3", "V6"):
            self.assertEqual(run_one(IND[iid], business(series()))["rating"], score.NOT_ASSESSED)

    def test_V2_V3_no_cost_of_sales_is_not_assessed(self):
        for iid, months in (("V2", 12), ("V3", 24)):
            with self.subTest(indicator=iid):
                res = run_one(IND[iid], business(series(months, cost_of_sales=0, gross_profit=10000)))
                self.assertEqual(res["rating"], score.NOT_ASSESSED)
                self.assertEqual(res["display"], "No cost of sales")
                self.assertIn("no cost of sales recorded", res["note"])
                self.assertIsNone(res["points"])

    def test_V3_no_cost_of_sales_in_earlier_year_is_not_assessed(self):
        cogs = [0] * 12 + [4000] * 12
        res = run_one(IND["V3"], business(series(24, cost_of_sales=cogs)))
        self.assertEqual(res["display"], "No cost of sales")
        self.assertIn("earlier 12-month period", res["note"])

    def test_V4_no_gross_profit_uses_config_rule(self):
        res = run_one(IND["V4"], business(series(gross_profit=0)))
        self.assertEqual(res["rating"], IND["V4"].get("if_gross_profit_zero_or_negative", "Red"))

    def test_V5_adds_back_interest_depreciation_and_one_offs(self):
        ms = series(net_profit=-500)
        pl = [line(m["month"], "Less Operating Expenses", "Interest Expense", 200) for m in ms] + \
             [line(m["month"], "Less Operating Expenses", "Depreciation", 300) for m in ms] + \
             [line(m["month"], "Income", "Interest Income", 999) for m in ms]   # income must be ignored
        ind = dict(IND["V5"], one_off_costs_dollars=12000)
        # (-6,000 + 2,400 + 3,600 + 12,000) / 120,000 = 0.10
        self.assertAlmostEqual(run_one(ind, business(ms, pl=pl))["value"], 0.10)

    def test_V7_not_assessed_until_quotes_pulled(self):
        self.assertEqual(run_one(IND["V7"], business(series()))["rating"], score.NOT_ASSESSED)

    def test_V8_no_long_term_liabilities_uses_config_rule(self):
        res = run_one(IND["V8"], business(series(total_liabilities=5000, current_liabilities=5000)))
        self.assertEqual(res["rating"], IND["V8"].get("if_no_long_term_liabilities", "Green"))

    def test_disabled_indicator_is_skipped(self):
        cfg = {"indicators": [dict(IND["D1"], enabled=False)], "points": CFG["points"]}
        self.assertEqual(score.assess(business(series()), cfg), [])


# ---------- 3. scoring, bands, overrides ----------

class TestScoring(unittest.TestCase):

    def result(self, kind, weight, rating):
        return {"ind": {"score": kind, "weight": weight}, "rating": rating,
                "points": CFG["points"][kind].get(rating)}

    def test_weighted_average_excludes_not_assessed(self):
        results = [self.result("distress", 10, "Red"), self.result("distress", 30, "Green"),
                   self.result("distress", 60, score.NOT_ASSESSED)]
        s, weight, possible, _ = score.total_score(results, "distress")
        red = CFG["points"]["distress"]["Red"]
        green = CFG["points"]["distress"]["Green"]
        self.assertAlmostEqual(s, (10 * red + 30 * green) / 40)
        self.assertEqual((weight, possible), (40, 100))

    def test_nothing_assessed_gives_no_score(self):
        s, *_ = score.total_score([self.result("viability", 10, score.NOT_ASSESSED)], "viability")
        self.assertIsNone(s)
        self.assertEqual(score.band_for(None, "viability", CFG), "Not enough data")

    def test_band_boundaries_from_config(self):
        for kind in ("distress", "viability"):
            bands = sorted(CFG["bands"][kind], key=lambda b: b["from"])
            for lower, upper in zip(bands, bands[1:]):
                with self.subTest(kind=kind, band=upper["band"]):
                    self.assertEqual(score.band_for(upper["from"], kind, CFG), upper["band"])
                    self.assertEqual(score.band_for(upper["from"] - 0.1, kind, CFG), lower["band"])

    def override(self, answer):
        cfg = copy.deepcopy(CFG)
        for q in cfg["owner_questions"]:
            if q["id"] == "Q1":
                q["answer"] = answer
        bands = {"distress": "Low", "viability": "Strong"}
        notes = score.apply_overrides(cfg, bands)
        return bands, notes

    def test_statutory_demand_yes_forces_high(self):
        bands, notes = self.override("Yes")
        self.assertEqual(bands["distress"], "High")
        self.assertTrue(any(n.startswith("APPLIED") for n in notes))

    def test_statutory_demand_no_leaves_band(self):
        self.assertEqual(self.override("No")[0]["distress"], "Low")

    def test_statutory_demand_unanswered_is_flagged(self):
        bands, notes = self.override(None)
        self.assertEqual(bands["distress"], "Low")
        self.assertTrue(any("not answered" in n for n in notes))


# ---------- 4. config ----------

class TestConfig(unittest.TestCase):

    def test_weights_add_to_100(self):
        for kind in ("distress", "viability"):
            total = sum(i["weight"] for i in CFG["indicators"] if i["score"] == kind and i.get("enabled", True))
            self.assertAlmostEqual(total, 100, msg=f"{kind} weights")

    def test_amber_comes_before_red(self):
        for ind in CFG["indicators"]:
            with self.subTest(indicator=ind["id"]):
                if ind["direction"] == "higher_is_worse":
                    self.assertLessEqual(ind["amber"], ind["red"])
                else:
                    self.assertGreaterEqual(ind["amber"], ind["red"])

    def test_every_scorecard_indicator_is_configured_and_calculated(self):
        md = Path("SCORECARD.md")
        if not md.exists():
            self.skipTest("SCORECARD.md not in folder")
        spec_ids = set(re.findall(r"^\| ([DV]\d+) \|", md.read_text(encoding="utf-8"), re.M))
        self.assertEqual(spec_ids, set(IND), "scorecard.json indicators differ from SCORECARD.md")
        for iid in spec_ids:
            self.assertIn(iid, score.CALCS, f"{iid} has no calculation in score.py")

    def test_every_indicator_has_a_threshold_test(self):
        tested = set(BUILDERS) | {"V7"}    # V7 can't be calculated yet - covered in edge cases
        self.assertEqual(set(IND) - tested, set())


# ---------- 5. plain-English wording ----------

WORDING = score.load_wording()


class TestWording(unittest.TestCase):

    def explain(self, ind, d):
        res = run_one(ind, d)
        problems = []
        return res, score.explain(res, WORDING, problems), problems

    def test_every_indicator_has_green_amber_and_red_sentences(self):
        for iid in IND:
            for rating in ("green", "amber", "red"):
                with self.subTest(indicator=iid, rating=rating):
                    self.assertTrue(WORDING["indicators"].get(iid, {}).get(rating),
                                    f"{iid} has no '{rating}' sentence in wording.json")

    def test_every_pathway_has_a_summary(self):
        for distress in (b["band"] for b in CFG["bands"]["distress"]):
            for viability in (b["band"] for b in CFG["bands"]["viability"]):
                with self.subTest(distress=distress, viability=viability):
                    self.assertTrue(score.pathway_summary(WORDING, {"distress": distress, "viability": viability}))

    def test_sentences_fill_in_every_placeholder(self):
        """Every Green/Amber/Red result from the threshold tests produces a complete sentence."""
        for iid, build in BUILDERS.items():
            ind = dict(IND[iid], approved_limit_dollars=100000) if iid == "D6" else IND[iid]
            for target, expected in threshold_cases(ind):
                d = build(target, ind)
                if d is None:
                    continue
                with self.subTest(indicator=iid, rating=expected):
                    res, text, problems = self.explain(ind, d)
                    self.assertEqual(problems, [])
                    self.assertNotIn("{", text)
                    self.assertGreater(len(text), 30)

    def test_special_case_sentences(self):
        ms = series()
        cases = [
            ("D3", business(series(cash=-500)), "overdrawn"),
            ("D5", business(ms, bs=[line(ms[-1]["month"], "Non-Current Liabilities", "Bank Loan", 20000)]), "none at"),
            ("D12", business(series(net_profit=-1000)), "used more cash"),
            ("D13", business(series(total_assets=0)), "no assets"),
            ("V1", business(series(total_assets=0)), "no assets"),
            ("V4", business(series(gross_profit=0)), "no gross profit"),
            # Green special cases
            ("D1", business(series(current_liabilities=0)), "no short-term debts"),
            ("D2", business(series(current_liabilities=0)), "no short-term debts"),
            ("D3", business(series(cash=[1000 * i for i in range(1, 13)])), "isn't falling"),
            ("D5", business(series()), "no bank loans"),
            ("D8", business(series()), "no unpaid supplier bills"),
            ("D10", business(series()), "no customers owe"),
            ("D8", aged("ACCPAY", 0), "none of the $10,000 in unpaid supplier bills"),
            ("D10", aged("ACCREC", 0), "none of the $10,000 owed by customers"),
            ("D12", business(series(current_liabilities=0)), "no short-term debts"),
            ("V8", business(series(total_liabilities=5000, current_liabilities=5000)), "no long-term debt"),
        ]
        for iid, d, phrase in cases:
            with self.subTest(indicator=iid, phrase=phrase):
                res, text, problems = self.explain(IND[iid], d)
                self.assertEqual(problems, [])
                self.assertIn(phrase, text.lower())

    def test_ato_credit_reads_as_credit_not_negative(self):
        ato = [-791] * 9 + [1631, 6583, 11062]
        res, text, problems = self.explain(IND["D4"], business(series(ato_liabilities=ato)))
        self.assertEqual(res["rating"], "Red")
        self.assertIn("from a $791 credit to $11,062 owed", text)
        self.assertNotIn("-$", text)
        self.assertIn("$791 credit", res["note"])

    def test_green_gets_a_going_well_sentence(self):
        res, text, problems = self.explain(IND["D13"], BUILDERS["D13"](0.1, IND["D13"]))
        self.assertEqual(res["rating"], "Green")
        self.assertIn("isn't over-reliant on borrowing", text)

    def test_not_assessed_gets_no_sentence(self):
        self.assertEqual(self.explain(IND["V7"], business(series()))[1], "")

    def test_unknown_placeholder_is_reported_not_crashed(self):
        wording = {"indicators": {"D13": {"red": "Debts are {not_a_real_figure}."}}}
        res = run_one(IND["D13"], BUILDERS["D13"](2, IND["D13"]))
        problems = []
        text = score.explain(res, wording, problems)
        self.assertEqual(text, "Debts are {not_a_real_figure}.")
        self.assertEqual(len(problems), 1)

    def test_missing_sentence_uses_fallback(self):
        res = run_one(IND["D13"], BUILDERS["D13"](2, IND["D13"]))
        text = score.explain(res, {"indicators": {}, "fallback": "{name} is {value}."}, [])
        self.assertEqual(text, f"{IND['D13']['name']} is 2.00.")


class TestMemo(unittest.TestCase):
    """The dashboard memo: verdict headline, top 3 issues, what's working, pathway in sentence case."""

    def test_every_pathway_has_a_verdict(self):
        for distress in (b["band"] for b in CFG["bands"]["distress"]):
            for viability in (b["band"] for b in CFG["bands"]["viability"]):
                with self.subTest(distress=distress, viability=viability):
                    text = score.verdict(WORDING, {"distress": distress, "viability": viability}, "Acme Pty Ltd")
                    self.assertTrue(text.startswith("Acme Pty Ltd "))
                    self.assertNotIn("{", text)

    def test_verdict_without_enough_data(self):
        text = score.verdict(WORDING, {"distress": "Not enough data", "viability": "Strong"}, "Acme")
        self.assertIn("Acme", text)

    def test_sentence_case_keeps_acronyms(self):
        self.assertEqual(score.sentence_case("RESTRUCTURE CANDIDATE: SBR, VA or safe harbour."),
                         "Restructure candidate: SBR, VA or safe harbour.")
        self.assertEqual(score.sentence_case("Healthy. Monitor quarterly."), "Healthy. Monitor quarterly.")

    def result(self, iid, weight, rating):
        return {"ind": {"id": iid, "weight": weight}, "rating": rating}

    def test_top_issues_weigh_red_above_amber(self):
        results = [self.result("A", 15, "Amber"), self.result("B", 12, "Red"), self.result("C", 10, "Red"),
                   self.result("D", 10, "Red"), self.result("E", 20, "Green"), self.result("F", 30, "Not assessed")]
        self.assertEqual([r["ind"]["id"] for r in score.top_issues(results)], ["B", "C", "D"])

    def test_top_issues_with_fewer_than_three(self):
        self.assertEqual(len(score.top_issues([self.result("A", 5, "Amber")])), 1)
        self.assertEqual(score.top_issues([self.result("A", 5, "Green")]), [])

    def test_whats_working_is_heaviest_greens(self):
        results = [self.result("A", 5, "Green"), self.result("B", 20, "Green"), self.result("C", 10, "Green"),
                   self.result("D", 7, "Green"), self.result("E", 50, "Red")]
        self.assertEqual([r["ind"]["id"] for r in score.whats_working(results)], ["B", "C", "D"])


# ---------- 6. data confidence and table labels ----------

TABLE_LABEL_MAX = 20     # longest short indicator name allowed in tables
TABLE_VALUE_MAX = 18     # longest value / reason label allowed in tables


class TestConfidence(unittest.TestCase):

    def level(self, active):
        d = business(series(has_activity=[False] * (12 - active) + [True] * active))
        return score.data_confidence(d, CFG, WORDING)

    def test_levels_follow_config_cut_offs(self):
        high = CFG["data_confidence"]["high_from_months"]
        medium = CFG["data_confidence"]["medium_from_months"]
        for active, expected in ((0, "Low"), (medium - 1, "Low"), (medium, "Medium"),
                                 (high - 1, "Medium"), (high, "High")):
            with self.subTest(months=active):
                self.assertEqual(self.level(active)["level"], expected)

    def test_under_6_months_is_low(self):
        for active in range(6):
            self.assertEqual(self.level(active)["level"], "Low")

    def test_confidence_sentence_fills_in(self):
        conf = self.level(3)
        self.assertIn("Only 3 of 12 months", conf["text"])
        self.assertNotIn("{", conf["text"])


class TestTableLabels(unittest.TestCase):
    """Tables show short labels only, so nothing gets cut off. Full text lives in the explanations."""

    def all_results(self):
        out = []
        for iid, build in BUILDERS.items():
            ind = dict(IND[iid], approved_limit_dollars=100000) if iid == "D6" else IND[iid]
            for target, _ in threshold_cases(ind):
                d = build(target, ind)
                if d is not None:
                    out.append(run_one(ind, d))
        edge_cases = [business(series(cash=-500)), business(series(current_liabilities=0)),
                      business(series(total_assets=0)), business(series(gross_profit=0)),
                      business(series(cost_of_sales=0)), business(series(revenue=0))]
        for d in edge_cases:
            out += score.assess(d, CFG)
        for folder in ("data", "data_healthy", "data_stressed"):
            if (Path(folder) / "model" / "monthly_summary.csv").exists():
                out += score.assess(score.load_data(Path(folder), CFG), CFG)
        return out

    def test_short_names_fit(self):
        for ind in CFG["indicators"]:
            with self.subTest(indicator=ind["id"]):
                self.assertIn("short_name", ind)
                self.assertLessEqual(len(score.short_name(ind)), TABLE_LABEL_MAX)

    def test_values_and_reasons_fit(self):
        for r in self.all_results():
            with self.subTest(indicator=r["ind"]["id"], display=r.get("display")):
                self.assertTrue(r.get("display"), "every result needs a table value or short reason")
                self.assertLessEqual(len(r["display"]), TABLE_VALUE_MAX)


# ---------- 7. the synthetic test businesses ----------

class TestBusinesses(unittest.TestCase):

    def run_folder(self, folder):
        if not (Path(folder) / "model" / "monthly_summary.csv").exists():
            self.skipTest(f"{folder} not built - run  py make_test_data.py  and  py build_model.py {folder}")
        d = score.load_data(Path(folder), CFG)
        results = score.assess(d, CFG)
        return {kind: score.band_for(score.total_score(results, kind)[0], kind, CFG)
                for kind in ("distress", "viability")}

    def test_healthy_business(self):
        self.assertEqual(self.run_folder("data_healthy"), {"distress": "Low", "viability": "Strong"})

    def test_stressed_business(self):
        self.assertEqual(self.run_folder("data_stressed"), {"distress": "High", "viability": "Weak"})


if __name__ == "__main__":
    unittest.main()
