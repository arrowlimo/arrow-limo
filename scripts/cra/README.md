# CRA Forms Automation (GST/HST, source deductions)

This toolkit lets you query data in the `almsdata` Postgres DB and fill CRA PDF forms (or generate a summary PDF if the form isn't fillable). It focuses on:

- GST/HST return (GST34) — lines 101, 105, 108, 109, 110, 111, 112, 113A/B, 114, 115, 135, 136, 138
- Source deductions (PD7A-like summary) — remittance summary by period

## How it works
- Queries are defined in `mapping_gst.json` (and other mappings later).
- `fill_cra_form.py` runs queries for a period, produces a dictionary of form field values, and either:
  - fills a provided fillable PDF template, or
  - generates a summary PDF report if the PDF isn't fillable.
- `preview_cra_fields.py` lists fields present in the PDF to help map.

## Quick start (Windows PowerShell)

1. Ensure your venv is active and required packages installed:

```powershell
l:\limo\.venv\Scripts\python.exe -m pip install psycopg2-binary pypdf reportlab
```

2. Preview fields in a CRA PDF (optional, helps build mapping):

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\preview_cra_fields.py --pdf "L:\limo\quickbooks\Arrow Limousine 2007.pdf" --out fields_2007.json
```

3. Fill GST return for a period using a mapping and a fillable template (if you have one):

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025Q3 `
  --template "L:\\templates\\GST34_fillable.pdf" `
  --output "L:\\limo\\reports\\GST34_2025Q3_filled.pdf"
```

4. Or generate a summary PDF without a fillable template:

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py --form gst --period 2025Q3 --output "L:\\limo\\reports\\GST34_2025Q3_summary.pdf"
```

## Mapping file
- Edit `mapping_gst.json` to adjust SQL and field names.
- Period tokens supported: `{period_start}`, `{period_end}`, `{year}`, `{quarter}`.

## Notes
- The provided 2003–2007 PDFs look like scanned/print forms (likely not fillable). Use the summary PDF output unless you have a fillable version.
- We default to the `modern_backend/app/db.py` connection env vars; override via environment if needed.
