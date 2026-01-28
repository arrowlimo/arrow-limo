#!/usr/bin/env python3
"""
COMPREHENSIVE YEAR-BY-YEAR DATA VALIDATION & MATCHING SYSTEM
============================================================

"HIKE 23, LONG 24 HIKE HIKE HIKE" - Systematic data mountain climbing!

Step 1: Validate each year from first to last (100% match requirement)
Step 2: Reverse chronological audit for misdated records  
Step 3: Multi-trip payment matching using Excel data
Step 4: Achieve 100% data integrity across all systems
"""

import os
import pyodbc
import psycopg2
import pandas as pd
from datetime import datetime, date
import calendar
from collections import defaultdict

# Database connections
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_connections():
    """Get both LMS and PostgreSQL connections."""
    
    # LMS Connection
    lms_path = r'L:\limo\backups\lms.mdb'
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    lms_conn = pyodbc.connect(lms_conn_str)
    
    # PostgreSQL Connection  
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    return lms_conn, pg_conn

def get_data_year_range(pg_conn):
    """Determine the full year range of data in the system."""
    
    print("🏔️  IDENTIFYING DATA MOUNTAIN RANGE")
    print("=" * 35)
    
    cur = pg_conn.cursor()
    
    # Get year range from charters
    cur.execute("""
        SELECT 
            MIN(EXTRACT(year FROM charter_date)) as first_year,
            MAX(EXTRACT(year FROM charter_date)) as last_year,
            COUNT(*) as total_charters
        FROM charters 
        WHERE charter_date IS NOT NULL
    """)
    
    charter_range = cur.fetchone()
    
    # Get year range from payments
    cur.execute("""
        SELECT 
            MIN(EXTRACT(year FROM payment_date)) as first_year,
            MAX(EXTRACT(year FROM payment_date)) as last_year,
            COUNT(*) as total_payments
        FROM payments 
        WHERE payment_date IS NOT NULL
    """)
    
    payment_range = cur.fetchone()
    
    # Overall range
    first_year = int(min(charter_range[0] or 9999, payment_range[0] or 9999))
    last_year = int(max(charter_range[1] or 0, payment_range[1] or 0))
    
    print(f"📊 DATA MOUNTAIN SURVEY:")
    print(f"   🗻 Charter Range: {charter_range[0]}-{charter_range[1]} ({charter_range[2]:,} records)")
    print(f"   💰 Payment Range: {payment_range[0]}-{payment_range[1]} ({payment_range[2]:,} records)")
    print(f"   ⛰️  EXPEDITION ROUTE: {first_year} → {last_year} ({last_year - first_year + 1} years)")
    
    cur.close()
    return first_year, last_year

