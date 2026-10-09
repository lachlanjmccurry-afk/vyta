"""
VYTA - Automatic data refresh
------------------------------
Run with:   py sync.py                 (Xero: refresh the login, pull, rebuild, score, save a snapshot)
       or:  py sync.py data_healthy    (test folder: rebuild, score and snapshot from its own raw files;
                                        Xero is only ever contacted for the  data  folder)

Runs every day at 7am through Windows Task Scheduler (task "Vyta daily sync"), and when you press
Refresh now in the dashboard.

Steps:
  1. Refresh the Xero connection (keeps the login alive - Xero drops it after 60 days unused) and
     check Xero still lets Vyta see the business (its Demo Company disconnects about every 28 days)
  2. Pull 12 months of data into a temporary folder  <folder>\\_sync\\raw
  3. Rebuild the model and score it there
  4. Only if every step worked: copy the new files over  <folder>\\raw  and  <folder>\\model
  5. Save a dated snapshot of both scores and every indicator's result in  <folder>\\history\\
If anything fails, the existing data is left exactly as it was.

Every run is written to  <folder>\\sync_log.txt  (newest at the bottom).
Read-only towards Xero. Never prints the contents of .env or tokens.json.
"""

import contextlib
import io
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
XERO_FOLDER = "data"
STAGE = "_sync"
LOCK = "_sync.lock"
LOG = "sync_log.txt"
CONNECTIONS_URL = "https://api.xero.com/connections"
LOG_KEEP_LINES = 5000
STALE_LOCK_SECONDS = 30 * 60   # a lock older than this was left by a run that crashed


class SyncFailed(Exception):
    pass


class Log:
    """Short progress lines go to the screen and the log; each step's own output goes to the log only."""

    def __init__(self, path):
        self.path = path
        self.lines = []

    def say(self, text):
        print(text)
        self.lines.append(text)

    def detail(self, text):
        self.lines.extend("      " + line for line in text.strip().splitlines())

    def save(self):
        old = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        new = old + [f"===== {datetime.now():%Y-%m-%d %H:%M:%S} =====", *self.lines, ""]
        self.path.write_text("\n".join(new[-LOG_KEEP_LINES:]) + "\n", encoding="utf-8")


@contextlib.contextmanager
def argv(*args):
    saved = sys.argv
    sys.argv = list(args)
    try:
        yield
    finally:
        sys.argv = saved


def step(log, title, fn, *args):
    """Run one step with its output captured. A [STOPPED] message or crash becomes SyncFailed."""
    log.say(f"  {title}...")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            fn(*args)
    except SystemExit:
        stopped = [l for l in out.getvalue().splitlines() if "[STOPPED]" in l]
        reason = stopped[-1].replace("[STOPPED]", "").strip() if stopped else "it stopped without a reason"
        raise SyncFailed(f"{title} failed: {reason}")
    except SyncFailed:
        raise
    except Exception as e:
        raise SyncFailed(f"{title} failed: {type(e).__name__}: {e}")
    finally:
        log.detail(out.getvalue())


# ---------- where the raw files come from ----------

def refresh_login():
    import pull_data
    if not pull_data.CLIENT_ID or not pull_data.CLIENT_SECRET:
        pull_data.stop("Your .env file is missing the Client ID or secret.")
    pull_data.refresh(pull_data.load_tokens())


def check_connection():
    """Xero can drop the link to a business while the login itself still works (the Demo Company is
    reset about every 28 days). Every pull would then fail with 403, so check first and say why."""
    import pull_data
    import requests
    tokens = pull_data.load_tokens()
    resp = requests.get(CONNECTIONS_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"},
                        timeout=30)
    if not resp.ok:
        pull_data.stop(f"Couldn't check the Xero connection ({resp.status_code}). Run  py connect_xero.py  again.")
    if tokens.get("tenant_id") not in {c.get("tenantId") for c in resp.json()}:
        pull_data.stop(f"Xero is no longer connected to {tokens.get('tenant_name', 'the business')} (Xero resets "
                       "its Demo Company about every 28 days, which disconnects it). Run  py connect_xero.py  "
                       "to reconnect, then refresh again.")


def pull_from_xero(raw):
    import pull_data
    pull_data.OUT_DIR = raw
    with argv("pull_data.py"):
        pull_data.main()


