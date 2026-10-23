"""
VYTA - Score history
---------------------
Each time sync.py refreshes a data folder it saves a snapshot of both scores and every indicator's
result in  <folder>\\history\\YYYY-MM-DD_HHMMSS.json (plus _2, _3... if two land in the same second). This file writes and reads those snapshots, and
works out what changed between two of them. Used by sync.py and the dashboard's History page and
"Last updated" line. Never contacts Xero.
"""

import contextlib
import io
import json
import re
from datetime import date, datetime
from pathlib import Path

import score

HISTORY = "history"
NOT_ASSESSED = "Not assessed"


def take(base, when=None):
    """Score the folder and save a snapshot. Returns (snapshot, path)."""
    base = Path(base)
    with contextlib.redirect_stdout(io.StringIO()):
        run = score.compute(base)
    when = when or datetime.now()
    snap = from_run(run, when)
    folder = base / HISTORY
    folder.mkdir(exist_ok=True)
    path = folder / f"{when:%Y-%m-%d_%H%M%S}.json"
    n = 1
    while path.exists():            # two refreshes in the same second keep both snapshots
        n += 1
        path = folder / f"{when:%Y-%m-%d_%H%M%S}_{n}.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return snap, path


def from_run(run, when):
    d = run["d"]
    return {
        "taken_at": when.isoformat(timespec="seconds"),
        "org": d["org"],
        "period_end": d["months"][-1]["month"].isoformat(),
        "data_as_at": d["as_at"].isoformat(),
        **{kind: {"score": None if run["scores"][kind][0] is None else round(run["scores"][kind][0], 1),
                  "band": run["bands"][kind]} for kind in ("distress", "viability")},
        "pathway": run["pathway"],
        "confidence": run["confidence"]["level"],
        "indicators": [{"id": r["ind"]["id"], "name": score.short_name(r["ind"]), "score": r["ind"]["score"],
                        "rating": r["rating"], "display": r.get("display", "")} for r in run["results"]],
    }


def load(base):
    """Every snapshot for a folder, oldest first. Files that can't be read are skipped."""
    snaps = []
    for path in sorted((Path(base) / HISTORY).glob("*.json")):
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
            snap["_taken"] = datetime.fromisoformat(snap["taken_at"])
            snaps.append(snap)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(snaps, key=lambda s: s["_taken"])


def last_updated(base):
    """When the data was last refreshed: the newest snapshot's time, or failing that the 'Pulled on'
    date in raw\\summary.txt (a date only). None if neither exists."""
    snaps = load(base)
    if snaps:
        return snaps[-1]["_taken"]
    try:
        found = re.search(r"Pulled on:\s*(\d{4}-\d{2}-\d{2})", (Path(base) / "raw" / "summary.txt").read_text())
    except OSError:
        return None
    return date.fromisoformat(found.group(1)) if found else None


def when_text(moment):
    """'9 Oct 2026, 7:02am', or just '9 Oct 2026' when only the date is known."""
    if moment is None:
        return None
    text = f"{moment.day} {moment:%b %Y}"
    if isinstance(moment, datetime):
        text += f", {moment.hour % 12 or 12}:{moment:%M}{'am' if moment.hour < 12 else 'pm'}"
    return text


def colour(rating):
    return rating if rating in ("Red", "Amber", "Green") else NOT_ASSESSED


def changes(before, after):
    """Indicators whose colour changed between two snapshots (Not assessed counts as a colour)."""
    old = {i["id"]: i for i in before["indicators"]}
    out = []
    for ind in after["indicators"]:
        prev = old.get(ind["id"])
        if prev is None or colour(prev["rating"]) != colour(ind["rating"]):
            out.append({"id": ind["id"], "name": ind["name"], "score": ind["score"],
                        "before": colour(prev["rating"]) if prev else None, "after": colour(ind["rating"]),
                        "display_before": prev.get("display", "") if prev else "", "display_after": ind["display"]})
    return out


def shown(part):
    """'72.0 (High)' for a snapshot's distress or viability entry."""
    return f"{'n/a' if part['score'] is None else format(part['score'], '.1f')} ({part['band']})"
