#!/usr/bin/env python3
"""
Generate 2012 T4 PDF Forms
Creates individual T4 Statement of Remuneration Paid for each employee
"""

import psycopg2
from decimal import Decimal
import sys
import os
from datetime import datetime

# Add the modern_backend path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'modern_backend'))

try:
    from app.services.pdf_generator import T4PDFForm
    print("✓ T4PDFForm class imported successfully")
except ImportError as e:
    print(f"✗ Failed to import T4PDFForm: {e}")
    print("  Attempting alternate import...")
    try:
        # Try direct import from pdf_generator
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pdf_generator",
            os.path.join(os.path.dirname(__file__), 'modern_backend', 'app', 'services', 'pdf_generator.py')
        )
        pdf_gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdf_gen)
        T4PDFForm = pdf_gen.T4PDFForm
        print("✓ T4PDFForm loaded via alternate method")
    except Exception as e2:
        print(f"✗ Alternate import also failed: {e2}")
        print("\nWill generate text-based T4 summary instead of PDFs")
        T4PDFForm = None

print()

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="ArrowLimousine"
)

cur = conn.cursor()

# Get employer info from system_config
cur.execute("""
    SELECT config_value 
    FROM system_config 
    WHERE config_key = 'company_name'
""")
company_result = cur.fetchone()
company_name = company_result[0] if company_result else "Arrow Limousine Service"

# Employer information (placeholders for missing data)
employer_data = {
    'legal_name': f'{company_name} Ltd.',
    'business_number': '123456789RC0001',  # PLACEHOLDER - need actual BN
    'address': 'PO Box 20042',  # PLACEHOLDER
    'city': 'Red Deer',
    'province': 'AB',
    'postal_code': 'T4N 6X2',  # PLACEHOLDER
    'payroll_account': 'RP0001'  # PLACEHOLDER
}

# Get all 2012 T4 records with employee details
cur.execute("""
    SELECT 
        e.employee_id,
        e.employee_number,
        e.first_name,
        e.last_name,
        e.full_name,
        e.t4_sin,
        e.street_address,
        e.city,
        e.province,
        e.postal_code,
        t.t4_id,
        t.box_14_employment_income,
        t.box_16_cpp_contributions,
        t.box_18_ei_premiums,
        t.box_22_income_tax,
        t.box_24_ei_insurable_earnings,
        t.box_26_cpp_pensionable_earnings,
        t.box_12_taxable_benefits,
        t.box_20_rpp_contributions,
        t.box_44_union_dues,
        t.box_46_charitable_donations
    FROM employee_t4_records t
    JOIN employees e ON t.employee_id = e.employee_id
    WHERE t.tax_year = 2012
    ORDER BY e.last_name, e.first_name
""")

employees_t4 = cur.fetchall()

print("=" * 100)
print("GENERATING 2012 T4 PDF FORMS")
print("=" * 100)
print()
print(f"Total T4 Forms to generate: {len(employees_t4)}")
print(f"Tax Year: 2012")
print(f"Employer: {employer_data['legal_name']}")
print()

# Create output directory
output_dir = os.path.join(os.path.dirname(__file__), 'T4_2012_Forms')
os.makedirs(output_dir, exist_ok=True)
print(f"Output directory: {output_dir}")
print()

generated_count = 0
error_count = 0
missing_sin_count = 0

for emp in employees_t4:
    emp_id, emp_num, first, last, full, sin, addr, city, prov, postal, t4_id, box14, box16, box18, box22, box24, box26, box12, box20, box44, box46 = emp
    
    name = f"{last}, {first}" if last and first else (full or "Unknown")
    
    # Skip if no SIN
    if not sin or not sin.strip():
        print(f"⚠ Skipping {name} - Missing SIN")
        missing_sin_count += 1
        continue
    
    # Prepare employee data
    employee_data = {
        'employee_number': emp_num or str(emp_id),
        'first_name': first or '',
        'last_name': last or '',
        'full_name': name,
        'sin': sin,
        'address': addr or '',
        'city': city or '',
        'province': prov or 'AB',
        'postal_code': postal or ''
    }
    
    # Prepare T4 data (using box14, box16, etc. as keys)
    t4_data = {
        'box14': float(box14 or 0),
        'box16': float(box16 or 0),
        'box18': float(box18 or 0),
        'box22': float(box22 or 0),
        'box24': float(box24 or 0),
        'box26': float(box26 or 0),
        'box12': float(box12 or 0) if box12 else 0,
        'box20': float(box20 or 0) if box20 else 0,
        'box44': float(box44 or 0) if box44 else 0,
        'box46': float(box46 or 0) if box46 else 0
    }
    
    # Generate PDF
    if T4PDFForm:
        try:
            pdf_generator = T4PDFForm(
                employee_data=employee_data,
                t4_data=t4_data,
                tax_year=2012
            )
            
            # Generate filename
            last_clean = (last or 'Unknown').replace(' ', '_').replace(',', '')
            first_clean = (first or '').replace(' ', '_').replace(',', '')
            filename = f"T4_2012_{last_clean}_{first_clean}_{sin}.pdf"
            pdf_path = os.path.join(output_dir, filename)
            
            # Generate PDF bytes and write to file
            pdf_bytes = pdf_generator.generate()
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
            
            print(f"✓ Generated: {filename}")
            generated_count += 1
            
        except Exception as e:
            print(f"✗ Error generating T4 for {name}: {e}")
            error_count += 1
    else:
        # Text mode - just print summary
        print(f"T4 Data for {name} (SIN: {sin}):")
        print(f"  Box 14 (Employment Income): ${box14 or 0:,.2f}")
        print(f"  Box 16 (CPP): ${box16 or 0:,.2f}")
        print(f"  Box 18 (EI): ${box18 or 0:,.2f}")
        print(f"  Box 22 (Tax): ${box22 or 0:,.2f}")
        print()
        generated_count += 1

print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Successfully generated: {generated_count} T4 forms")
print(f"Skipped (missing SIN): {missing_sin_count} employees")
print(f"Errors: {error_count}")
print()

if missing_sin_count > 0:
    print("⚠ ATTENTION: Some employees are missing SIN numbers and were skipped:")
    for emp in employees_t4:
        if not emp[5] or not emp[5].strip():
            name = f"{emp[3]}, {emp[2]}" if emp[3] and emp[2] else (emp[4] or "Unknown")
            print(f"  - {name} (ID: {emp[0]})")
    print()

if T4PDFForm:
    print(f"📁 PDF files saved to: {output_dir}")
    print()
    print("⚠ IMPORTANT: Employer information contains PLACEHOLDERS")
    print("   Please update the following before filing:")
    print("   - Business Number (currently: 123456789RC0001)")
    print("   - Employer Address (currently: PO Box 20042)")
    print("   - Postal Code (currently: T4N 6X2)")
    print("   - Payroll Account Number (currently: RP0001)")
else:
    print("Text-based summary generated (PDF module not available)")

cur.close()
conn.close()
