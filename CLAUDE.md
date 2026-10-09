# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Vyta is a read-only tool. It connects to Xero and scores Australian small businesses for financial distress and insolvency risk. The scoring is based on ASIC v Plymin indicators plus ATO rules. Development currently uses Xero's "Demo Company (AU)".

The owner is not a developer. Explain what you're doing in plain English, and **ask before doing anything risky** (deleting or overwriting files, installing things outside the `.venv`, or anything that touches Xero).

## Hard rules

- **Read-only towards Xero.** Never write anything back to Xero. Never add write scopes (only `*.read` scopes are allowed) and never call an API with POST, PUT or DELETE, other than the OAuth token endpoint.
- **Never open, print, copy or read `.env` or `tokens.json`.** They hold secrets. The scripts load them; you don't need to see them.
- **Environment:** Windows, Command Prompt, existing `.venv`. Run Python with `py` (for example, `py build_model.py`). Install packages into the `.venv` only.

## File map

| File | Status | Purpose |
|---|---|---|
| `connect_xero.py` | Done, working | One-off Xero OAuth login → `tokens.json` |
| `pull_data.py` | Done, working | `py pull_data.py [YYYY-MM]` → 12 months of raw Xero data in `data\raw\*.json` + `summary.txt` |
| `build_model.py` | Written | `data\raw` → `data\model\vyta_model.xlsx` (for people to read) + `data\model\monthly_summary.csv` (input to the scoring engine) |
| `vyta_scorecard_v2.xlsx` + `SCORECARD.md` | Owner's spec (v2, 9 Oct 2026) | Replaces v1. **Two scores**: Distress (13 indicators, D1–D13, higher = worse) and Viability (8 indicators, V1–V8, higher = better). Also holds the bands, the statutory-demand override, a 3×3 Distress × Viability outcome matrix, 10 owner questions and open items. Thresholds are working assumptions |
| `scorecard.json` | Done | Settings file for all 21 indicators (thresholds, weights, edge-case rules), bands, overrides, outcome matrix and owner questions. It was created by hand from the v2 spreadsheet; if the spreadsheet changes, re-check the values. Percentages are stored as decimals |
| `score.py` | Done | `py score.py [data folder]` (default `data`). One calculation function per indicator, listed in `CALCS`; it reuses `build_model.py` helpers. Edge-case rules (divide by zero, etc.) come from `scorecard.json`. Unpaid invoice ageing uses the "Pulled on" date in `summary.txt`. Reads `monthly_summary.csv` + `data\raw` + `scorecard.json`, rates each indicator Green/Amber/Red, works out both 0–100 scores, bands and the outcome-matrix pathway, applies the overrides, and writes `data\model\vyta_score.xlsx`. Indicators that need owner input or data Vyta doesn't have show as "Not assessed" with a reason and are left out of the score (not counted as zero) |

| `wording.json` | Done | All the plain-English report text, editable by the owner: a Green ("going well + keep doing"), Amber and Red sentence per indicator, optional special-case sentences such as `red_overdrawn` or `green_no_debt` (picked by the `case=` a calc function returns), and a one-line summary for each of the 9 outcome-matrix pathways. `{placeholders}` are filled by `score.explain()` from the standard fields plus each calc's `facts`. Unknown placeholders are reported, not fatal. **Keep wording out of the code** |
| `dashboard.py` | Done | Streamlit dashboard: `py -m streamlit run dashboard.py` (opens http://localhost:8501). The sidebar picks any folder that has `model\monthly_summary.csv`. It calls `score.compute()`, so it always matches `score.py`. It shows score cards, the pathway with its summary, traffic-light tables, explanations ("Needs attention" / "Going well" tabs) and a PDF export button. Read-only; writes no files. Check it with `streamlit.testing.v1.AppTest` (headless Edge screenshots are blocked on this machine) |
| `report_pdf.py` | Done | `build_pdf(run)` → PDF bytes (ReportLab), used by the dashboard export. `py report_pdf.py [folder]` saves `<folder>\model\vyta_report.pdf`. Colours (`RATING_STYLE`, `BAND_RATING`) are shared with the dashboard |
| `requirements.txt` | Done | Pinned packages for the `.venv` (Python 3.14) |
| `make_test_data.py` | Done | Writes two **synthetic** 24-month businesses in Xero's JSON format to `data_healthy\raw` and `data_stressed\raw` (organisation names start with "TEST"). Never touches `data\` or Xero. Use these to check the engine scores at both ends |

The pipeline runs in order: `connect_xero.py` (once) → `pull_data.py` → `build_model.py` → `score.py`. `build_model.py` and `score.py` both take an optional data folder (default `data`), e.g. `py build_model.py data_stressed` and then `py score.py data_stressed`. `build_model.py` works out the number of months from the P&L report's header row, so it handles 12 or 24 months.

**Tests:** `py -m unittest test_score -v` (standard library `unittest`; pytest isn't installed). To run one test: `py -m unittest test_score.TestThresholds.test_D7`. `test_score.py` builds a small made-up business for each indicator that lands on either side of the `scorecard.json` thresholds, so the tests follow threshold edits automatically. When adding an indicator, add a builder to `BUILDERS`; `test_every_indicator_has_a_threshold_test` fails until you do. The `TestBusinesses` tests are skipped unless `data_healthy` and `data_stressed` have been built.

Expected test results (as of 9 Oct 2026): healthy → Low/Strong ("Healthy"), Demo Company → High/Strong ("Restructure candidate"), stressed → High/Weak ("Likely liquidation"). If a change to the scoring moves these unexpectedly, investigate before shipping it.

## How the pieces fit together

- **Auth:** `connect_xero.py` runs a local callback server on the port in `XERO_REDIRECT_URI` (default 8080) and picks the tenant whose name contains "demo". `pull_data.py` refreshes tokens automatically. Xero rotates the refresh token every time, so it's saved straight away.
- **Rate limiting:** every call sleeps 1.1s (Xero allows 60 calls a minute), waits out a 429 using `Retry-After`, and pages list endpoints 100 records at a time. A failed endpoint is logged as FAILED in `summary.txt`; the run doesn't stop.
- **`data\raw\summary.txt` is a contract:** `build_model.py` reads the period end date from it with the regex `ending (\d{4}-\d{2}-\d{2})`.
- **`build_model.py`:**
  - `flatten()` turns Xero's nested reports into flat rows. Report columns are **newest month first**.
  - Metrics are found by regex-matching Xero's section and line labels in `build_monthly()`. When figures look wrong, check those regexes first.
  - ATO lines are matched dynamically through `ATO_PATTERN`. Each becomes its own `ato: <name>` CSV column, so the CSV columns change with the data.
  - `current_assets` = bank total + Xero's "Total Current Assets", because Xero lists bank separately.
  - Self-checks: P&L ties and balance sheet ties (should be $0). A mismatch means a line was missed.
  - The aged invoice snapshot uses **today's** unpaid balances, not month-end balances.
- **Demo data caveat:** only Jul–Sep 2026 have activity. Earlier months show flat opening balances.

## Conventions

- User-facing script output is plain language. Fatal errors go through `stop()` → `[STOPPED] <what to do next>`, exit 1. Success ends with `[DONE]` and the next command.
- `build_model.py` fails with a PermissionError if `vyta_model.xlsx` is open in Excel; close Excel and run it again.