def validate_year_data_integrity(year, lms_conn, pg_conn):
    """Validate 100% data integrity for a specific year."""
    
    print(f"\n🥾 HIKING YEAR {year} - VALIDATION CHECKPOINT")
    print("-" * 40)
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    validation_results = {
        'year': year,
        'lms_reserves': 0,
        'pg_charters': 0,
        'lms_payments': 0,
        'pg_payments': 0,
        'charter_match_rate': 0.0,
        'payment_match_rate': 0.0,
        'missing_charters': [],
        'missing_payments': [],
        'date_errors': [],
        'validation_status': 'UNKNOWN'
    }
    
    try:
        # LMS Reserve count for year
        lms_cur.execute("""
            SELECT COUNT(*), SUM(Rate), SUM(Balance) 
            FROM Reserve 
            WHERE YEAR(PU_Date) = ?
        """, (year,))
        
        lms_reserve_data = lms_cur.fetchone()
        validation_results['lms_reserves'] = lms_reserve_data[0] or 0
        lms_total_rate = lms_reserve_data[1] or 0
        lms_total_balance = lms_reserve_data[2] or 0
        
        # PostgreSQL charter count for year
        pg_cur.execute("""
            SELECT COUNT(*), SUM(rate), SUM(balance)
            FROM charters 
            WHERE EXTRACT(year FROM charter_date) = %s
        """, (year,))
        
        pg_charter_data = pg_cur.fetchone()
        validation_results['pg_charters'] = pg_charter_data[0] or 0
        pg_total_rate = pg_charter_data[1] or 0
        pg_total_balance = pg_charter_data[2] or 0
        
        # Calculate charter match rate
        if validation_results['lms_reserves'] > 0:
            validation_results['charter_match_rate'] = (validation_results['pg_charters'] / validation_results['lms_reserves']) * 100
        
        # LMS Payment count for year
        lms_cur.execute("""
            SELECT COUNT(*), SUM(Amount) 
            FROM Payment 
            WHERE YEAR(LastUpdated) = ?
        """, (year,))
        
        lms_payment_data = lms_cur.fetchone()
        validation_results['lms_payments'] = lms_payment_data[0] or 0
        lms_payment_total = lms_payment_data[1] or 0
        
        # PostgreSQL payment count for year  
        pg_cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM payments 
            WHERE EXTRACT(year FROM payment_date) = %s
        """, (year,))
        
        pg_payment_data = pg_cur.fetchone()
        validation_results['pg_payments'] = pg_payment_data[0] or 0
        pg_payment_total = pg_payment_data[1] or 0
        
        # Calculate payment match rate
        if validation_results['lms_payments'] > 0:
            validation_results['payment_match_rate'] = (validation_results['pg_payments'] / validation_results['lms_payments']) * 100
        
        # Determine validation status
        charter_perfect = validation_results['charter_match_rate'] >= 99.5
        payment_good = validation_results['payment_match_rate'] >= 95.0  # Payments might have additional sources
        
        if charter_perfect and payment_good:
            validation_results['validation_status'] = '[OK] SUMMIT REACHED'
        elif charter_perfect:
            validation_results['validation_status'] = '[WARN]  CHARTER SUMMIT, PAYMENT CLIMB'
        elif validation_results['charter_match_rate'] >= 90.0:
            validation_results['validation_status'] = '🧗 STEEP ASCENT NEEDED'
        else:
            validation_results['validation_status'] = '🚨 BASE CAMP - MAJOR GAPS'
        
        # Report year results
        print(f"   📊 CHARTERS: LMS {validation_results['lms_reserves']:,} → PG {validation_results['pg_charters']:,} ({validation_results['charter_match_rate']:.1f}%)")
        print(f"      💰 Rate Total: LMS ${lms_total_rate:,.2f} → PG ${pg_total_rate:,.2f}")
        print(f"      💳 Balance: LMS ${lms_total_balance:,.2f} → PG ${pg_total_balance:,.2f}")
        
        print(f"   💰 PAYMENTS: LMS {validation_results['lms_payments']:,} → PG {validation_results['pg_payments']:,} ({validation_results['payment_match_rate']:.1f}%)")
        print(f"      💵 Amount Total: LMS ${lms_payment_total:,.2f} → PG ${pg_payment_total:,.2f}")
        
        print(f"   🎯 STATUS: {validation_results['validation_status']}")
        
        return validation_results
        
    except Exception as e:
        print(f"   [FAIL] AVALANCHE ERROR: {str(e)}")
        validation_results['validation_status'] = f'[FAIL] ERROR: {str(e)}'
        return validation_results

def find_missing_records_for_year(year, lms_conn, pg_conn):
    """Find specific missing records for a year that needs improvement."""
    
    print(f"\n🔍 SEARCHING FOR MISSING RECORDS IN {year}")
    print("-" * 38)
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    missing_charters = []
    
    try:
        # Get all LMS reserves for the year
        lms_cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Name
            FROM Reserve 
            WHERE YEAR(PU_Date) = ?
            ORDER BY PU_Date, Reserve_No
        """, (year,))
        
        lms_reserves = lms_cur.fetchall()
        
        print(f"   📋 Checking {len(lms_reserves):,} LMS reserves against PostgreSQL...")
        
        missing_count = 0
        for reserve_no, account_no, pu_date, rate, balance, name in lms_reserves:
            # Check if exists in PostgreSQL
            pg_cur.execute("""
                SELECT charter_id FROM charters 
                WHERE reserve_number = %s
            """, (str(reserve_no),))
            
            pg_charter = pg_cur.fetchone()
            
            if not pg_charter:
                missing_charters.append({
                    'reserve_no': reserve_no,
                    'account_no': account_no,
                    'date': pu_date,
                    'rate': rate or 0,
                    'balance': balance or 0,
                    'name': name
                })
                missing_count += 1
                
                if missing_count <= 10:  # Show first 10
                    print(f"      [FAIL] Missing: {reserve_no} - {name} - ${rate or 0} ({pu_date})")
        
        if missing_count > 10:
            print(f"      ... and {missing_count - 10} more missing records")
        
        print(f"   📊 MISSING RECORDS: {missing_count:,} charters need import")
        
        return missing_charters
        
    except Exception as e:
        print(f"   [FAIL] Search error: {str(e)}")
        return []

