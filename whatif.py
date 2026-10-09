"""
VYTA - What if?
----------------
Adjusts a business's figures for a few "what if" levers, then scores the adjusted figures with
score.score_data() - the same function that scores the real data - so there is no second copy of
the scoring rules. Used by the dashboard's What if? page. Never changes the real data or scores.

How each lever changes the figures:
  Price / margin increase (%)   revenue x (1 + %) for the last 12 months; costs unchanged
  Revenue change (%)            more or less volume: revenue and cost of sales both x (1 + %)
  Cost of sales reduction (%)   cost of sales x (1 - %) for the last 12 months
  Overhead reduction (%)        operating expenses x (1 - %) for the last 12 months
  Faster debtor collection      at the latest month-end, debtors fall by that many days of sales
                                (same debtor-days formula as D9) and the cash comes in
  ATO payment plan              the latest ATO debt is spread over 12 months: the first instalment
                                (1/12) is paid from cash at the latest month-end, so the ATO
                                balance falls instead of rising
Profit levers are applied month by month; the extra profit builds up in cash and net assets,
so the balance sheet still balances. Depreciation, interest and unpaid-invoice ageing (D8, D10)
are left as they are.
"""

import copy
import re

import score

LEVERS = ("price", "revenue", "cost_of_sales", "overhead", "debtor_days", "ato_plan")
NO_CHANGE = {"price": 0.0, "revenue": 0.0, "cost_of_sales": 0.0, "overhead": 0.0, "debtor_days": 0,
             "ato_plan": False}


def adjust(d, levers):
    """A copy of the business with the levers applied (percentages as decimals, e.g. 0.1 = 10%)."""
    lv = dict(NO_CHANGE, **levers)
    d = dict(d, months=copy.deepcopy(d["months"]))
    window = d["months"][-12:]
    extra_profit = 0.0
    for m in window:
        revenue = m["revenue"] * (1 + lv["price"]) * (1 + lv["revenue"])
        cost_of_sales = m["cost_of_sales"] * (1 + lv["revenue"]) * (1 - lv["cost_of_sales"])
        opex = m["operating_expenses"] * (1 - lv["overhead"])
        change = (revenue - m["revenue"]) - (cost_of_sales - m["cost_of_sales"]) - (opex - m["operating_expenses"])
        if "total_expenses" in m:
            m["total_expenses"] += (cost_of_sales - m["cost_of_sales"]) + (opex - m["operating_expenses"])
        m["gross_profit"] += (revenue - m["revenue"]) - (cost_of_sales - m["cost_of_sales"])
        m["revenue"], m["cost_of_sales"], m["operating_expenses"] = revenue, cost_of_sales, opex
        m["net_profit"] += change
        extra_profit += change
        move_cash(m, extra_profit, assets_too=True)
        m["net_assets"] += extra_profit

    last = d["months"][-1]
    if lv["debtor_days"] and last["revenue"] > 0:
        collected = min(last["debtors"], lv["debtor_days"] * last["revenue"] * 12 / 365)
        last["debtors"] -= collected
        move_cash(last, collected)              # debtors -> cash: current assets unchanged
    if lv["ato_plan"] and last["ato_liabilities"] > 0:
        instalment = last["ato_liabilities"] / 12
        last["ato_liabilities"] -= instalment
        last["current_liabilities"] -= instalment
        last["total_liabilities"] -= instalment
        move_cash(last, -instalment, assets_too=True)
    return d


def move_cash(m, amount, assets_too=False):
    m["cash"] += amount
    if assets_too:
        m["current_assets"] += amount
        m["total_assets"] += amount


def run(base_run, levers):
    """Score the adjusted business with the same cfg and wording as the real run."""
    d = adjust(base_run["d"], levers)
    return score.score_data(d, base_run["cfg"], base_run["wording"])


def changed_indicators(before, after):
    """[(before result, after result)] for every indicator whose colour changes."""
    by_id = {r["ind"]["id"]: r for r in after["results"]}
    return [(r, by_id[r["ind"]["id"]]) for r in before["results"]
            if by_id[r["ind"]["id"]]["rating"] != r["rating"]]


# ---------- plain-English line ----------

def lever_phrases(levers, text):
    """['cutting overhead by 10%', 'collecting debtors 15 days faster', ...] from wording.json."""
    lv = dict(NO_CHANGE, **levers)
    t = text.get("levers", {})
    pct = lambda x: f"{abs(x) * 100:g}%"
    out = []
    if lv["price"]:
        out.append(t.get("price", "raising prices by {pct}").format(pct=pct(lv["price"])))
    if lv["revenue"]:
        key = "revenue_up" if lv["revenue"] > 0 else "revenue_down"
        out.append(t.get(key, "changing revenue by {pct}").format(pct=pct(lv["revenue"])))
    if lv["cost_of_sales"]:
        out.append(t.get("cost_of_sales", "cutting cost of sales by {pct}").format(pct=pct(lv["cost_of_sales"])))
    if lv["overhead"]:
        out.append(t.get("overhead", "cutting overhead by {pct}").format(pct=pct(lv["overhead"])))
    if lv["debtor_days"]:
        out.append(t.get("debtor_days", "collecting debtors {days} days faster").format(days=lv["debtor_days"]))
    if lv["ato_plan"]:
        out.append(t.get("ato_plan", "putting the ATO debt on a 12-month payment plan"))
    return out


def join(phrases):
    return phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]


def describe(levers, before, after, text):
    """One plain-English sentence, e.g. 'Cutting overhead by 10% and collecting debtors 15 days faster
    moves this business from High to Moderate distress.' Templates are in wording.json -> whatif_page."""
    phrases = lever_phrases(levers, text)
    if not phrases:
        return text.get("no_levers", "Move a slider to see how the scores would change.")
    fields = dict(levers=join(phrases), d_before=before["bands"]["distress"], d_after=after["bands"]["distress"],
                  v_before=before["bands"]["viability"], v_after=after["bands"]["viability"])
    moved = (fields["d_before"] != fields["d_after"], fields["v_before"] != fields["v_after"])
    key = {(True, True): "moves_both", (True, False): "moves_distress", (False, True): "moves_viability",
           (False, False): "no_change"}[moved]
    sentence = text.get(key, "{levers} changes the scores.").format(**fields)
    sentence = sentence[:1].upper() + sentence[1:]
    if before["pathway"] != after["pathway"]:
        sentence += " " + text.get("pathway_change", "").format(before=pathway_name(before["pathway"]),
                                                                 after=pathway_name(after["pathway"]))
    return sentence.strip()


def pathway_name(pathway):
    """'Urgent advice: assess restructure vs liquidation.' -> 'Urgent advice' (the part before : . or ()."""
    return score.sentence_case(re.split(r"[:.(]", pathway)[0].strip())
