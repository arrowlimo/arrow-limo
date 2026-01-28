"""
Execute 2013 T4 Summary import to driver_payroll table.

SAFETY FEATURES:
- Requires --write flag to execute (dry-run by default)
- Confirmation prompt before database changes
- Transaction rollback on error
- Deduplicates staging data (imports only 1 T4 Summary record)
- Post-import verification

Based on investigation findings:
- Database has 1,380 wage records with CPP $4,377.31 (30.4% of T4 total)
- T4 Summary shows authoritative CPP $14,387.58, EI $7,137.61
- Import adds T4 Summary as reference record for CRA compliance
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import argparse
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def execute_import(write_mode=False):
    """Execute 2013 T4 Summary import."""
    
    # Load staging data
    staging_path = r"l:\limo\data\2013_payroll_staging.json"
    with open(staging_path, 'r', encoding='utf-8') as f:
        staging = json.load(f)
    
    print("=" * 80)
    print("2013 T4 SUMMARY IMPORT EXECUTION")
    print("=" * 80)
    print()
    
    if not write_mode:
        print("⚠️  DRY-RUN MODE")
        print("   Add --write flag to execute actual import")
        print()
    
    # Extract T4 summary records and DEDUPLICATE
    t4_summaries = staging.get('data_ready_for_import', {}).get('t4_summary', [])
    
    print(f"Staging file has {len(t4_summaries)} T4 Summary records")
    
    # Deduplicate by comparing CPP/EI totals
    unique_summaries = {}
    for summary in t4_summaries:
        key = (
            summary.get('total_cpp', 0),
            summary.get('total_ei', 0),
            summary.get('total_employment_income', 0)
        )
        if key not in unique_summaries:
            unique_summaries[key] = summary
        else:
            print(f"  ⚠️  Skipping duplicate: {summary['source_file']}")
    
    print(f"After deduplication: {len(unique_summaries)} unique T4 Summary records")
    print()
    
    if not unique_summaries:
        print("❌ No unique T4 Summary records to import")
        return
    
    # Display records to be imported
    print("=" * 80)
    print("RECORDS TO IMPORT")
    print("=" * 80)
    
    for idx, summary in enumerate(unique_summaries.values(), 1):
        print(f"\n📄 Record {idx}")
        print(f"   Source: {summary['source_file']}")
        print(f"   Year: 2013")
        print(f"   CPP: ${float(summary['total_cpp']):,.2f}")
        print(f"   EI: ${float(summary['total_ei']):,.2f}")
        print(f"   Total Income: ${float(summary.get('total_employment_income', 0) or 0):,.2f}")
        print(f"   Total Employees: {summary.get('total_employees', 'N/A')}")
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get current database state
        print(f"\n{'='*80}")
        print("CURRENT DATABASE STATE (2013)")
        print("=" * 80)
        
        cur.execute("""
            SELECT 
                COUNT(*) as record_count,
                ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
                ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
                ROUND(SUM(COALESCE(tax, 0))::numeric, 2) as total_tax,
                ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
            FROM driver_payroll
            WHERE year = 2013
            AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        """)
        
        current = cur.fetchone()
        print(f"  Records: {current['record_count']}")
        print(f"  CPP: ${current['total_cpp']:,.2f}")
        print(f"  EI: ${current['total_ei']:,.2f}")
        print(f"  Tax: ${current['total_tax']:,.2f}")
        print(f"  Gross: ${current['total_gross']:,.2f}")
        
        # Check for existing T4 Summary records
        cur.execute("""
            SELECT COUNT(*) as count
            FROM driver_payroll
            WHERE year = 2013
            AND source LIKE '%T4_SUMMARY%'
        """)
        
        existing_t4 = cur.fetchone()['count']
        if existing_t4 > 0:
            print(f"\n⚠️  WARNING: {existing_t4} T4_SUMMARY records already exist in database")
        
        if write_mode:
            # Final confirmation
            print(f"\n{'='*80}")
            print("⚠️  CONFIRM IMPORT")
            print("=" * 80)
            print(f"\nThis will insert {len(unique_summaries)} T4 Summary record(s) into driver_payroll")
            print(f"Source will be marked as: T4_SUMMARY_2013_PDF")
            print(f"\nType 'yes' to proceed, anything else to cancel:")
            
            confirmation = input("> ").strip().lower()
            
            if confirmation != 'yes':
                print("\n❌ Import cancelled by user")
                return
            
            # Execute insert
            print(f"\n{'='*80}")
            print("EXECUTING IMPORT")
            print("=" * 80)
            
            inserted_count = 0
            for summary in unique_summaries.values():
                cur.execute("""
                    INSERT INTO driver_payroll (
                        year,
                        source,
                        cpp,
                        ei,
                        tax,
                        gross_pay,
                        payroll_class,
                        imported_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    2013,
                    'T4_SUMMARY_2013_PDF',
                    Decimal(str(summary['total_cpp'])),
                    Decimal(str(summary['total_ei'])),
                    Decimal(str(summary.get('total_income_tax') or 0)),
                    Decimal(str(summary.get('total_employment_income') or 0)),
                    'T4_SUMMARY',
                    datetime.now()
                ))
                
                record_id = cur.fetchone()['id']
                inserted_count += 1
                print(f"  ✅ Inserted T4 Summary record (id: {record_id})")
            
            conn.commit()
            print(f"\n✅ Successfully imported {inserted_count} T4 Summary record(s)")
            
            # Post-import verification
            print(f"\n{'='*80}")
            print("POST-IMPORT VERIFICATION")
            print("=" * 80)
            
            cur.execute("""
                SELECT 
                    COUNT(*) as record_count,
                    ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
                    ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
                    ROUND(SUM(COALESCE(tax, 0))::numeric, 2) as total_tax,
                    ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
                FROM driver_payroll
                WHERE year = 2013
                AND (payroll_class = 'WAGE' OR payroll_class = 'T4_SUMMARY')
            """)
            
            after = cur.fetchone()
            print(f"\nUpdated totals (including T4_SUMMARY):")
            print(f"  Records: {after['record_count']} (was {current['record_count']})")
            print(f"  CPP: ${after['total_cpp']:,.2f} (was ${current['total_cpp']:,.2f})")
            print(f"  EI: ${after['total_ei']:,.2f} (was ${current['total_ei']:,.2f})")
            print(f"  Tax: ${after['total_tax']:,.2f} (was ${current['total_tax']:,.2f})")
            print(f"  Gross: ${after['total_gross']:,.2f} (was ${current['total_gross']:,.2f})")
            
            # Show T4 Summary records
            cur.execute("""
                SELECT 
                    id,
                    source,
                    ROUND(cpp::numeric, 2) as cpp,
                    ROUND(ei::numeric, 2) as ei,
                    ROUND(COALESCE(tax, 0)::numeric, 2) as tax,
                    ROUND(COALESCE(gross_pay, 0)::numeric, 2) as gross,
                    imported_at
                FROM driver_payroll
                WHERE year = 2013
                AND source LIKE '%T4_SUMMARY%'
                ORDER BY imported_at DESC
            """)
            
            print(f"\n{'='*80}")
            print("T4_SUMMARY RECORDS IN DATABASE")
            print("=" * 80)
            
            for row in cur.fetchall():
                print(f"\nID: {row['id']}")
                print(f"  Source: {row['source']}")
                print(f"  CPP: ${row['cpp']:,.2f}")
                print(f"  EI: ${row['ei']:,.2f}")
                print(f"  Tax: ${row['tax']:,.2f}")
                print(f"  Gross: ${row['gross']:,.2f}")
                print(f"  Imported: {row['imported_at']}")
            
            print(f"\n{'='*80}")
            print("✅ IMPORT COMPLETE")
            print("=" * 80)
            print(f"\nT4 Summary totals now preserved in database for CRA compliance")
            print(f"Use WHERE payroll_class = 'T4_SUMMARY' to query these records")
            
        else:
            print(f"\n{'='*80}")
            print("DRY-RUN COMPLETE")
            print("=" * 80)
            print(f"\n✅ Validation passed")
            print(f"✅ {len(unique_summaries)} unique T4 Summary record(s) ready to import")
            print(f"\nTo execute actual import:")
            print(f"  python -X utf8 scripts/execute_2013_import.py --write")
    
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        print(f"\nTransaction rolled back - no changes made")
        raise
    
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute 2013 T4 Summary import')
    parser.add_argument('--write', action='store_true', 
                       help='Execute actual import (default is dry-run)')
    
    args = parser.parse_args()
    execute_import(write_mode=args.write)