def xero_steps(base, raw):
    return [("Refreshing the Xero connection", refresh_login),
            ("Checking Xero can still see the business", check_connection),
            ("Pulling 12 months of data from Xero (read-only)", pull_from_xero, raw)]


def copy_steps(base, raw):
    return [("Copying the saved raw files (Xero isn't used for this folder)", shutil.copytree, base / "raw", raw)]


def default_fetch(base):
    """Only the data folder is connected to Xero; test folders are rebuilt from their saved files."""
    return xero_steps if Path(base).name == XERO_FOLDER else copy_steps


def check_pull(raw):
    summary = raw / "summary.txt"
    if not summary.exists():
        raise SyncFailed("The pull didn't finish (no summary.txt). Your existing data has been kept.")
    failed = [l.split(":")[0] for l in summary.read_text().splitlines() if "FAILED" in l]
    if failed:
        raise SyncFailed(f"Xero didn't send everything ({', '.join(failed)} failed). "
                         "Your existing data has been kept; it will try again next time.")


# ---------- building, scoring and swapping in ----------

def build(stage):
    import build_model
    with argv("build_model.py", str(stage)):
        build_model.main()


def score_folder(stage):
    import score
    with argv("score.py", str(stage)):
        score.main()


def install(stage, base):
    """Copy the new raw and model files over the old ones. Checks first that none of the old files is
    open in Excel, so it never stops half-way."""
    pairs = [(f, base / sub / f.name) for sub in ("raw", "model") for f in sorted((stage / sub).iterdir())]
    for _, target in pairs:
        if target.exists():
            try:
                os.replace(target, target)
            except PermissionError:
                raise SyncFailed(f"{target.name} is open (probably in Excel). Close it and refresh again. "
                                 "Your existing data has been kept.")
    for src, target in pairs:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def take_lock(base):
    lock = base / LOCK
    if lock.exists() and time.time() - lock.stat().st_mtime < STALE_LOCK_SECONDS:
        raise SyncFailed("Another refresh is already running. Try again in a few minutes.")
    lock.write_text(f"Started {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    return lock


def run(base, fetch=None):
    """Refresh one data folder. Returns (worked, message). fetch(base, raw) gives the steps that put
    raw files in  raw  (default: Xero for the data folder, a copy of the saved files otherwise)."""
    import snapshots

    base = Path(base)
    fetch = fetch or default_fetch(base)
    log = Log(base / LOG) if base.exists() else None
    if log is None:
        return False, f"[STOPPED] Can't find the folder {base}."
    stage = base / STAGE
    lock = None
    log.say(f"Refreshing {base}")
    try:
        lock = take_lock(base)
        if stage.exists():
            shutil.rmtree(stage)
        raw = stage / "raw"
        for title, fn, *args in fetch(base, raw):
            step(log, title, fn, *args)
        check_pull(raw)
        step(log, "Building the model", build, stage)
        step(log, "Scoring", score_folder, stage)
        log.say("  Saving the new files...")
        install(stage, base)
        log.say("  Saving a snapshot for the History page...")
        snap, path = snapshots.take(base)
        log.detail(f"Snapshot: {path}")
        message = (f"[DONE] {snap['org']} updated. Distress {snapshots.shown(snap['distress'])}, "
                   f"Viability {snapshots.shown(snap['viability'])}.")
        log.say(message)
        return True, message
    except SyncFailed as e:
        message = f"[STOPPED] {e}"
        log.say(message)
        return False, message
    except Exception as e:
        message = f"[STOPPED] Something unexpected went wrong: {type(e).__name__}: {e}"
        log.say(message)
        return False, message
    finally:
        if lock is not None:            # never tidy up after a different run that holds the lock
            shutil.rmtree(stage, ignore_errors=True)
            lock.unlink(missing_ok=True)
        log.save()


def main():
    os.chdir(HERE)          # Task Scheduler starts us elsewhere; the scripts expect to be in the project folder
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(XERO_FOLDER)
    worked, _ = run(base)
    if worked:
        print(f"\nLog: {(base / LOG).resolve()}\nNext: open the dashboard with  py -m streamlit run dashboard.py")
    sys.exit(0 if worked else 1)


if __name__ == "__main__":
    main()
