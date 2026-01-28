"""
T4 Data Extraction and Verification (Stage 2)
- Extracts numeric data from T4 PDFs (boxes 14, 16, 18, 22, 24, etc.)
- Compares extracted values against employee_t4_records table
- Flags discrepancies between PDF and database
- Outputs detailed reconciliation report
"""
import os
import re
import json
import psycopg2
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

import pdfplumber


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

INVENTORY_PATH = Path(r"L:\limo\reports\PAYROLL_DOCUMENTS_INVENTORY_2012_2016.json")
OUTPUT_JSON = Path(r"L:\limo\reports\T4_RECONCILIATION_REPORT.json")
OUTPUT_MD = Path(r"L:\limo\reports\T4_RECONCILIATION_REPORT.md")

# T4 box patterns - CRA T4 format has box numbers and values on separate lines with variable spacing
T4_BOXES = {
    "14": r"14[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # Employment income
    "16": r"16[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # Employee CPP contributions
    "18": r"18[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # Employee EI premiums
    "22": r"22[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # Income tax deducted
    "24": r"24[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # EI insurable earnings
    "26": r"26[\s\S]{0,100}?(\d{1,10}\.\d{2})",  # CPP pensionable earnings
}

# Social Insurance Number pattern - 9 digits (often appears as social insurance number in text)
SIN_PATTERN = r"(\d{3}\s+\d{3}\s+\d{3})"


def extract_text_from_pdf(path: Path) -> str:
    """Extract all text from PDF."""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def parse_amount(text: str) -> Decimal:
    """Convert text amount to Decimal."""
    clean = text.replace(",", "").replace("$", "").strip()
    try:
        return Decimal(clean)
    except:
        return Decimal("0.00")


def extract_t4_data(pdf_path: Path, year: int):
    """Extract T4 box values from PDF - handles multi-employee T4 bundles."""
    text = extract_text_from_pdf(pdf_path)
    
    result = {
        "path": str(pdf_path),
        "year": year,
        "employees": []
    }
    
    # Split by pages to handle multiple employees per PDF
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            
            # Extract SIN to identify employee (if present)
            sin_match = re.search(SIN_PATTERN, page_text)
            sin = sin_match.group(1).replace(" ", "") if sin_match else f"UNKNOWN_PAGE{page_num}"
            
            # Extract box values
            boxes = {}
            for box_num, pattern in T4_BOXES.items():
                match = re.search(pattern, page_text)
                if match:
                    boxes[f"box_{box_num}"] = parse_amount(match.group(1))
            
            # Only add if we found at least box 14 (employment income - mandatory on T4)
            if "box_14" in boxes and boxes["box_14"] > 0:
                result["employees"].append({
                    "name": sin,  # Use SIN as identifier
                    "sin": sin,
                    "boxes": boxes
                })
    
    return result


def get_db_t4_records(year: int):
    """Fetch T4 records from database for given year."""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    query = """
        SELECT 
            e.first_name || ' ' || e.last_name as employee_name,
            t4.employee_id,
            t4.tax_year,
            t4.box_14_employment_income,
            t4.box_16_cpp_contributions,
            t4.box_18_ei_premiums,
            t4.box_22_income_tax,
            t4.box_24_ei_insurable_earnings,
            t4.box_26_cpp_pensionable_earnings
        FROM employee_t4_records t4
        LEFT JOIN employees e ON t4.employee_id = e.employee_id
        WHERE t4.tax_year = %s
        ORDER BY employee_name
    """
    
    cur.execute(query, (year,))
    rows = cur.fetchall()
    
    records = []
    for row in rows:
        records.append({
            "employee_name": row[0],
            "employee_id": row[1],
            "tax_year": row[2],
            "box_14": Decimal(str(row[3])) if row[3] else Decimal("0.00"),
            "box_16": Decimal(str(row[4])) if row[4] else Decimal("0.00"),
            "box_18": Decimal(str(row[5])) if row[5] else Decimal("0.00"),
            "box_22": Decimal(str(row[6])) if row[6] else Decimal("0.00"),
            "box_24": Decimal(str(row[7])) if row[7] else Decimal("0.00"),
            "box_26": Decimal(str(row[8])) if row[8] else Decimal("0.00"),
        })
    
    cur.close()
    conn.close()
    
    return records


def fuzzy_name_match(name1: str, name2: str) -> bool:
    """Simple fuzzy match - normalize and compare."""
    n1 = re.sub(r'[^a-z]', '', name1.lower())
    n2 = re.sub(r'[^a-z]', '', name2.lower())
    return n1 == n2 or n1 in n2 or n2 in n1


