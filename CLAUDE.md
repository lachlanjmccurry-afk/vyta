# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Vyta is a read-only tool. It connects to Xero and scores Australian small businesses for financial distress and insolvency risk. The scoring is based on ASIC v Plymin indicators plus ATO rules. Development currently uses Xero's "Demo Company (AU)".

The owner is not a developer. Explain what you're doing in plain English, and **ask before doing anything risky** (deleting or overwriting files, installing things outside the `.venv`, or anything that touches Xero).

## Hard rules

- **Read-only towards Xero.** Never write anything back to Xero. Never add write scopes (only `*.read` scopes are allowed) and never call an API with POST, PUT or DELETE, other than the OAuth token endpoint.
- **Never open, print, copy or read `.env` or `tokens.json`.** They hold secrets. The scripts load them; you don't need to see them.
- **Environment:** Windows, Command Prompt, existing `.venv`. Run Python with `py` (for example, `py build_model.py`). Install packages into the `.venv` only.

## Git

- Private repo: https://github.com/lachlanjmccurry-afk/vyta (branch `main`). Commits use the GitHub noreply address (set in this repo's own git config, not globally).
- Git and the GitHub CLI (`gh`) were installed with winget for the current user only. A shell opened before that install may need its PATH refreshed.
- `.gitignore` excludes `.env`, `tokens.json`, anything named like a token, secret or credential, `.venv`, and all `data\` and `data_*\` folders (Xero downloads and everything made from them). **Never commit business data or secrets.** Run `git status` before every commit, and check that nothing under `data` is staged.
- Ask before pushing.

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
| `dashboard.py` | Done | Streamlit dashboard: `py -m streamlit run dashboard.py` (opens http://localhost:8501). Entry point only: CSS, logo and the client picker in the sidebar (any folder with `model\monthly_summary.csv`, widget key `folder`), then it calls `score.compute()` once (stored in `st.session_state["vy_run"]`, read by `ui.current_run()`) and runs `st.navigation(position="top")` over the pages in `views\`. Always matches `score.py`. Theme, serif headings and the hidden Deploy button/menu are set in `.streamlit\config.toml`; traffic-light colours are used only on results and on the threshold zones. Read-only; writes no files. **Don't take screenshots** (blocked on this laptop; the owner checks the dashboard). Check it with `test_dashboard.py` (`streamlit.testing.v1.AppTest`), and stop any server you start |
| `views\*.py` | Done | The four pages. **overview** is the adviser's memo: verdict (`score.verdict`), score cards, data confidence, top 3 issues (`score.top_issues`: weight × severity, Red counts double), what's working, pathway, and Export PDF. **cash** shows the "Where has the cash gone?" waterfall plus the month-end cash line. **indicators** has one row per indicator (Streamlit columns in a `vyrows-*` keyed container) with a sparkline; Details opens an `st.dialog` with the trend chart, explanation and figures used (`facts`). **owner_questions** shows the questions from `scorecard.json`, the indicators waiting on the owner, and the override status. Page text lives in `wording.json` → `cash_page`, `indicators_page`, `owner_questions_page` |
| `ui.py` | Done | Shared dashboard pieces: CSS with one spacing scale (`--s1`…`--s7`), logo mark, result pills, masthead, headings, `chart()` (always `theme=None` so Streamlit doesn't recolour Plotly) |
| `charts.py` | Done | Plotly `vyta` template (navy/warm grey, no default colours), plus `sparkline`, `trend_chart` (Amber/Red zones follow `direction`), `waterfall` and `cash_line` |
| `trends.py` | Done | `indicator_series(d, ind)` re-runs the `score.CALCS` function on data cut off at each of the last 12 month-ends. Rule-based months are gaps. `NO_TREND` lists the snapshot-only indicators (D8, D10). The latest point always equals the scored value (tested) |
| `cashflow.py` | Done | `cash_bridge(d)`: opening cash → operating profit (net profit), ATO movement, debt movement (loans only via `score.bank_debt`; overdraft is already in cash), change in debtors, change in creditors, other (the balancing figure) → closing. Opening is the month-end before the 12-month window, or the first month-end when only 12 months exist. Tested in `test_cashflow.py` |
| `report_pdf.py` | Done | `build_pdf(run)` → PDF bytes (ReportLab), used by the dashboard export. `py report_pdf.py [folder]` saves `<folder>\model\vyta_report.pdf`. Colours (`RATING_STYLE`, `BAND_RATING`) are shared with the dashboard |
| `requirements.txt` | Done | Pinned packages for the `.venv` (Python 3.14) |
| `make_test_data.py` | Done | Writes two **synthetic** 24-month businesses in Xero's JSON format to `data_healthy\raw` and `data_stressed\raw` (organisation names start with "TEST"). Never touches `data\` or Xero. Use these to check the engine scores at both ends |

The pipeline runs in order: `connect_xero.py` (once) → `pull_data.py` → `build_model.py` → `score.py`. `build_model.py` and `score.py` both take an optional data folder (default `data`), e.g. `py build_model.py data_stressed` and then `py score.py data_stressed`. `build_model.py` works out the number of months from the P&L report's header row, so it handles 12 or 24 months.

**Tests:** `py -m unittest test_score test_cashflow test_trends test_dashboard -v` (standard library `unittest`; pytest isn't installed). `test_dashboard` opens every page for every built data folder. To run one test: `py -m unittest test_score.TestThresholds.test_D7`. `test_score.py` builds a small made-up business for each indicator that lands on either side of the `scorecard.json` thresholds, so the tests follow threshold edits automatically. When adding an indicator, add a builder to `BUILDERS`; `test_every_indicator_has_a_threshold_test` fails until you do. The `TestBusinesses` tests are skipped unless `data_healthy` and `data_stressed` have been built.

Expected results (as of 9 Oct 2026):
- Healthy test business → Low/Strong ("Healthy"), High confidence.
- Demo Company → High/Uncertain ("Urgent advice"), **Low** confidence (3 of 12 months active). Its V2 and V3 are not assessed because it records no cost of sales.
- Stressed test business → High/Weak ("Likely liquidation"), High confidence.

Scoring rules added 9 Oct 2026:
- V2/V3 are "Not assessed" when cost of sales is zero (a 100% gross margin would be meaningless).
- Data confidence is High at 12 active months, Medium at 6–11 and Low under 6. The cut-offs are in `scorecard.json` → `data_confidence`; the wording is in `wording.json` → `data_confidence`.
- Negative ATO balances are worded as credits (`ato_balance()` in `score.py`).
- Tables use only `short_name` labels (max 20 characters) and short `display` values or reasons (max 18 characters, enforced by `TestTableLabels`). Full names and reasons go in the explanations. If a change to the scoring moves these unexpectedly, investigate before shipping it.

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
