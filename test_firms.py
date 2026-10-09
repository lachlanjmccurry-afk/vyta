"""
VYTA - Tests for adviser matching (firms.py) and the demo listings (firms.json)
--------------------------------------------------------------------------------
Run with:   py -m unittest test_firms -v

Uses small made-up runs (no data folders needed). Also checks every listing in firms.json stays
obviously fictional: reserved 5550 phone numbers and .example email addresses.
"""

import itertools
import re
import unittest

import firms

DATA = firms.load()


def fake_run(distress="High", viability="Strong", ratings=None, label="Restructure candidate"):
    ratings = ratings or {}
    return {"bands": {"distress": distress, "viability": viability}, "pathway_label": label,
            "results": [{"ind": {"id": i}, "rating": r, "display": d} for i, (r, d) in ratings.items()]}


class TestMatching(unittest.TestCase):

    def test_only_firms_serving_the_pathway(self):
        run = fake_run("Low", "Strong")
        for f in firms.matches(run, DATA):
            self.assertTrue("any" in f["serves"] or "Low/Strong" in f["serves"], f["name"])
        names = {f["name"] for f in firms.matches(run, DATA)}
        self.assertNotIn("Northbank Restructuring", names)

    def test_every_pathway_has_advisers(self):
        for d, v in itertools.product(("Low", "Moderate", "High"), ("Strong", "Uncertain", "Weak")):
            with self.subTest(pathway=f"{d}/{v}"):
                self.assertTrue(firms.matches(fake_run(d, v), DATA))

    def test_filter_by_type(self):
        for kind in DATA["types"]:
            for f in firms.matches(fake_run(), DATA, kind=kind):
                self.assertEqual(f["type"], kind)

    def test_why_matched_uses_the_indicator_values(self):
        run = fake_run(ratings={"D4": ("Red", "3 months"), "D5": ("Red", "91.8%")})
        why = {f["id"]: f["why_text"] for f in firms.matches(run, DATA)}
        self.assertEqual(why["bayside"], "Bank debt has grown 91.8% in six months.")
        self.assertEqual(why["northbank"], "Restructure candidate businesses with ATO and bank debt.")

    def test_why_matched_falls_back_when_nothing_is_flagged(self):
        run = fake_run(ratings={"D4": ("Green", "0 months"), "D5": ("Green", "0.0%")})
        why = {f["id"]: f["why_text"] for f in firms.matches(run, DATA)}
        bayside = next(f for f in DATA["firms"] if f["id"] == "bayside")
        self.assertEqual(why["bayside"], bayside["why_default"])

    def test_firms_in_the_business_state_come_first(self):
        run = fake_run("High", "Uncertain")
        listed = firms.matches(run, DATA, state="NSW")
        locals_ = [f["local"] for f in listed]
        self.assertTrue(any(locals_))
        self.assertEqual(locals_, sorted(locals_, reverse=True))
        self.assertTrue(all(f["state"] == "NSW" for f in listed if f["local"]))


class TestListings(unittest.TestCase):

    def test_every_listing_is_complete(self):
        for f in DATA["firms"]:
            with self.subTest(firm=f.get("id")):
                for key in ("id", "name", "initials", "type", "type_label", "serves", "why_default",
                            "helps_with", "city", "state", "phone", "email"):
                    self.assertTrue(f.get(key), key)
                self.assertIn(f["type"], DATA["types"])

    def test_listings_are_fictional(self):
        for f in DATA["firms"]:
            with self.subTest(firm=f["id"]):
                self.assertRegex(f["phone"], r"^\(0[2378]\) 5550 \d{4}$")   # ACMA range reserved for fiction
                self.assertTrue(f["email"].endswith(".example"))            # reserved domain, never delivers
                self.assertFalse(re.search(r"\d{3}\s?\d{3}\s?\d{3}", f.get("badge", "")))   # no real-looking ACN/ABN


if __name__ == "__main__":
    unittest.main()