def compare_t4_data(pdf_data, db_records, year):
    """Compare PDF-extracted T4 data against database records using SIN."""
    # First, get SINs for DB records
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Map employee_id to SIN
    cur.execute("SELECT employee_id, t4_sin FROM employees WHERE t4_sin IS NOT NULL")
    sin_map = {row[0]: row[1].replace(" ", "").replace("-", "") for row in cur.fetchall()}
    cur.close()
    conn.close()
    
    # Add SINs to db_records
    for rec in db_records:
        rec["sin"] = sin_map.get(rec["employee_id"], "")
    
    results = {
        "year": year,
        "pdf_count": len(pdf_data),
        "db_count": len(db_records),
        "matches": [],
        "discrepancies": [],
        "pdf_only": [],
        "db_only": db_records.copy()
    }
    
    for pdf_emp in pdf_data:
        pdf_sin = pdf_emp["sin"]
        pdf_boxes = pdf_emp["boxes"]
        
        # Find matching DB record by SIN
        matched = False
        for db_rec in db_records:
            if db_rec["sin"] == pdf_sin and pdf_sin != "":
                matched = True
                results["db_only"] = [r for r in results["db_only"] if r != db_rec]
                
                # Compare box values
                discrepancies = []
                for box_key in ["box_14", "box_16", "box_18", "box_22", "box_24", "box_26"]:
                    pdf_val = pdf_boxes.get(box_key, Decimal("0.00"))
                    db_val = db_rec.get(box_key, Decimal("0.00"))
                    
                    if abs(pdf_val - db_val) > Decimal("0.01"):  # Allow 1 cent rounding
                        discrepancies.append({
                            "box": box_key,
                            "pdf_value": float(pdf_val),
                            "db_value": float(db_val),
                            "difference": float(pdf_val - db_val)
                        })
                
                if discrepancies:
                    results["discrepancies"].append({
                        "sin": pdf_sin,
                        "employee_name": db_rec["employee_name"],
                        "issues": discrepancies
                    })
                else:
                    results["matches"].append({
                        "sin": pdf_sin,
                        "employee_name": db_rec["employee_name"]
                    })
                break
        
        if not matched:
            results["pdf_only"].append({
                "sin": pdf_sin,
                "boxes": {k: float(v) for k, v in pdf_boxes.items()}
            })
    
    return results


def load_inventory():
    """Load document inventory."""
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(f"Inventory not found: {INVENTORY_PATH}")
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=" * 70)
    print("T4 Data Extraction and Verification - Stage 2")
    print("=" * 70)
    
    inventory = load_inventory()
    documents = inventory.get("documents", [])
    
    # Filter T4 documents by year
    t4_docs = [d for d in documents if "T4" in d.get("categories", [])]
    
    years_to_process = [2012, 2013, 2014]  # 2015/2016 missing per TODO list
    all_year_results = {}
    
    for year in years_to_process:
        print(f"\n{'=' * 70}")
        print(f"Processing Year: {year}")
        print(f"{'=' * 70}")
        
        year_docs = [d for d in t4_docs if d.get("year") == year]
        print(f"Found {len(year_docs)} T4 PDFs for {year}")
        
        # Show which PDFs we're trying to process
        for doc in year_docs:
            path = Path(doc["path"])
            print(f"  - {path.name} {'(SKIPPED - OCR locked)' if '_ocred' in path.name else ''}")
        
        # Extract from PDFs
        pdf_employees = []
        for doc in year_docs:
            path = Path(doc["path"])
            # Try to read all PDFs - even _ocred ones can be read with pdfplumber (just not with Tesseract)
            try:
                extracted = extract_t4_data(path, year)
                pdf_employees.extend(extracted["employees"])
                print(f"  ✓ {path.name}: {len(extracted['employees'])} employee(s)")
            except Exception as e:
                print(f"  ✗ {path.name}: {e}")
        
        print(f"\nTotal employees extracted from PDFs: {len(pdf_employees)}")
        
        # Get DB records
        db_records = get_db_t4_records(year)
        print(f"Total T4 records in database: {len(db_records)}")
        
        # Compare
        comparison = compare_t4_data(pdf_employees, db_records, year)
        all_year_results[year] = comparison
        
        print(f"\nResults for {year}:")
        print(f"  ✓ Matches: {len(comparison['matches'])}")
        print(f"  ⚠ Discrepancies: {len(comparison['discrepancies'])}")
        print(f"  📄 PDF only: {len(comparison['pdf_only'])}")
        print(f"  💾 DB only: {len(comparison['db_only'])}")
    
    # Save reports
    output = {
        "scan_date": datetime.now().isoformat(),
        "years_processed": years_to_process,
        "results_by_year": all_year_results
    }
    
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    
    # Generate markdown summary
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# T4 Reconciliation Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for year in years_to_process:
            res = all_year_results[year]
            f.write(f"## {year}\n\n")
            f.write(f"- **Matches:** {len(res['matches'])}\n")
            f.write(f"- **Discrepancies:** {len(res['discrepancies'])}\n")
            f.write(f"- **PDF only:** {len(res['pdf_only'])}\n")
            f.write(f"- **DB only:** {len(res['db_only'])}\n\n")
            
            if res['discrepancies']:
                f.write("### Discrepancies\n\n")
                for disc in res['discrepancies']:
                    f.write(f"**SIN: {disc['sin']}** ({disc['employee_name']})\n")
                    for issue in disc['issues']:
                        f.write(f"  - {issue['box']}: PDF=${issue['pdf_value']:.2f}, DB=${issue['db_value']:.2f}, Δ=${issue['difference']:.2f}\n")
                    f.write("\n")
            
            if res['pdf_only']:
                f.write("### In PDF but not in Database\n\n")
                for emp in res['pdf_only']:
                    f.write(f"- SIN: {emp['sin']}: {emp['boxes']}\n")
                f.write("\n")
            
            if res['db_only']:
                f.write("### In Database but not in PDFs\n\n")
                for emp in res['db_only']:
                    sin_display = emp.get('sin', 'NO_SIN')
                    f.write(f"- {emp['employee_name']} (SIN: {sin_display}, Box 14: ${emp['box_14']:.2f})\n")
                f.write("\n")
    
    print(f"\n{'=' * 70}")
    print(f"✅ T4 reconciliation report saved: {OUTPUT_JSON}")
    print(f"✅ T4 reconciliation summary saved: {OUTPUT_MD}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