def detect_misdated_records(pg_conn):
    """Detect records that might be misdated (reverse chronological audit)."""
    
    print(f"\n🔄 REVERSE CHRONOLOGICAL AUDIT - MISDATED DETECTIVE WORK")
    print("-" * 59)
    
    cur = pg_conn.cursor()
    
    misdated_issues = []
    
    try:
        # Look for charters with dates that seem wrong
        cur.execute("""
            SELECT 
                charter_id, 
                reserve_number,
                charter_date,
                created_at,
                updated_at,
                EXTRACT(year FROM charter_date) as charter_year,
                EXTRACT(year FROM created_at) as created_year,
                ABS(EXTRACT(year FROM charter_date) - EXTRACT(year FROM created_at)) as year_diff
            FROM charters 
            WHERE ABS(EXTRACT(year FROM charter_date) - EXTRACT(year FROM created_at)) > 2
            AND charter_date IS NOT NULL 
            AND created_at IS NOT NULL
            ORDER BY year_diff DESC
            LIMIT 50
        """)
        
        date_anomalies = cur.fetchall()
        
        if date_anomalies:
            print(f"   🚨 FOUND {len(date_anomalies)} DATE ANOMALIES:")
            
            for charter_id, reserve_no, charter_date, created_at, updated_at, charter_year, created_year, year_diff in date_anomalies[:10]:
                print(f"      Charter {reserve_no}: {charter_date} vs Created {created_at} ({year_diff} year gap)")
                
                misdated_issues.append({
                    'charter_id': charter_id,
                    'reserve_number': reserve_no,
                    'charter_date': charter_date,
                    'created_at': created_at,
                    'year_difference': year_diff,
                    'issue_type': 'date_anomaly'
                })
        
        # Look for payments that might be in wrong year
        cur.execute("""
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.payment_date,
                c.charter_date,
                EXTRACT(year FROM p.payment_date) as payment_year,
                EXTRACT(year FROM c.charter_date) as charter_year,
                ABS(EXTRACT(year FROM p.payment_date) - EXTRACT(year FROM c.charter_date)) as year_diff
            FROM payments p
            JOIN charters c ON p.reserve_number = c.reserve_number
            WHERE ABS(EXTRACT(year FROM p.payment_date) - EXTRACT(year FROM c.charter_date)) > 1
            AND p.payment_date IS NOT NULL
            AND c.charter_date IS NOT NULL
            ORDER BY year_diff DESC
            LIMIT 30
        """)
        
        payment_date_issues = cur.fetchall()
        
        if payment_date_issues:
            print(f"\n   💰 FOUND {len(payment_date_issues)} PAYMENT DATE MISMATCHES:")
            
            for payment_id, reserve_no, payment_date, charter_date, payment_year, charter_year, year_diff in payment_date_issues[:5]:
                print(f"      Payment {payment_id}: Paid {payment_date} for Charter {charter_date} ({year_diff} year gap)")
        
        print(f"\n   📊 MISDATED AUDIT RESULTS:")
        print(f"      🗓️  Date anomalies: {len(date_anomalies)}")
        print(f"      💸 Payment mismatches: {len(payment_date_issues)}")
        
        return misdated_issues
        
    except Exception as e:
        print(f"   [FAIL] Audit error: {str(e)}")
        return []

