"""
VYTA - Early-warning benchmark on closed jobs
----------------------------------------------
Run with:   .venv\\Scripts\\python.exe benchmark.py           (summary table)
            .venv\\Scripts\\python.exe benchmark.py --months  (also every month's score)

For each imported business (data_business_a, _b ... made by import_exports.py) that has an appointment
date in "Data Exports\\benchmark.json", re-scores it at every month-end BEFORE the appointment, using only
the figures that existed then, exactly as Vyta would have reported them (score.score_month, steady bands
included). It shows how many months of warning Vyta would have given.

Run it after every change to the scoring (scorecard.json, score.py) to check Vyta still catches what it
caught before. The previous run is kept in "Data Exports\\benchmark_results.json" and changes are shown.

benchmark.json (in Data Exports, never committed) looks like:
    {"appointments": {"A": "2026-09-28", "B": "2026-06-17"}}
"""

import contextlib
import io
import json
import sys
from datetime import date
from pathlib import Path

import paths
import score

SOURCE = paths.EXPORTS
SETTINGS = SOURCE / "benchmark.json"
RESULTS = SOURCE / "benchmark_results.json"
FLAGGED = ("Moderate", "High")


def months_before(month, when):
    return (when.year - month.year) * 12 + when.month - month.month


def check(letter, when, cfg, wording):
    folder = paths.imported(letter)
    if not (folder / "model" / "monthly_summary.csv").exists():
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        d = score.load_data(folder, cfg)
    history = []
    for i, m in enumerate(d["months"]):
        if m["month"] >= when:
            break
        with contextlib.redirect_stdout(io.StringIO()):
            r = score.score_month(d, cfg, wording, i)
        history.append({"month": m["month"].isoformat(), "distress": round(r["scores"]["distress"][0] or 0),
                        "band": r["bands"]["distress"], "viability": round(r["scores"]["viability"][0] or 0),
                        "vband": r["bands"]["viability"], "pathway": r["pathway_label"],
                        "confidence": r["confidence"]["level"],
                        "applied": [n[9:] for n in r["override_notes"] if n.startswith("APPLIED")]})
    if not history:
        return None
    first = lambda bands: next((h for h in history if h["band"] in bands), None)
    streak = None
    for h in reversed(history):
        if h["band"] not in FLAGGED:
            break
        streak = h
    lead = lambda h: months_before(date.fromisoformat(h["month"]), when) if h else None
    return {"appointed": when.isoformat(), "from": history[0]["month"], "history": history,
            "first_flagged": lead(first(FLAGGED)), "first_high": lead(first(("High",))),
            "unbroken_flagged": lead(streak), "last": history[-1]}


def fmt_lead(n):
    return "never" if n is None else f"{n} mths"


def main(args):
    if not SETTINGS.exists():
        sys.exit(f'[STOPPED] Can\'t find {SETTINGS}. Add the appointment dates, e.g. {{"appointments": {{"A": "2026-09-28"}}}}')
    appointments = json.loads(SETTINGS.read_text())["appointments"]
    previous = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    cfg, wording = score.load_config(), score.load_wording()

    results = {}
    for letter, when in sorted(appointments.items()):
        res = check(letter, date.fromisoformat(when), cfg, wording)
        if res:
            results[letter] = res

    print("Early-warning benchmark (each month scored with only the figures available then)\n")
    print(f"{'':3} {'Appointed':11} {'Flagged since':14} {'First High':11} {'Unbroken':10} Last month-end before appointment")
    caught = 0
    for letter, r in results.items():
        last = r["last"]
        ok = last["band"] == "High"
        caught += ok
        print(f"{letter:3} {r['appointed']:11} {fmt_lead(r['first_flagged']):14} {fmt_lead(r['first_high']):11} "
              f"{fmt_lead(r['unbroken_flagged']):10} {'OK ' if ok else 'MISS'} {last['month'][:7]}: Distress "
              f"{last['distress']} {last['band']}, {last['pathway']} [{last['confidence']} confidence]")
        before = previous.get(letter)
        if before:
            changes = [f"{k} {fmt_lead(before.get(k))} -> {fmt_lead(r[k])}"
                       for k in ("first_flagged", "first_high", "unbroken_flagged") if before.get(k) != r[k]]
            if before["last"]["band"] != last["band"]:
                changes.append(f"last band {before['last']['band']} -> {last['band']}")
            if changes:
                print(f"    changed since last run: {'; '.join(changes)}")
        if last["applied"]:
            print(f"    override: {'; '.join(last['applied'])}")
        if "--months" in args:
            print("    " + " ".join(f"{h['month'][2:7]}:{h['distress']}{h['band'][0]}" for h in r["history"]))
    print(f"\nHigh distress at the last month-end before appointment: {caught} of {len(results)}")
    RESULTS.write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "history"} for k, v in results.items()},
                                  indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
