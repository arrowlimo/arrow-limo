"""
PD7A Summary Extraction (Stage 3)
- Inventory-driven (uses PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json)
- No database writes; pure JSON/Markdown summary
"""
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber


INVENTORY_PATH = Path(r"L:\\limo\\reports\\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
OUTPUT_JSON = Path(r"L:\\limo\\reports\\PD7A_SUMMARY_REPORT.json")
OUTPUT_MD = Path(r"L:\\limo\\reports\\PD7A_SUMMARY_REPORT.md")

# PD7A detection and numeric patterns
PATTERNS = {
    "gross_payroll": re.compile(r"gross\s+payroll.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "num_employees_paid": re.compile(r"employees\s+paid.*?(\d+)", re.IGNORECASE),
    "tax_deductions": re.compile(r"tax\s+deductions.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "cpp_employee": re.compile(r"cpp\s*-?\s*employee.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "cpp_company": re.compile(r"cpp\s*-?\s*company.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "total_cpp": re.compile(r"total\s+cpp.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "ei_employee": re.compile(r"ei\s*-?\s*employee.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "ei_company": re.compile(r"ei\s*-?\s*company.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "total_ei": re.compile(r"total\s+ei.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
    "total_remittance": re.compile(r"remittance\s+for\s+period.*?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)", re.IGNORECASE),
}

# Period label (e.g., "July 2014" or "Jul 14")
PERIOD_PATTERN = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{2,4})", re.IGNORECASE)

def parse_decimal(text: str) -> Decimal:
    clean = text.replace(",", "").replace(" ", "").strip()
    try:
        return Decimal(clean)
    except Exception:
        return Decimal("0.00")


def parse_pd7a(pdf_path: Path, fallback_year: int | None):
    """Extract PD7A summary data from PDF (no DB writes)."""
    values = {
        "path": str(pdf_path),
        "filename": pdf_path.name,
        "year": fallback_year,
        "period_label": None,
        "gross_payroll": None,
        "num_employees_paid": None,
        "tax_deductions": None,
        "cpp_employee": None,
        "cpp_company": None,
        "total_cpp": None,
        "ei_employee": None,
        "ei_company": None,
        "total_ei": None,
        "total_remittance": None,
        "flags": [],
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([p.extract_text() or "" for p in pdf.pages])
            if not text:
                values["flags"].append("NO_TEXT")
                return values

            period = PERIOD_PATTERN.search(text)
            if period:
                year_part = period.group(2)
                year_val = int(year_part) + 2000 if len(year_part) == 2 else int(year_part)
                values["year"] = year_val
                values["period_label"] = period.group(0)

            for key, pattern in PATTERNS.items():
                m = pattern.search(text)
                if m:
                    values[key] = parse_decimal(m.group(1))
                else:
                    values["flags"].append(f"MISSING_{key.upper()}")

            return values

    except Exception as e:
        values["flags"].append(f"ERROR: {e}")
        return values

def load_inventory():
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Inventory not found: {INVENTORY_PATH}")
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("PD7A Summary Extraction - Stage 3")
    print("=" * 70)

    inventory = load_inventory()
    documents = inventory.get("documents", [])
    pd7a_docs = [d for d in documents if "PD7A" in d.get("categories", [])]

    print(f"Found {len(pd7a_docs)} PD7A PDFs in inventory")

    results = []
    for doc in pd7a_docs:
        path = Path(doc["path"])
        year = doc.get("year")
        extracted = parse_pd7a(path, year)
        results.append(extracted)
        print(f"  ✓ {path.name}: remittance={extracted['total_remittance']} flags={extracted['flags']}")

    by_year = {}
    for r in results:
        yr = r.get("year")
        by_year.setdefault(yr, {
            "count": 0,
            "total_remittance": Decimal("0.00"),
            "gross_payroll": Decimal("0.00"),
            "tax_deductions": Decimal("0.00"),
            "cpp_employee": Decimal("0.00"),
            "cpp_company": Decimal("0.00"),
            "ei_employee": Decimal("0.00"),
            "ei_company": Decimal("0.00"),
        })
        by_year[yr]["count"] += 1
        for key in ["total_remittance", "gross_payroll", "tax_deductions", "cpp_employee", "cpp_company", "ei_employee", "ei_company"]:
            if r.get(key):
                by_year[yr][key] += r[key]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "scan_date": datetime.now().isoformat(),
            "total_files": len(results),
            "by_year": {str(k): {kk: str(vv) for kk, vv in v.items()} for k, v in by_year.items()},
            "results": results,
        }, f, indent=2, default=str)

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# PD7A Summary Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for yr in sorted(by_year.keys()):
            agg = by_year[yr]
            f.write(f"## {yr}\n")
            f.write(f"- Files: {agg['count']}\n")
            f.write(f"- Total remittance: ${agg['total_remittance']:.2f}\n")
            f.write(f"- Gross payroll: ${agg['gross_payroll']:.2f}\n")
            f.write(f"- Tax deductions: ${agg['tax_deductions']:.2f}\n")
            f.write(f"- CPP employee: ${agg['cpp_employee']:.2f}\n")
            f.write(f"- CPP company: ${agg['cpp_company']:.2f}\n")
            f.write(f"- EI employee: ${agg['ei_employee']:.2f}\n")
            f.write(f"- EI company: ${agg['ei_company']:.2f}\n\n")

        f.write("## File Details\n\n")
        for r in results:
            f.write(f"- {r['filename']} (Year {r.get('year')}, Period {r.get('period_label')}) — Remittance {r.get('total_remittance')} Flags: {', '.join(r['flags']) if r['flags'] else 'None'}\n")

    print("\n" + "=" * 70)
    print(f"✅ PD7A summary report saved: {OUTPUT_JSON}")
    print(f"✅ PD7A summary markdown saved: {OUTPUT_MD}")
    print("=" * 70)


if __name__ == '__main__':
    main()
