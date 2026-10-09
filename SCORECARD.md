# Vyta Distress Scorecard – v2

Source of truth for the scoring engine. Full workbook: `vyta_scorecard_v2.xlsx`. Updated 9 Oct 2026 with Patrick's (Elevon) feedback.

## Core design
- Two scores, both 0–100: **Distress** (higher = worse) and **Viability** (higher = better).
- Each indicator rates Green / Amber / Red. "Higher is worse" → Amber/Red when value >= threshold; "Lower is worse" → when value <= threshold.
- Distress points: Red 100, Amber 50, Green 0. Viability points: Green 100, Amber 50, Red 0.
- Score = weighted average of indicators with data. Missing data is excluded, not scored as zero.
- Bands: Distress Low <30, Moderate 30–59, High 60+. Viability Weak <40, Uncertain 40–64, Strong 65+.
- Override: unpaid statutory demand (owner input) → Distress = High.
- Keep all thresholds, weights and band cut-offs in one config file so they can be tuned per industry later.

## Distress indicators
| ID | Indicator | Calculation | Xero source | Direction | Amber | Red | Weight | Status |
|---|---|---|---|---|---|---|---|---|
| D1 | Current ratio | Current assets ÷ current liabilities | Balance Sheet report | Lower is worse | 1.2 | 1 | 8 | Rick to confirm formula |
| D2 | Quick ratio | (Cash + trade debtors) ÷ current liabilities | Balance Sheet report | Lower is worse | 1 | 0.7 | 8 | Rick to confirm formula |
| D3 | Cash runway (months) | Cash ÷ average monthly net cash outflow (last 3 months) | Bank transactions / Bank Summary | Lower is worse | 6 | 3 | 10 | Confirmed (draft threshold) |
| D4 | ATO debt: consecutive months rising | Count of consecutive month-ends where ATO liabilities (GST, PAYG, ICA) increased | Balance Sheet by month (ATO liability accounts) | Higher is worse | 2 | 3 | 12 | Threshold to confirm ('ATO definitely') |
| D5 | Bank debt growth (6 months) | % change in loans + overdraft balances over 6 months | Balance Sheet by month (loan/overdraft accounts) | Higher is worse | 10% | 25% | 7 | New from Patrick |
| D6 | Facility utilisation | Overdraft/facility drawn ÷ approved limit | Balance from Xero; limit entered manually | Higher is worse | 85% | 100% | 6 | New from Patrick |
| D7 | Trade creditor days | Trade payables ÷ (COGS + operating expenses) × 365 | Aged Payables + P&L | Higher is worse | 60 | 90 | 7 | Confirmed (draft threshold) |
| D8 | Trade creditors >90 days overdue | Payables >90 days overdue ÷ total trade payables | Aged Payables report | Higher is worse | 15% | 30% | 7 | New from Patrick |
| D9 | Debtor days trend (3 months) | Change in debtor days vs 3 months ago | Aged Receivables + P&L | Higher is worse | 10 | 20 | 5 | New from Patrick |
| D10 | Debtors >90 days overdue | Receivables >90 days overdue ÷ total receivables | Aged Receivables report | Higher is worse | 15% | 25% | 5 | New from Patrick |
| D11 | Sales up, cash down | Consecutive months where rolling 3-month revenue rose and cash balance fell | P&L by month + Bank balances | Higher is worse | 2 | 3 | 8 | New from Patrick |
| D12 | Operating cash flow ratio | Operating cash flow (last 12 months) ÷ current liabilities | Bank transactions / cash flow derived | Lower is worse | 0.4 | 0.2 | 7 | Rick to confirm formula |
| D13 | Debt-to-asset ratio | Total liabilities ÷ total assets | Balance Sheet report | Higher is worse | 0.7 | 1 | 10 | New from Patrick |

## Viability indicators
| ID | Indicator | Calculation | Xero source | Direction | Amber | Red | Weight | Status |
|---|---|---|---|---|---|---|---|---|
| V1 | Equity ratio | Net assets ÷ total assets | Balance Sheet report | Lower is worse | 0.2 | 0 | 15 | New from Patrick |
| V2 | Gross margin | Gross profit ÷ revenue (last 12 months) | P&L report | Lower is worse | 30% | 15% | 15 | Threshold varies by industry |
| V3 | Gross margin trend (12 months) | Gross margin now minus gross margin 12 months ago (percentage points) | P&L by month | Lower is worse | -2% | -5% | 10 | New from Patrick |
| V4 | Overhead ÷ gross profit | Operating expenses ÷ gross profit | P&L report | Higher is worse | 90% | 100% | 15 | New from Patrick |
| V5 | Underlying profit margin | (Net profit + interest + depreciation + one-off/legacy costs) ÷ revenue | P&L report (adjustments flagged manually) | Lower is worse | 5% | 0% | 20 | New from Patrick (core test) |
| V6 | Revenue trend (12 months) | % change in rolling 12-month revenue | P&L by month | Lower is worse | -5% | -15% | 10 | New from Patrick |
| V7 | Pipeline coverage | Open quotes value ÷ average monthly revenue | Xero Quotes (often incomplete) | Lower is worse | 1 | 0.5 | 5 | New from Patrick (data often patchy) |
| V8 | Long-term asset coverage | Non-current assets ÷ non-current liabilities | Balance Sheet report | Lower is worse | 1.2 | 1 | 10 | New from Patrick |

## Outcome matrix (Distress × Viability)
| | Strong | Uncertain | Weak |
|---|---|---|---|
| **Low** | Healthy – monitor | Performance review | Structural concern |
| **Moderate** | Early intervention | Turnaround review | Restructure or orderly exit |
| **High** | Restructure candidate (SBR/VA/safe harbour) | Urgent advice | Likely liquidation/exit |

## Non-Xero inputs (owner questionnaire)
Statutory demand received (override), bank arrears/limit changes, ATO payment plan status, customer and problem solved, competitive advantage, owner view on underlying profitability, where cash has gone, overhead reduction options, pipeline/WIP, capital intensity.

## Not yet confirmed
D1, D2, D12 formulas (Rick); D4 threshold (Patrick); industry benchmarks for all thresholds (especially V2). Outputs are indicative only, not an insolvency determination.
