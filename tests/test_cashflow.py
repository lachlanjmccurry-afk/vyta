"""
VYTA - Tests for the "Where has the cash gone?" calculation (cashflow.py)
-------------------------------------------------------------------------
Run with:   py -m unittest test_cashflow -v

Uses only made-up numbers. Never touches Xero.
"""

import _setup  # noqa: F401  (code folders + work from the vyta folder)
import paths
import unittest

from cashflow import STEPS, cash_bridge
from test_score import business, line, series


def bridge_total(b):
    return b["opening"] + sum(v for _, v in b["steps"])


class TestCashBridge(unittest.TestCase):

    def test_hand_worked_example(self):
        # 13 months so the opening balance is the month-end before the 12-month window
        cash = [10000] + [9000] * 11 + [7000]
        ms = series(13, cash=cash, net_profit=500, debtors=[5000] * 12 + [8000],
                    creditors=[3000] * 12 + [3500], ato_liabilities=[1000] * 12 + [2500])
        b = cash_bridge(business(ms))
        steps = dict(b["steps"])
        self.assertEqual(b["opening"], 10000)
        self.assertEqual(b["closing"], 7000)
        self.assertEqual(b["opening_month"], ms[0]["month"])
        self.assertEqual(b["months_covered"], 12)
        self.assertEqual(steps["Operating profit"], 6000)        # 12 months x 500
        self.assertEqual(steps["ATO movement"], 1500)            # ATO owed more = cash kept
        self.assertEqual(steps["Debt movement"], 0)
        self.assertEqual(steps["Change in debtors"], -3000)      # customers owe more = cash not collected
        self.assertEqual(steps["Change in creditors"], 500)      # owe suppliers more = cash kept
        self.assertEqual(steps["Other"], -3000 - 6000 - 1500 + 3000 - 500)
        self.assertAlmostEqual(bridge_total(b), b["closing"])

    def test_steps_in_order(self):
        b = cash_bridge(business(series(13)))
        self.assertEqual(tuple(label for label, _ in b["steps"]), STEPS)

    def test_twelve_months_starts_at_first_month_end(self):
        ms = series(12, cash=[1000 + i * 100 for i in range(12)])
        b = cash_bridge(business(ms))
        self.assertEqual(b["opening_month"], ms[0]["month"])
        self.assertEqual(b["opening"], 1000)
        self.assertEqual(b["months_covered"], 11)
        self.assertEqual(dict(b["steps"])["Operating profit"], 11 * 1000)
        self.assertAlmostEqual(bridge_total(b), b["closing"])

    def test_twenty_four_months_uses_last_twelve(self):
        ms = series(24, cash=list(range(1000, 25000, 1000)))
        b = cash_bridge(business(ms))
        self.assertEqual(b["opening_month"], ms[11]["month"])
        self.assertEqual(b["months_covered"], 12)
        self.assertAlmostEqual(bridge_total(b), b["closing"])

    def test_new_loan_counts_overdraft_excluded(self):
        ms = series(13)
        first, last = ms[0]["month"], ms[-1]["month"]
        bs = [line(first, "Non-current Liabilities", "Bank Loan", 20000),
              line(last, "Non-current Liabilities", "Bank Loan", 50000),
              line(last, "Bank", "Business Cheque", -4000),          # overdraft: already inside cash
              line(last, "Current Liabilities", "Director Loan", 9000)]  # not bank debt
        steps = dict(cash_bridge(business(ms, bs=bs))["steps"])
        self.assertEqual(steps["Debt movement"], 30000)

    def test_always_adds_up(self):
        for n in (2, 6, 12, 13, 24):
            ms = series(n, cash=[(i * 7919) % 5000 - 1000 for i in range(n)],
                        debtors=[(i * 3001) % 4000 for i in range(n)],
                        net_profit=[(i * 1237) % 900 - 300 for i in range(n)])
            b = cash_bridge(business(ms))
            self.assertAlmostEqual(bridge_total(b), b["closing"], msg=f"{n} months")

    def test_one_month_has_no_bridge(self):
        self.assertIsNone(cash_bridge(business(series(1))))


if __name__ == "__main__":
    unittest.main()