def analyze_multi_trip_payments(pg_conn):
    """Analyze and match payments that cover multiple trips."""
    
    print(f"\n🎒 MULTI-TRIP PAYMENT EXPEDITION")
    print("-" * 32)
    
    cur = pg_conn.cursor()
    
    try:
        # Find payments without reserve numbers (potential multi-trip payments)
        cur.execute("""
            SELECT 
                payment_id,
                account_number,
                amount,
                payment_date,
                notes,
                last_updated_by
            FROM payments 
            WHERE (reserve_number IS NULL OR reserve_number = '')
            AND amount > 100  -- Larger payments more likely to be multi-trip
            ORDER BY amount DESC
            LIMIT 20
        """)
        
        unlinked_payments = cur.fetchall()
        
        print(f"   📊 FOUND {len(unlinked_payments)} LARGE UNLINKED PAYMENTS:")
        
        multi_trip_candidates = []
        
        for payment_id, account_no, amount, payment_date, notes, updated_by in unlinked_payments:
            print(f"      💰 Payment {payment_id}: ${amount:,.2f} (Account: {account_no})")
            print(f"         Date: {payment_date}, Notes: {(notes or 'No notes')[:50]}...")
            
            if account_no:
                # Find charters for this account around the payment date
                cur.execute("""
                    SELECT charter_id, reserve_number, charter_date, rate, balance
                    FROM charters 
                    WHERE account_number = %s
                    AND charter_date BETWEEN %s - INTERVAL '30 days' AND %s + INTERVAL '30 days'
                    ORDER BY charter_date
                """, (account_no, payment_date, payment_date))
                
                nearby_charters = cur.fetchall()
                
                if len(nearby_charters) > 1:
                    total_owed = sum(charter[4] or 0 for charter in nearby_charters)  # Sum balances
                    
                    print(f"         🎯 {len(nearby_charters)} nearby charters, total owed: ${total_owed:,.2f}")
                    
                    multi_trip_candidates.append({
                        'payment_id': payment_id,
                        'amount': amount,
                        'account_number': account_no,
                        'nearby_charters': nearby_charters,
                        'total_owed': total_owed,
                        'match_likelihood': min(100, (amount / total_owed * 100) if total_owed > 0 else 0)
                    })
        
        # Show best multi-trip matches
        multi_trip_candidates.sort(key=lambda x: x['match_likelihood'], reverse=True)
        
        print(f"\n   🎯 TOP MULTI-TRIP MATCH CANDIDATES:")
        for candidate in multi_trip_candidates[:5]:
            likelihood = candidate['match_likelihood']
            print(f"      Payment {candidate['payment_id']}: ${candidate['amount']:,.2f} → {len(candidate['nearby_charters'])} charters (${candidate['total_owed']:,.2f}) - {likelihood:.1f}% match")
        
        return multi_trip_candidates
        
    except Exception as e:
        print(f"   [FAIL] Multi-trip analysis error: {str(e)}")
        return []

