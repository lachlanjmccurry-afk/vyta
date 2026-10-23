"""
VYTA - Adviser matching for the Get help page
----------------------------------------------
Reads firms.json (fictional demo listings) and picks the firms that serve the business's pathway,
with a "Why matched" sentence built from the indicator results. Firms in the business's own state
(from Xero's organisation address) are listed first; otherwise firms.json order is kept.
Read-only. Never contacts Xero.
"""

import json
from pathlib import Path

import paths

FIRMS = paths.FIRMS
FLAGGED = ("Red", "Amber")


class Blank(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def load():
    if not FIRMS.exists():
        return {"types": {}, "firms": []}
    return json.loads(FIRMS.read_text(encoding="utf-8"))


def business_state(base):
    """The business's state (e.g. 'NSW') from its Xero street address, or None."""
    try:
        org = json.loads((Path(base) / "raw" / "organisation.json").read_text())["Organisations"][0]
    except (OSError, KeyError, IndexError, ValueError):
        return None
    addresses = sorted(org.get("Addresses", []), key=lambda a: a.get("AddressType") != "STREET")
    return next((a["Region"].strip().upper() for a in addresses if a.get("Region")), None)


def pathway_key(run):
    return f"{run['bands']['distress']}/{run['bands']['viability']}"


def why_matched(firm, run):
    results = {r["ind"]["id"]: r for r in run["results"]}
    fields = Blank({i: r.get("display", "") for i, r in results.items()}, pathway=run["pathway_label"])
    for rule in firm.get("why", []):
        if all(results.get(i, {}).get("rating") in FLAGGED for i in rule["indicators"]):
            return rule["text"].format_map(fields)
    return firm.get("why_default", "").format_map(fields)


def matches(run, data, state=None, kind=None):
    """Firms that serve this pathway (optionally only one type), each with 'why_text' and 'local' added."""
    key = pathway_key(run)
    out = []
    for order, firm in enumerate(data.get("firms", [])):
        serves = firm.get("serves", [])
        if "any" not in serves and key not in serves:
            continue
        if kind and firm.get("type") != kind:
            continue
        out.append({**firm, "why_text": why_matched(firm, run), "local": bool(state) and firm.get("state") == state,
                    "_order": order})
    return sorted(out, key=lambda f: (not f["local"], f["_order"]))
