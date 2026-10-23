# Vyta

Early-warning tool for Australian small businesses. It reads a business's Xero file (read-only), scores
**Distress** (how serious is it) and **Viability** (is it worth saving), and shows the warning signs behind them.

## Everyday commands

Open Command Prompt in this folder and type one of these. They also work from any other folder with
`py C:\Users\LMcCurry\vyta\vyta.py <command>`.

| To do this | Type |
|---|---|
| Open the dashboard | `py vyta.py dashboard` |
| Update the Xero business now (also runs by itself at 7am) | `py vyta.py refresh` |
| Sign in to Xero again (when the refresh says the connection expired) | `py vyta.py connect` |
| Check everything still works | `py vyta.py test` |
| See how early Vyta warned on the closed jobs | `py vyta.py benchmark` |
| Import Xero Excel exports from `businesses\Data Exports` | `py vyta.py import` |
| Save a PDF report | `py vyta.py report businesses\test_stressed` |
| See every command | `py vyta.py` |

If `py` uses the wrong Python, use `.venv\Scripts\python.exe vyta.py <command>` instead.

## What's in each folder

| Folder | What it's for | Edit it? |
|---|---|---|
| `settings\` | `scorecard.json` (warning levels, weights, bands), `wording.json` (every sentence the app shows), `firms.json` (adviser listings) | **Yes**, this is where you change how Vyta scores and what it says |
| `businesses\` | One folder per business: `xero` (your live Xero data), `test_healthy` and `test_stressed` (made up), `business_a`… (imported, anonymised). Drop Excel exports into `Data Exports`. **Private: never uploaded to GitHub** | No, made by the commands |
| `docs\` | The scorecard spec (`SCORECARD.md`, the Excel workbook), command cheat sheet, notes, session summaries, website design references | Yes |
| `engine\` | The scoring: reading the reports, the 23 indicators, cash, trends, what-if, PDF report | Code |
| `app\` | The dashboard's look and its pages (`app\views`) | Code |
| `xero\` | Connecting to Xero, downloading the data, the daily refresh | Code |
| `tools\` | Make test data, import Excel exports, the benchmark, logo files | Code |
| `tests\` | Automated checks (`py vyta.py test`) | Code |
| `assets\` | Logos | |

## Files at the top

| File | Why it's here |
|---|---|
| `vyta.py` | The one command for everything above |
| `dashboard.py` | Starts the dashboard |
| `demo_app.py`, `requirements.txt`, `.streamlit\`, `.devcontainer\` | The online demo on Streamlit Cloud needs these at the top level, so **don't move them** |
| `CLAUDE.md`, `AGENTS.md` | Instructions for Claude Code and Codex |
| `.env`, `tokens.json` | **Secrets** for the Xero connection. Never share or upload them |

## Online demo

https://demoapppy-djuv3vyyz3ynzokj86m8ix.streamlit.app/ runs `demo_app.py` with the two made-up
businesses only. It never connects to Xero and never sees anything in `businesses\`.
