# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Vyta is a read-only tool. It connects to Xero and scores Australian small businesses for financial distress and insolvency risk. The scoring is based on ASIC v Plymin indicators plus ATO rules. Development currently uses Xero's "Demo Company (AU)".

The owner is not a developer. Explain what you're doing in plain English, and **ask before doing anything risky** (deleting or overwriting files, installing things outside the `.venv`, or anything that touches Xero).

## Folder layout (tidied 23 Oct 2026)

Run everything through **`vyta.py`** from the vyta folder (`py vyta.py` lists commands: dashboard, demo, refresh,
connect, test, benchmark, import, test-data, report, logos, `run <script> [args]`). It puts the code folders on
`sys.path` and works from the vyta folder, so modules still import each other by plain name (`import score`).

| Folder | Contents |
|---|---|
| `engine\` | score, build_model, cashflow, trends, whatif, snapshots, firms, report_pdf, **paths.py** (every location) |
| `app\` | ui, charts, demo, `views\` (dashboard pages) |
| `xero\` | connect_xero, pull_data, sync |
| `tools\` | make_test_data, import_exports, benchmark, make_logo_assets |
| `tests\` | test_*.py; each starts with `import _setup` (`tests\_setup.py`). Run `py vyta.py test` |
| `settings\` | scorecard.json, wording.json, firms.json |
| `businesses\` | **gitignored**: `xero\` (live Xero, was `data\`), `test_healthy\`, `test_stressed\`, `business_a\`…, `Data Exports\` |
| `docs\` | SCORECARD.md, vyta_scorecard_v2.xlsx, plus the owner's own docs (untracked: keep them out of the public repo) |

- **Never hard-code a location**: use `paths.py` (`paths.XERO`, `paths.TEST_HEALTHY`, `paths.SCORECARD`, `paths.EXPORTS`, `paths.imported("A")`). Business folders are identified by their posix path, e.g. `businesses/test_healthy`.
- Must stay at the top: `dashboard.py`, `demo_app.py`, `requirements.txt`, `.streamlit\`, `.devcontainer\` (Streamlit Cloud). Both apps start with a 3-line block that imports `engine\paths.py` and calls `paths.setup()`.
- Task Scheduler "Vyta daily sync" runs `.venv\Scripts\pythonw.exe "C:\Users\LMcCurry\vyta\vyta.py" refresh` in the vyta folder.
- The rest of this file was written before the tidy-up: read `data\` as `businesses\xero\`, `data_healthy`/`data_stressed` as `businesses\test_healthy`/`test_stressed`, `data_business_a` as `businesses\business_a`, and `py <script>.py` as `py vyta.py run <script>`.

## Hard rules

- **Read-only towards Xero.** Never write anything back to Xero. Never add write scopes (only `*.read` scopes are allowed) and never call an API with POST, PUT or DELETE, other than the OAuth token endpoint.
- **Never open, print, copy or read `.env` or `tokens.json`.** They hold secrets. The scripts load them; you don't need to see them.
- **Environment:** Windows, Command Prompt, existing `.venv`. Run Python with `py` (for example, `py build_model.py`). Install packages into the `.venv` only.

## Git

- Private repo: https://github.com/lachlanjmccurry-afk/vyta (branch `main`). Commits use the GitHub noreply address (set in this repo's own git config, not globally).
- Git and the GitHub CLI (`gh`) were installed with winget for the current user only. A shell opened before that install may need its PATH refreshed.
- `.gitignore` excludes `.env`, `tokens.json`, anything named like a token, secret or credential, `.venv`, and all `data\` and `data_*\` folders (Xero downloads and everything made from them). **Never commit business data or secrets.** Run `git status` before every commit, and check that nothing under `data` is staged.
- After finishing and testing a piece of work, commit and push to main without asking. Before every commit, run git status and confirm nothing from the data folders, .env, tokens or credentials is staged. Never force push.

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
| `dashboard.py` | Done | Streamlit dashboard: `py -m streamlit run dashboard.py` (opens http://localhost:8501). Entry point only. It sets up the CSS, then `st.navigation(position="hidden")`, because `ui.sidebar` draws its own navy sidebar: logo, `st.page_link`s with the current page in a `nav-on-*` keyed container, and a "Connected to Xero" box. The fixed white top bar comes from `ui.topbar`/`ui.fill_topbar`: initials badge, business picker (any folder with `model\monthly_summary.csv`, widget key `folder`), period, "Synced daily from Xero" + Last updated, Refresh now (key `refresh`), and Export PDF (key `export`; "Get listed" link on the Get help page). It calls `score.compute()` once (stored in `st.session_state["vy_run"]`, read by `ui.current_run()`). Main nav: Overview, Details, Get help; "More tools": Cash, What if?, History, Owner questions. Theme (Plus Jakarta Sans, navy sidebar via `[theme.sidebar]`) is in `.streamlit\config.toml`. The design follows the owner's three mock-up screenshots (Overview, Details, Get help); traffic-light colours only on results. **Don't take screenshots** (blocked on this laptop; the owner checks the dashboard). Check it with `test_dashboard.py` (`streamlit.testing.v1.AppTest`), and stop any server you start |
| `views\*.py` | Done | Seven pages. **overview**: verdict as the page title, data-confidence banner, two score cards with band bars (segments sized from `scorecard.json` bands, marker at the score), navy pathway banner (`run["pathway_label"]` + summary, link to Get help), Top 3 issues (`score.top_issues`: weight × severity, Red counts double; first sentence of each explanation) and What's working. **details**: key month-end balances (`wording.json` → `details_page.figures` maps CSV columns to labels), then a Distress/Viability `st.segmented_control` (key `details_kind`). Rows are plain HTML `<details>` (no reload); opening one shows the explanation, an inline SVG 12-month trend (`charts.svg_trend`), figures used (`facts`), weight and calculation. **get_help**: `firms.json` advisers matched by `firms.py`, `st.pills` filter (key `help_filter`), "Listed partner" tags, Contact / View profile `st.dialog`s, How listings work, and the navy "Are you an adviser?" card (anchor `#get-listed`). **history**: both scores across the snapshots (one chart per score, because they point in opposite directions), the "What changed since last time" colour changes, and every snapshot. **whatif**: sliders (session-state keys `wi_*`, Reset key `wi_reset`), before → after for both scores, bands, the pathway and the indicators that change colour (see `whatif.py`). **cash**: the "Where has the cash gone?" waterfall plus the month-end cash line. **owner_questions**: the questions from `scorecard.json`, the indicators waiting on the owner, and the override status. All page text is in `wording.json` (`shell`, `overview_page`, `details_page`, `help_page`, `cash_page`, `whatif_page`, `history_page`, `owner_questions_page`, `refresh`, `pathway_labels`) |
| `demo_app.py` + `demo.py` | Done | Online demo for reviewers on Streamlit Community Cloud (deploy with main file `demo_app.py`; try locally with `py -m streamlit run demo_app.py`). Sets `VYTA_DEMO=1` and runs `dashboard.py`. In demo mode only `data_healthy`/`data_stressed` are listed, Refresh now is hidden, and the sidebar box says "Demo version". Xero and `data\` are never touched. `demo.ensure_data()` builds the two test businesses on first start (they aren't in GitHub). **Never put real business data in the demo.** Tested in `test_demo.py` |
| `firms.json` + `firms.py` | Done | **Fictional demo** adviser listings for Get help (reserved `(0x) 5550 xxxx` phone numbers, `.example` emails; `test_firms.py` enforces this). Each firm has a `type` (filter), `serves` (pathways as `"Distress/Viability"` bands, or `"any"`), and `why` rules (shown when all listed indicators are Red/Amber; `{D5}` = that indicator's value, `{pathway}` = short name), plus `why_default`. Firms in the business's state (Xero street address) come first |
| `assets\` + `make_logo_assets.py` | Done | `assets\vyta_logo.png` is the master logo (copied from the owner's `Vyta Logo.png`). `py make_logo_assets.py` makes `vyta_logo_dark.png` (background removed, wordmark white, for the navy sidebar) and `vyta_mark.png` (the round mark, browser-tab icon) |
| `whatif.py` | Done | What if? page logic. `adjust(d, levers)` returns a copy of the business with price, volume, cost of sales and overhead changes applied to the last 12 months (extra profit added to cash and net assets so the balance sheet still balances), faster debtor collection (days of sales from debtors to cash at the latest month-end, using the D9 debtor-days formula), and an ATO plan (first of 12 instalments paid from cash at the latest month-end). `run()` scores it with `score.score_data()`, so there's no second copy of the scoring. `describe()` builds the plain-English sentence from `wording.json` → `whatif_page`. No levers gives exactly the real scores (tested in `test_whatif.py`) |
| `ui.py` | Done | Shared dashboard pieces: all the CSS (Plus Jakarta Sans from Google Fonts, one spacing scale `--s1`…`--s7`, cards are `.vy-panel` or containers keyed `card-*`), sidebar, top bar, refresh, result pills (`pill`, `band_pill`), `page_head(eyebrow, title, lead)`, `heading`, `chart()` (always `theme=None` so Streamlit doesn't recolour Plotly). HTML passed to `md()` must have **no blank lines**, otherwise Markdown takes over (and `$` amounts can turn into maths) |
| `charts.py` | Done | The palette (navy `#0F1A2A`, ink, muted, line; `ui.py` imports it) and the Plotly `vyta` template, plus `sparkline`, `svg_trend` (inline SVG for HTML rows), `trend_chart` (Amber/Red zones follow `direction`), `score_history`, `waterfall` and `cash_line` |
| `trends.py` | Done | `indicator_series(d, ind)` re-runs the `score.CALCS` function on data cut off at each of the last 12 month-ends. Rule-based months are gaps. `NO_TREND` lists the snapshot-only indicators (D8, D10). The latest point always equals the scored value (tested) |
| `cashflow.py` | Done | `cash_bridge(d)`: opening cash → operating profit (net profit), ATO movement, debt movement (loans only via `score.bank_debt`; overdraft is already in cash), change in debtors, change in creditors, other (the balancing figure) → closing. Opening is the month-end before the 12-month window, or the first month-end when only 12 months exist. Tested in `test_cashflow.py` |
| `report_pdf.py` | Done | `build_pdf(run)` → PDF bytes (ReportLab), used by the dashboard export. `py report_pdf.py [folder]` saves `<folder>\model\vyta_report.pdf`. Colours (`RATING_STYLE`, `BAND_RATING`) are shared with the dashboard |
| `requirements.txt` | Done | Pinned packages for the `.venv` (Python 3.14) |
| `sync.py` | Done | `py sync.py [folder]` (default `data`). Automatic refresh: for `data` only, refreshes the Xero login, checks the business is still connected (`/connections`; the Demo Company disconnects about every 28 days → "run `py connect_xero.py`"), then pulls. Other folders copy their own `raw` instead (never Xero). Pulls, builds and scores in `<folder>\_sync`, and only copies over `raw` + `model` if every step worked (any FAILED endpoint, crash or file open in Excel → existing data kept). Then saves a snapshot. A `_sync.lock` stops two runs overlapping. Each run is appended to `<folder>\sync_log.txt`. Ends with `[DONE]`/`[STOPPED]`; exit code 0/1 |
| `snapshots.py` | Done | Snapshots in `<folder>\history\YYYY-MM-DD_HHMMSS.json`: both scores and bands, pathway, confidence, and every indicator's rating and display value. `load`, `last_updated` (newest snapshot, otherwise the "Pulled on" date), `changes` (indicators whose colour changed; Not assessed counts as a colour) |
| `import_exports.py` + `Data Exports\` | Done | `py import_exports.py` (use `.venv\Scripts\python.exe`). Turns Xero **Excel exports** (monthly P&L, balance sheet, aged receivables/payables) in `Data Exports\` into API-shaped raw files in `data_business_a`, `_b`… then runs build_model + score. Each workbook = one business, each subfolder = one business. Names are anonymised ("Business A", "Customer 1"). Missing aged reports → D8/D10 Not assessed (`rawged_status.json`). **`Data Exports\` holds real client data: never commit, never use in the demo or website, never print names in output.** Validated 22 Oct 2026: current ratio, quick ratio and net assets match the source ratio analyses exactly |
| `make_test_data.py` | Done | Writes two **synthetic** 24-month businesses in Xero's JSON format to `data_healthy\raw` and `data_stressed\raw` (organisation names start with "TEST"). Never touches `data\` or Xero. Use these to check the engine scores at both ends |

The pipeline runs in order: `connect_xero.py` (once) → `pull_data.py` → `build_model.py` → `score.py`. `sync.py` runs the last three for you (safely) and saves a history snapshot. `build_model.py` and `score.py` both take an optional data folder (default `data`), e.g. `py build_model.py data_stressed` and then `py score.py data_stressed`. `build_model.py` works out the number of months from the P&L report's header row, so it handles 12 or 24 months.

**Daily refresh:** Windows Task Scheduler task **"Vyta daily sync"** (current user, no admin) runs `.venv\Scripts\pythonw.exe vyta.py refresh` in the project folder at 7am daily. If the laptop was off it runs at the next chance, and it is stopped after 30 minutes. To check it: look at `data\sync_log.txt`, or run `schtasks /Query /TN "Vyta daily sync" /V /FO LIST` (Last Result 0 = worked, 1 = stopped, see log). Turn it off: `schtasks /Change /TN "Vyta daily sync" /DISABLE` (`/ENABLE` to turn it back on). Remove it: `schtasks /Delete /TN "Vyta daily sync" /F`. Created with PowerShell `Register-ScheduledTask` (`-Daily -At 7am`, `-StartWhenAvailable`).

**Tests:** `py vyta.py test` (standard library `unittest`; pytest isn't installed). `test_dashboard` opens every page for every built data folder. To run one test: `py -m unittest test_score.TestThresholds.test_D7`. `test_score.py` builds a small made-up business for each indicator that lands on either side of the `scorecard.json` thresholds, so the tests follow threshold edits automatically. When adding an indicator, add a builder to `BUILDERS`; `test_every_indicator_has_a_threshold_test` fails until you do. The `TestBusinesses` tests are skipped unless `data_healthy` and `data_stressed` have been built.

Expected results (as of 9 Oct 2026):
- Healthy test business → Low/Strong ("Healthy"), High confidence.
- Demo Company → High/Uncertain ("Urgent advice"), **Low** confidence (3 of 12 months active). Its V2 and V3 are not assessed because it records no cost of sales.
- Stressed test business → High/Weak ("Likely liquidation"), High confidence.

Scoring rules added 9 Oct 2026:
- V2/V3 are "Not assessed" when cost of sales is zero (a 100% gross margin would be meaningless).
- Data confidence is High at 12 active months, Medium at 6–11 and Low under 6. The cut-offs are in `scorecard.json` → `data_confidence`; the wording is in `wording.json` → `data_confidence`.
- Negative ATO balances are worded as credits (`ato_balance()` in `score.py`).
- Tables use only `short_name` labels (max 20 characters) and short `display` values or reasons (max 18 characters, enforced by `TestTableLabels`). Full names and reasons go in the explanations. If a change to the scoring moves these unexpectedly, investigate before shipping it.

Scoring rules added 23 Oct 2026 (from the closed-job benchmark):
- **D14 Sales vs normal** and **D15 Books up to date** are *warning flags* (`"flag_only": true`, weight 0, `issue_weight` 10): they don't dilute the weighted score while Green, but rank in Top 3 issues. D15 is also Amber when total liabilities are below zero.
- **Override `stopped_trading`** (scorecard.json): D14 or D15 Red while current assets < current liabilities (or net assets < 0) → Distress High.
- **Data confidence → Low** when the books look unreliable (`score.books_warnings`: recent near-empty months, or liabilities below zero), with the reason in the banner.
- **Steady bands** (`score.score_month` / `score.steady`): a worse band shows at once; a better band only once two month-ends agree (note starts `HELD:`). `compute()` returns steadied results; `score_data()` is raw. What if? compares against `run["unsteadied"]`.
- **`benchmark.py`** re-scores each `data_business_*` at every month-end before its appointment date (`Data Exports\benchmark.json`, local only) and shows the warning lead time, with changes since the last run. **Run it after any scoring change.** 23 Oct 2026 result: High at the last month-end before appointment for 4 of 5 (A, B, C, D); E's books are unreliable (Low confidence).

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