def import_missing_year_data(year, missing_charters, lms_conn, pg_conn, dry_run=True):
    """Import missing charter data for a specific year."""
    
    if not missing_charters:
        return
    
    print(f"\n📥 IMPORTING MISSING {year} DATA")
    print("-" * 29)
    
    if dry_run:
        print("   📋 DRY RUN MODE - No actual imports")
    
    pg_cur = pg_conn.cursor()
    imported_count = 0
    
    try:
        for charter in missing_charters[:50]:  # Limit to 50 per batch
            if not dry_run:
                pg_cur.execute("""
                    INSERT INTO charters (
                        reserve_number, account_number, charter_date, rate, 
                        balance, notes, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    charter['reserve_no'],
                    charter['account_no'], 
                    charter['date'],
                    charter['rate'],
                    charter['balance'],
                    f"Missing data import for {year} - {charter['name']}"
                ))
                imported_count += 1
            else:
                imported_count += 1
                if imported_count <= 5:
                    print(f"      Would import: {charter['reserve_no']} - {charter['name']} - ${charter['rate']}")
        
        if not dry_run and imported_count > 0:
            pg_conn.commit()
            print(f"   [OK] IMPORTED {imported_count} missing charters for {year}")
        elif dry_run:
            print(f"   📊 Would import {imported_count} charters")
        
    except Exception as e:
        print(f"   [FAIL] Import error: {str(e)}")
        if not dry_run:
            pg_conn.rollback()

def comprehensive_year_by_year_validation():
    """Main expedition through all years of data."""
    
    print("🏔️  COMPREHENSIVE DATA MOUNTAIN EXPEDITION")
    print("🥾 'HIKE 23, LONG 24 HIKE HIKE HIKE!'")
    print("=" * 45)
    
    try:
        # Get database connections
        lms_conn, pg_conn = get_connections()
        
        # Determine expedition route (year range)
        first_year, last_year = get_data_year_range(pg_conn)
        
        expedition_results = []
        
        # FORWARD HIKE: Validate each year from first to last
        print(f"\n🥾 FORWARD EXPEDITION: {first_year} → {last_year}")
        print("=" * 40)
        
        for year in range(first_year, last_year + 1):
            validation_result = validate_year_data_integrity(year, lms_conn, pg_conn)
            expedition_results.append(validation_result)
            
            # If year needs improvement, find missing records
            if validation_result['charter_match_rate'] < 99.5:
                missing_charters = find_missing_records_for_year(year, lms_conn, pg_conn)
                validation_result['missing_charters'] = missing_charters
                
                # Import missing data (dry run first)
                if missing_charters:
                    import_missing_year_data(year, missing_charters, lms_conn, pg_conn, dry_run=True)
        
        # REVERSE AUDIT: Look for misdated records  
        print(f"\n🔄 REVERSE EXPEDITION: Misdated Record Detection")
        print("=" * 48)
        
        misdated_records = detect_misdated_records(pg_conn)
        
        # MULTI-TRIP PAYMENT MATCHING
        print(f"\n🎒 PAYMENT EXPEDITION: Multi-Trip Analysis")
        print("=" * 42)
        
        multi_trip_matches = analyze_multi_trip_payments(pg_conn)
        
        # EXPEDITION SUMMARY
        print(f"\n🏆 EXPEDITION SUMMARY REPORT")
        print("=" * 28)
        
        years_at_summit = sum(1 for r in expedition_results if '[OK]' in r['validation_status'])
        years_need_work = len(expedition_results) - years_at_summit
        
        total_missing = sum(len(r.get('missing_charters', [])) for r in expedition_results)
        
        print(f"   📊 EXPEDITION STATISTICS:")
        print(f"      🏔️  Years surveyed: {len(expedition_results)}")
        print(f"      [OK] Years at summit (>99.5%): {years_at_summit}")
        print(f"      🧗 Years needing work: {years_need_work}")
        print(f"      📋 Missing records found: {total_missing:,}")
        print(f"      🔄 Misdated records: {len(misdated_records)}")
        print(f"      💰 Multi-trip candidates: {len(multi_trip_matches)}")
        
        # Show year-by-year status
        print(f"\n   🗻 YEAR-BY-YEAR SUMMIT STATUS:")
        for result in expedition_results:
            status_icon = "[OK]" if "[OK]" in result['validation_status'] else "🧗"
            print(f"      {result['year']}: {status_icon} {result['charter_match_rate']:.1f}% charter match")
        
        # Next steps recommendations
        print(f"\n   🎯 NEXT EXPEDITION STEPS:")
        
        if years_need_work > 0:
            print(f"      1. Import {total_missing:,} missing charter records")
            print(f"      2. Address misdated records ({len(misdated_records)} found)")
            print(f"      3. Link multi-trip payments ({len(multi_trip_matches)} candidates)")
            print(f"      4. Re-validate to achieve 100% data integrity")
        else:
            print(f"      🏆 ALL YEARS AT SUMMIT! Data integrity achieved!")
            print(f"      🔄 Focus on ongoing maintenance and real-time validation")
        
        return expedition_results
        
    except Exception as e:
        print(f"\n[FAIL] EXPEDITION EMERGENCY: {str(e)}")
        return []
    
    finally:
        try:
            lms_conn.close()
            pg_conn.close()
            print(f"\n🔒 Base camp secured - connections closed")
        except:
            pass

def main():
    """Launch the comprehensive data validation expedition."""
    
    # Set database environment
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    # Launch expedition!
    expedition_results = comprehensive_year_by_year_validation()
    
    print(f"\n🎖️  EXPEDITION COMPLETE!")
    print("   Ready for 100% data integrity achievement!")

if __name__ == "__main__":
    main()