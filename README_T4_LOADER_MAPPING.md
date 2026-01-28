# T4 Loader Name/SIN Mapping

The loader `scripts/load_t4_recon_to_db.py` now supports strict name-based matching and an optional external mapping file to resolve entries when `sin` is missing or not found in `employees.t4_sin`.

## Mapping File Format
Create a CSV with the following headers:

- employee_name: Text as it appears in the reconciliation report
- t4_sin: Optional SIN; if provided, must match `employees.t4_sin`
- employee_id: Optional numeric `employees.employee_id`

You may provide either `employee_id` or `t4_sin`, or both. If both are present, `employee_id` is preferred.

Example:

```
employee_name,t4_sin,employee_id
"John Doe",637005133,
"Jane Smith",,102
"Doe, John",637005133,
```

Normalization is strict: names are lowercased and inner whitespace collapsed. Variants like `first_name last_name`, `last_name first_name`, `full_name`, `name`, and `legacy_name` will be attempted.

## Usage

Dry-run with mapping file and updates on existing zero-value rows:

```powershell
l:\limo\.venv\Scripts\python.exe -X utf8 scripts\load_t4_recon_to_db.py --dry-run --update --years 2013,2014 --name-match --mapping-file L:\limo\data\T4_NAME_SIN_MAPPING.csv
```

Write mode:

```powershell
l:\limo\.venv\Scripts\python.exe -X utf8 scripts\load_t4_recon_to_db.py --write --update --years 2013,2014 --name-match --mapping-file L:\limo\data\T4_NAME_SIN_MAPPING.csv
```

## Outputs

- Missing or skipped entries are reported to `L:\limo\reports\T4_MISSING_MAPPINGS.csv` with year, source, SIN, employee_name, reason, and boxes JSON.

## Notes

- Ambiguous name matches (same normalized name across multiple employees) are skipped to avoid incorrect assignments.
- External mapping entries take priority over internal name matches.
- All DB updates and inserts will include a note indicating the match source (e.g., `(name)`, `(mapping:employee_id)`).
