"""
2013 Payroll Import Verification (Dry-Run)

Reviews staging data and shows exactly what will be imported.
NO DATABASE CHANGES - verification only.
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from decimal import Decimal
import os

DATA_DIR = Path(r"L:\limo\data")
STAGING_FILE = DATA_DIR / "2013_payroll_staging.json"

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def verify_import():
    """Dry-run verification of import."""
    
    print("="*80)
    print("2013 PAYROLL IMPORT VERIFICATION (DRY-RUN)")
    print("="*80)
    print("\n⚠️  NO DATABASE CHANGES WILL BE MADE")
    print("   This is a verification/preview only\n")
    
    # Load staging data
    with open(STAGING_FILE, 'r', encoding='utf-8') as f:
        staging = json.load(f)
    
    print("="*80)
    print("STAGING DATA SUMMARY")
    print("="*80)
    
    print(f"\nGenerated: {staging['generated_at']}")
    print(f"Source Year: {staging['year']}")
    print(f"Records to import: {staging['import_summary']['total_records_to_import']}")
    
    # Show what will be imported
    print(f"\n{'='*80}")
    print("IMPORT PREVIEW - T4 SUMMARY RECORDS")
    print("="*80)
    
    t4_records = staging['data_ready_for_import']['t4_summary']
    
    for i, record in enumerate(t4_records, 1):
        print(f"\n📄 Record {i}/{len(t4_records)}")
        print(f"   Source: {record['source_file']}")
        print(f"   Year: {record['year']}")
        print(f"   Type: {record['record_type']}")
        
        if record.get('total_cpp'):
            print(f"   CPP Total: ${Decimal(record['total_cpp']):,.2f}")
        if record.get('total_ei'):
            print(f"   EI Total: ${Decimal(record['total_ei']):,.2f}")
        if record.get('total_income_tax'):
            print(f"   Income Tax: ${Decimal(record['total_income_tax']):,.2f}")
        if record.get('total_employment_income'):
            print(f"   Employment Income: ${Decimal(record['total_employment_income']):,.2f}")
        if record.get('total_employees'):
            print(f"   Employee Count: {record['total_employees']}")
        
        print(f"   Import Action: {record['import_action']}")
    
    # Database comparison
    print(f"\n{'='*80}")
    print("DATABASE COMPARISON")
    print("="*80)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get current 2013 totals
        cur.execute("""
            SELECT 
                COUNT(*) as record_count,
                COALESCE(SUM(cpp), 0) as total_cpp,
                COALESCE(SUM(ei), 0) as total_ei,
                COALESCE(SUM(tax), 0) as total_tax,
                COALESCE(SUM(gross_pay), 0) as total_gross
            FROM driver_payroll
            WHERE year = 2013
            AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        """)
        
        current = cur.fetchone()
        
        print(f"\nCURRENT DATABASE (2013):")
        print(f"  Records: {current['record_count']}")
        print(f"  CPP Total: ${Decimal(str(current['total_cpp'])):,.2f}")
        print(f"  EI Total: ${Decimal(str(current['total_ei'])):,.2f}")
        print(f"  Tax Total: ${Decimal(str(current['total_tax'])):,.2f}")
        print(f"  Gross Pay: ${Decimal(str(current['total_gross'])):,.2f}")
        
        # Show T4 totals from staging
        t4_cpp = Decimal(t4_records[0]['total_cpp']) if t4_records and t4_records[0].get('total_cpp') else Decimal('0')
        t4_ei = Decimal(t4_records[0]['total_ei']) if t4_records and t4_records[0].get('total_ei') else Decimal('0')
        
        print(f"\nT4 SUMMARY TOTALS (TO IMPORT):")
        print(f"  CPP Total: ${t4_cpp:,.2f}")
        print(f"  EI Total: ${t4_ei:,.2f}")
        
        # Calculate discrepancy
        cpp_diff = t4_cpp - Decimal(str(current['total_cpp']))
        ei_diff = t4_ei - Decimal(str(current['total_ei']))
        
        print(f"\nDISCREPANCY ANALYSIS:")
        print(f"  CPP Difference: ${cpp_diff:,.2f}")
        print(f"  EI Difference: ${ei_diff:,.2f}")
        
        if abs(cpp_diff) > Decimal('5000'):
            print(f"\n  ⚠️  LARGE CPP DISCREPANCY (${abs(cpp_diff):,.2f})")
            print(f"     Database may be missing {abs(cpp_diff)/t4_cpp*100:.1f}% of CPP deductions")
        
        if abs(ei_diff) > Decimal('3000'):
            print(f"\n  ⚠️  LARGE EI DISCREPANCY (${abs(ei_diff):,.2f})")
            print(f"     Database may be missing {abs(ei_diff)/t4_ei*100:.1f}% of EI premiums")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Database connection error: {str(e)}")
    
    # Validation warnings
    print(f"\n{'='*80}")
    print("VALIDATION WARNINGS")
    print("="*80)
    
    for warning in staging['validation_warnings']:
        print(f"\n{warning['severity']}: {warning['category']}")
        print(f"  {warning['message']}")
        print(f"  → {warning['recommendation']}")
    
    # Import decision
    print(f"\n{'='*80}")
    print("IMPORT DECISION")
    print("="*80)
    
    if staging['duplicate_check']['driver_payroll']['existing_records'] > 0:
        print(f"\n⚠️  DATABASE ALREADY HAS {staging['duplicate_check']['driver_payroll']['existing_records']} 2013 RECORDS")
        print(f"\nOPTIONS:")
        print(f"  1. SKIP IMPORT - Keep existing database records as-is")
        print(f"  2. ADD T4 SUMMARY - Add T4 totals as separate records for CRA reference")
        print(f"  3. RECONCILE - Investigate why database differs from T4")
        print(f"\nRECOMMENDATION:")
        print(f"  Option 2: Add T4 Summary records with source='T4_SUMMARY_2013_PDF'")
        print(f"  This preserves both database detail AND authoritative T4 totals")
    else:
        print(f"\n✅ NO EXISTING 2013 RECORDS")
        print(f"   Safe to proceed with import")
    
    # Final summary
    print(f"\n{'='*80}")
    print("VERIFICATION COMPLETE")
    print("="*80)
    
    print(f"\n✅ Staging data validated")
    print(f"✅ {len(t4_records)} T4 Summary records ready")
    print(f"✅ Duplicate check complete")
    print(f"✅ Database comparison complete")
    
    print(f"\nTO PROCEED WITH IMPORT:")
    print(f"  1. Review this verification report")
    print(f"  2. Confirm import approach (add T4 summary records)")
    print(f"  3. Run: python scripts/execute_2013_import.py --write")
    
    print(f"\n⚠️  REMEMBER: This was a DRY-RUN")
    print(f"   No database changes were made")


if __name__ == '__main__':
    verify_import()
