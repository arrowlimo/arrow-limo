"""
Generate 2013 Staging Data for Import

Prepares extracted 2013 payroll data for import:
- Checks for duplicates against database
- Validates data completeness
- Generates staging JSON
- Creates import verification report
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import os

DATA_DIR = Path(r"L:\limo\data")
EXTRACTED_FILE = DATA_DIR / "2013_payroll_extracted.json"
STAGING_FILE = DATA_DIR / "2013_payroll_staging.json"

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_staging_data():
    """Generate staging data with duplicate detection."""
    
    print("="*80)
    print("2013 PAYROLL STAGING DATA GENERATION")
    print("="*80)
    
    # Load extracted data
    with open(EXTRACTED_FILE, 'r', encoding='utf-8') as f:
        extracted = json.load(f)
    
    staging = {
        'generated_at': datetime.now().isoformat(),
        'source_file': str(EXTRACTED_FILE),
        'year': 2013,
        'import_summary': {},
        'duplicate_check': {},
        'validation_warnings': [],
        'data_ready_for_import': {}
    }
    
    # Check database for existing 2013 data
    print(f"\n{'='*80}")
    print("DUPLICATE CHECK - DATABASE COMPARISON")
    print("="*80)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check driver_payroll for 2013
        cur.execute("""
            SELECT COUNT(*) as count, 
                   COALESCE(SUM(gross_pay), 0) as total_gross
            FROM driver_payroll
            WHERE year = 2013
        """)
        result = cur.fetchone()
        existing_payroll_records = result['count']
        existing_gross_total = result['total_gross']
        
        print(f"\nExisting driver_payroll records for 2013: {existing_payroll_records}")
        print(f"Existing gross pay total: ${existing_gross_total:,.2f}")
        
        staging['duplicate_check']['driver_payroll'] = {
            'existing_records': existing_payroll_records,
            'existing_gross_total': str(existing_gross_total),
            'action': 'skip_individual_imports' if existing_payroll_records > 0 else 'ready_to_import'
        }
        
        # Check if T4 summary data exists
        cur.execute("""
            SELECT COUNT(*) as count
            FROM driver_payroll
            WHERE year = 2013
            AND source LIKE '%T4%'
        """)
        result = cur.fetchone()
        existing_t4_records = result['count']
        
        print(f"Existing T4-sourced records: {existing_t4_records}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n⚠️  Database connection error: {str(e)}")
        existing_payroll_records = 0
        existing_t4_records = 0
        staging['duplicate_check']['error'] = str(e)
    
    # Prepare T4 Summary data for import
    print(f"\n{'='*80}")
    print("T4 SUMMARY - STAGING FOR IMPORT")
    print("="*80)
    
    t4_summary_records = []
    
    for summary in extracted['t4_summary']:
        if summary.get('total_cpp_contributions') or summary.get('total_ei_premiums'):
            record = {
                'source_file': summary['filename'],
                'year': 2013,
                'record_type': 'T4_SUMMARY_YEAREND',
                'total_cpp': summary.get('total_cpp_contributions'),
                'total_ei': summary.get('total_ei_premiums'),
                'total_income_tax': summary.get('total_income_tax'),
                'total_employment_income': summary.get('total_employment_income'),
                'total_employees': summary.get('total_employees'),
                'import_action': 'CREATE_SUMMARY_RECORD'
            }
            t4_summary_records.append(record)
            
            print(f"\nFile: {summary['filename']}")
            if record['total_cpp']:
                print(f"  CPP: ${Decimal(record['total_cpp']):,.2f}")
            if record['total_ei']:
                print(f"  EI:  ${Decimal(record['total_ei']):,.2f}")
    
    staging['data_ready_for_import']['t4_summary'] = t4_summary_records
    
    print(f"\n✅ {len(t4_summary_records)} T4 Summary records ready for import")
    
    # Prepare T4 slips metadata (not individual amounts - those need manual correction)
    print(f"\n{'='*80}")
    print("T4 SLIPS - METADATA ONLY")
    print("="*80)
    
    print(f"\nTotal T4 slips extracted: {len(extracted['t4_slips'])}")
    print(f"T4s with SIN numbers: {sum(1 for t4 in extracted['t4_slips'] if t4.get('sin'))}")
    print(f"\n⚠️  Employee names are OCR errors - manual correction required")
    print(f"   Recommendation: Skip individual T4 imports, use summary totals only")
    
    staging['data_ready_for_import']['t4_slips'] = {
        'total_count': len(extracted['t4_slips']),
        'with_sin': sum(1 for t4 in extracted['t4_slips'] if t4.get('sin')),
        'import_action': 'SKIP_NEEDS_MANUAL_CORRECTION',
        'reason': 'Employee names are OCR errors (CRA PPU, RRO AE RPAP, etc.)'
    }
    
    # Validation warnings
    print(f"\n{'='*80}")
    print("VALIDATION WARNINGS")
    print("="*80)
    
    warnings = []
    
    # Check for database discrepancy
    if existing_payroll_records > 0:
        warnings.append({
            'severity': 'HIGH',
            'category': 'DATA_MISMATCH',
            'message': f'Database has {existing_payroll_records} 2013 payroll records totaling ${existing_gross_total:,.2f}',
            'recommendation': 'Compare T4 totals ($14,387.58 CPP, $7,137.61 EI) with database. Database may be incomplete.'
        })
    
    # Check for missing PD7A data
    if not any(r.get('gross_payroll') for r in extracted['pd7a_reports']):
        warnings.append({
            'severity': 'MEDIUM',
            'category': 'MISSING_DATA',
            'message': 'No monthly PD7A payroll details extracted (gross pay, deductions)',
            'recommendation': 'T4 Summary totals are sufficient for CRA compliance. Monthly details optional.'
        })
    
    # Check for missing T4 employee details
    if not any(t4.get('box_14') for t4 in extracted['t4_slips']):
        warnings.append({
            'severity': 'HIGH',
            'category': 'MISSING_DATA',
            'message': 'No T4 individual employee amounts extracted (Box 14 employment income)',
            'recommendation': 'Use T4 Summary aggregates only. Individual T4s need manual PDF review if required.'
        })
    
    for warning in warnings:
        print(f"\n{warning['severity']}: {warning['category']}")
        print(f"  {warning['message']}")
        print(f"  → {warning['recommendation']}")
    
    staging['validation_warnings'] = warnings
    
    # Import summary
    print(f"\n{'='*80}")
    print("IMPORT SUMMARY")
    print("="*80)
    
    import_summary = {
        't4_summary_records': len(t4_summary_records),
        't4_individual_slips': 0,  # Skipping due to OCR errors
        'pd7a_monthly_reports': 0,  # Skipping due to missing data
        'payroll_stub_details': 0,  # Skipping
        'total_records_to_import': len(t4_summary_records)
    }
    
    staging['import_summary'] = import_summary
    
    print(f"\nRecords ready for import:")
    for key, value in import_summary.items():
        if value > 0:
            print(f"  ✅ {key}: {value}")
        else:
            print(f"  ⏭️  {key}: {value} (skipped)")
    
    # Save staging file
    print(f"\n{'='*80}")
    print("SAVING STAGING DATA")
    print("="*80)
    
    with open(STAGING_FILE, 'w', encoding='utf-8') as f:
        json.dump(staging, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Staging data saved to: {STAGING_FILE}")
    print(f"   Size: {STAGING_FILE.stat().st_size:,} bytes")
    
    # Final recommendations
    print(f"\n{'='*80}")
    print("NEXT STEPS")
    print("="*80)
    
    print(f"\n1. REVIEW staging file: {STAGING_FILE}")
    print(f"2. VERIFY T4 Summary totals: CPP $14,387.58, EI $7,137.61")
    print(f"3. RUN import verification script (dry-run)")
    print(f"4. APPROVE and execute import")
    
    if existing_payroll_records > 0:
        print(f"\n⚠️  IMPORTANT: Database already has {existing_payroll_records} 2013 payroll records")
        print(f"   Consider if T4 Summary import would create duplicates")
        print(f"   Review database data first before importing")
    
    return staging


if __name__ == '__main__':
    generate_staging_data()
