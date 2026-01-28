#!/usr/bin/env python3
"""
LMS Payment Data Gap Summary Report
==================================

Quick summary of missing payment data discovered
"""

import pyodbc
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

LMS_PATH = r'L:\limo\backups\lms.mdb'
PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def main():
    print('🚨 CRITICAL: LMS PAYMENT DATA GAP DISCOVERED')
    print('=' * 60)

    try:
        # Connect to LMS
        lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
        lms_cur = lms_conn.cursor()
        
        # Connect to PostgreSQL  
        pg_conn = psycopg2.connect(**PG_CONFIG)
        pg_cur = pg_conn.cursor()
        
        # Get basic counts
        lms_cur.execute("SELECT COUNT(*) FROM Payment")
        lms_total = lms_cur.fetchone()[0]
        
        pg_cur.execute("SELECT COUNT(*) FROM payments")
        pg_total = pg_cur.fetchone()[0]
        
        print(f'📊 PAYMENT RECORD COUNTS:')
        print(f'   LMS (source):        {lms_total:>8,} payments')
        print(f'   PostgreSQL (target): {pg_total:>8,} payments')
        print(f'   Difference:          {pg_total - lms_total:>8,} ({((pg_total - lms_total)/lms_total*100):+.1f}%)')
        
        # Get financial totals
        lms_cur.execute("SELECT SUM(Amount) FROM Payment WHERE Amount IS NOT NULL")
        lms_total_amount = lms_cur.fetchone()[0] or 0
        
        pg_cur.execute("SELECT SUM(amount) FROM payments WHERE amount IS NOT NULL")
        pg_total_amount = pg_cur.fetchone()[0] or 0
        
        print(f'\n💰 PAYMENT AMOUNT TOTALS:')
        print(f'   LMS total:           ${lms_total_amount:>12,.2f}')
        print(f'   PostgreSQL total:    ${pg_total_amount:>12,.2f}')
        print(f'   Difference:          ${pg_total_amount - lms_total_amount:>12,.2f}')
        
        # Check payment key coverage
        lms_cur.execute("SELECT COUNT(*) FROM Payment WHERE [Key] IS NOT NULL")
        lms_with_keys = lms_cur.fetchone()[0]
        
        pg_cur.execute("SELECT COUNT(*) FROM payments WHERE payment_key IS NOT NULL")
        pg_with_keys = pg_cur.fetchone()[0]
        
        print(f'\n🔑 PAYMENT KEY COVERAGE:')
        print(f'   LMS with keys:       {lms_with_keys:>8,} ({lms_with_keys/lms_total*100:.1f}%)')
        print(f'   PostgreSQL with keys:{pg_with_keys:>8,} ({pg_with_keys/pg_total*100:.1f}%)')
        
        # Data quality check
        lms_cur.execute("SELECT COUNT(*) FROM Payment WHERE Amount IS NOT NULL AND Amount <> 0")
        lms_valid_amounts = lms_cur.fetchone()[0]
        
        pg_cur.execute("SELECT COUNT(*) FROM payments WHERE amount IS NOT NULL AND amount <> 0")
        pg_valid_amounts = pg_cur.fetchone()[0]
        
        print(f'\n[OK] DATA QUALITY:')
        print(f'   LMS valid amounts:   {lms_valid_amounts:>8,} ({lms_valid_amounts/lms_total*100:.1f}%)')
        print(f'   PostgreSQL valid:    {pg_valid_amounts:>8,} ({pg_valid_amounts/pg_total*100:.1f}%)')
        
        # Critical findings
        print(f'\n🎯 KEY FINDINGS:')
        
        if lms_total > 0 and pg_total > 0:
            if lms_total > pg_total:
                missing_count = lms_total - pg_total
                print(f'   🔴 CRITICAL: {missing_count:,} payments from LMS missing in PostgreSQL')
                print(f'   💰 Potential missing amount: ~${(missing_count * (lms_total_amount/lms_total)):,.2f}')
            elif pg_total > lms_total:
                extra_count = pg_total - lms_total
                print(f'   🟡 PostgreSQL has {extra_count:,} more payments than LMS')
                print(f'   📝 This could indicate additional payment sources (Square, etc.)')
            else:
                print(f'   [OK] Payment counts match between systems')
        
        # Data completeness assessment
        lms_completeness = (lms_with_keys / lms_total * 100) if lms_total > 0 else 0
        pg_completeness = (pg_with_keys / pg_total * 100) if pg_total > 0 else 0
        
        print(f'\n📋 DATA COMPLETENESS ASSESSMENT:')
        if lms_completeness > 90 and pg_completeness > 80:
            print(f'   [OK] Good: Both systems have high payment key coverage')
        elif lms_completeness > 90:
            print(f'   [WARN]  LMS data excellent, PostgreSQL needs improvement')
        elif pg_completeness > 80:
            print(f'   [WARN]  PostgreSQL good, LMS data may need cleanup')
        else:
            print(f'   🔴 Both systems have payment key coverage issues')
        
        print(f'\n🎯 RECOMMENDED ACTIONS:')
        
        if lms_total != pg_total:
            print(f'   1. 🔍 Investigate payment count discrepancy')
            print(f'   2. 📥 Consider running incremental payment import')
            print(f'   3. 🔗 Verify payment key matching logic')
        
        if abs(lms_total_amount - pg_total_amount) > 1000:
            print(f'   4. 💰 Investigate significant amount difference')
            
        if lms_completeness < 95 or pg_completeness < 85:
            print(f'   5. 🔑 Improve payment key coverage')
            
        print(f'\n[OK] Summary: {"CRITICAL ISSUES FOUND" if lms_total != pg_total or abs(lms_total_amount - pg_total_amount) > 1000 else "Data quality acceptable"}')
        
    except Exception as e:
        print(f'[FAIL] Analysis failed: {e}')
    finally:
        try:
            lms_conn.close()
            pg_conn.close()
        except:
            pass

if __name__ == "__main__":
    main()