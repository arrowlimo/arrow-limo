import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# Get August 2012 database totals
cur.execute("""
    SELECT COUNT(*), SUM(gross_pay), SUM(cpp), SUM(ei), SUM(tax)
    FROM driver_payroll
    WHERE year = 2012 AND month = 8 AND driver_id != 'ADJ'
""")

db_count, db_gross, db_cpp, db_ei, db_tax = cur.fetchone()

# PDF totals from August 2012 Payroll Summary
pdf_gross = 14773.59
pdf_cpp = 868.28
pdf_ei = 277.91
pdf_tax = 2130.50

print("="*60)
print("AUGUST 2012 COMPARISON: Database vs PDF Payroll Summary")
print("="*60)

print(f"\nDatabase (current):")
print(f"  Entries: {db_count}")
print(f"  Gross Pay:  ${db_gross:>12,.2f}")
print(f"  CPP:        ${db_cpp:>12,.2f}")
print(f"  EI:         ${db_ei:>12,.2f}")
print(f"  Tax:        ${db_tax:>12,.2f}")

print(f"\nPDF Summary (August 2012 Payroll Summary):")
print(f"  Employees: 10")
print(f"  Gross Pay:  ${pdf_gross:>12,.2f}")
print(f"  CPP:        ${pdf_cpp:>12,.2f}")
print(f"  EI:         ${pdf_ei:>12,.2f}")
print(f"  Tax:        ${pdf_tax:>12,.2f}")

print(f"\nDiscrepancy:")
gross_diff = float(db_gross) - pdf_gross
cpp_diff = float(db_cpp) - pdf_cpp
ei_diff = float(db_ei) - pdf_ei
tax_diff = float(db_tax) - pdf_tax

print(f"  Gross Pay:  ${gross_diff:>12,.2f} ({'OVER' if gross_diff > 0 else 'UNDER' if gross_diff < 0 else 'MATCH'})")
print(f"  CPP:        ${cpp_diff:>12,.2f} ({'OVER' if cpp_diff > 0 else 'UNDER' if cpp_diff < 0 else 'MATCH'})")
print(f"  EI:         ${ei_diff:>12,.2f} ({'OVER' if ei_diff > 0 else 'UNDER' if ei_diff < 0 else 'MATCH'})")
print(f"  Tax:        ${tax_diff:>12,.2f} ({'OVER' if tax_diff > 0 else 'UNDER' if tax_diff < 0 else 'MATCH'})")

# Analysis
print(f"\n{'='*60}")
print("ANALYSIS")
print("="*60)

if abs(gross_diff) < 100:
    print("[OK] August 2012 gross pay matches closely (within $100)")
    print("   Database likely has correct data already")
else:
    print(f"[WARN]  August 2012 has ${abs(gross_diff):,.2f} discrepancy")
    if gross_diff < 0:
        print(f"   Database is UNDER by ${abs(gross_diff):,.2f}")
        print(f"   PDF shows higher amounts - may need to import missing data")
    else:
        print(f"   Database is OVER by ${gross_diff:,.2f}")
        print(f"   Database may have duplicate or inflated entries")

print("\n📋 PDF contains detailed employee-level data:")
print("   - Individual employee hours, wages, gratuities, expenses")
print("   - Tax withholdings (CPP, EI, Federal Tax)")
print("   - Vacation pay accruals")
print("   - CRA remittance calculations")
print("\nThis format can be parsed to import/verify all 2012 monthly data")

cur.close()
conn.close()
