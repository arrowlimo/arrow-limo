# Personal Claimables Scanner

Scan receipts for likely personal claimable expenses and compute the owner taxable benefit including GST.

What it does
- Loads taxonomy from `scripts/claimable_personal_expenses.json`
- Queries `receipts` in a given date range from Postgres `almsdata`
- Uses keyword matching with exclusions to flag likely personal items (guidance-only)
- Computes owner benefit = total paid including GST (gross). If `gst_amount` is missing, derives GST as `gross * (rate/(1+rate))` with default rate 5%.
- Writes CSV to `reports/personal_benefits_<year>.csv` and prints per-category + grand totals

Prereqs
- Python with psycopg2 installed (already used across this repo)
- DB env vars optional; defaults: DB_NAME=almsdata, DB_USER=postgres, DB_HOST=localhost

Quick start
- Scan current year
  - `python l:\limo\scripts\scan_personal_claimables.py`
- Scan specific year (e.g., 2019)
  - `python l:\limo\scripts\scan_personal_claimables.py --year 2019`
- Custom period
  - `python l:\limo\scripts\scan_personal_claimables.py --start-date 2019-01-01 --end-date 2019-12-31`
- Limit and verbose for quick tests
  - `python l:\limo\scripts\scan_personal_claimables.py --year 2019 --limit 50 --verbose`
- Last full month
  - `python l:\limo\scripts\scan_personal_claimables.py --last-month`

Flags
- `--year N` pick a year (default: current)
- `--start-date YYYY-MM-DD` and `--end-date YYYY-MM-DD` for a custom range
- `--min-amount X` ignore small gross amounts
- `--assume-gst-rate R` fallback GST rate if not present on row (default 0.05)
- `--taxonomy path` alternate taxonomy JSON
- `--owner name` owner name to attribute benefits (default Paul)
- `--output path` write CSV to a custom file
- `--last-month` scan the last full calendar month automatically

Empty-year behavior
- If no receipts in the period (e.g., none for 2025 yet), the script exits cleanly and still writes a CSV with just the header and prints 0 totals.

Notes & caveats
- This is a heuristic finder to triage potential personal items. CRA eligibility depends on actual facts, supporting slips, and rules.
- Update `scripts/claimable_personal_expenses.json` to refine categories/keywords or year applicability.

Scheduling (Windows)
- Use the helper script to register a monthly task that runs on the 1st at 6:00 AM for the last full month:
  - PowerShell (as Administrator):
    - `l:\limo\scripts\register_monthly_personal_claimables_task.ps1`
  - The task is named `Limo-PersonalClaimables-LastMonth`. It runs the scanner with `--last-month` and writes CSVs to `l:\limo\reports`.
