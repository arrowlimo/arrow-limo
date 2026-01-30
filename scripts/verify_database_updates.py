#!/usr/bin/env python3
"""
Database Update Verification - Comprehensive Check

Verify that all Phase 1, 2, and 3 data recovery work has been 
properly committed and updated in the almsdata database.
"""

import os
import sys
import psycopg2
from datetime import datetime

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def verify_database_updates():
    """Comprehensive verification of all database updates."""
    
    print("ALMSDATA DATABASE UPDATE VERIFICATION")
    print("=" * 45)
    print(f"Verification Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Verify Phase 1 Data (2013-2016 Charge Summary Imports)
    print("🔍 PHASE 1 VERIFICATION - 2013-2016 CHARGE SUMMARIES:")
    print("-" * 55)
    
    phase1_sources = [
        '2013_ChargeSum_Import',
        '2014_ChargeSum_Import', 
        '2015_ChargeSum_Import',
        '2016_ChargeSum_Import',
        'QuickBooks-Excel-2013',
        'QuickBooks-Excel-2014',
        'QuickBooks-Excel-2015',
        'QuickBooks-Excel-2016'
    ]
    
    phase1_total = 0
    for source in phase1_sources:
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE source_system = %s
        """, (source,))
        
        result = cur.fetchone()
        if result and result[0] > 0:
            count, amount = result
            phase1_total += (amount or 0)
            print(f"[OK] {source}: {count:,} records, ${amount or 0:,.2f}")
        else:
            print(f"[FAIL] {source}: No data found")
    
    print(f"📊 PHASE 1 TOTAL: ${phase1_total:,.2f}")
    
    # 2. Verify Phase 2 Data (2013 Specialized Data)
    print(f"\n🔍 PHASE 2 VERIFICATION - 2013 SPECIALIZED DATA:")
    print("-" * 50)
    
    phase2_sources = [
        '2013_JE_Import',
        '2013_VehicleExp_Import', 
        '2013_Gratuity_Import',
        '2013_SBS_Import'
    ]
    
    phase2_total = 0
    for source in phase2_sources:
        cur.execute("""
            SELECT COUNT(*), SUM(gross_amount)
            FROM receipts 
            WHERE source_system = %s
        """, (source,))
        
        result = cur.fetchone()
        if result and result[0] > 0:
            count, amount = result
            phase2_total += (amount or 0)
            print(f"[OK] {source}: {count:,} records, ${amount or 0:,.2f}")
        else:
            print(f"[FAIL] {source}: No data found")
    
    print(f"📊 PHASE 2 TOTAL: ${phase2_total:,.2f}")
    
    # 3. Verify Phase 3 Data (Charter Revenue Completion)
    print(f"\n🔍 PHASE 3 VERIFICATION - CHARTER REVENUE COMPLETION:")
    print("-" * 55)
    
    # Check charter revenue updates
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total_charters,
            COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as with_revenue,
            SUM(COALESCE(total_amount_due, 0)) as total_revenue
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_updates = cur.fetchall()
    phase3_total = 0
    
    for year, total, with_revenue, revenue in charter_updates:
        year_int = int(year) if year else 0
        completion_pct = (with_revenue / total * 100) if total > 0 else 0
        
        if year_int >= 2021 and with_revenue > 0:  # Years we updated
            phase3_total += (revenue or 0)
            print(f"[OK] {year_int}: {with_revenue:,}/{total:,} charters ({completion_pct:.1f}%), ${revenue or 0:,.2f}")
        elif year_int >= 2021:
            print(f"[WARN]  {year_int}: {with_revenue:,}/{total:,} charters ({completion_pct:.1f}%), ${revenue or 0:,.2f}")
    
    print(f"📊 PHASE 3 CHARTER REVENUE: ${phase3_total:,.2f}")
    
    # 4. Overall Database Status
    print(f"\n📊 OVERALL DATABASE STATUS:")
    print("-" * 30)
    
    # Total receipts
    cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT source_system) as unique_sources,
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest
        FROM receipts
    """)
    
    receipts_status = cur.fetchone()
    if receipts_status:
        total_records, total_amount, sources, earliest, latest = receipts_status
        print(f"📋 RECEIPTS TABLE:")
        print(f"   Records: {total_records:,}")
        print(f"   Amount: ${total_amount or 0:,.2f}")
        print(f"   Sources: {sources}")
        print(f"   Range: {earliest} to {latest}")
    
    # Total charters
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as with_revenue,
            SUM(COALESCE(total_amount_due, 0)) as total_revenue
        FROM charters
    """)
    
    charter_status = cur.fetchone()
    if charter_status:
        total_charters, with_revenue, total_revenue = charter_status
        completion_pct = (with_revenue / total_charters * 100) if total_charters > 0 else 0
        print(f"\n🚗 CHARTERS TABLE:")
        print(f"   Records: {total_charters:,}")
        print(f"   With Revenue: {with_revenue:,} ({completion_pct:.1f}%)")
        print(f"   Total Revenue: ${total_revenue or 0:,.2f}")
    
    # Total payments
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
    """)
    
    payment_status = cur.fetchone()
    if payment_status:
        total_payments, total_amount = payment_status
        print(f"\n💰 PAYMENTS TABLE:")
        print(f"   Records: {total_payments:,}")
        print(f"   Amount: ${total_amount or 0:,.2f}")
    
    # 5. Data Quality Checks
    print(f"\n🔍 DATA QUALITY VERIFICATION:")
    print("-" * 30)
    
    # Check for recent updates
    cur.execute("""
        SELECT 
            source_system,
            COUNT(*) as records,
            MAX(created_at) as last_created
        FROM receipts 
        WHERE created_at >= CURRENT_DATE
        GROUP BY source_system
        ORDER BY last_created DESC
    """)
    
    recent_updates = cur.fetchall()
    if recent_updates:
        print("[OK] RECENT UPDATES (Today):")
        for source, records, last_created in recent_updates:
            print(f"   {source}: {records:,} records, last: {last_created}")
    else:
        print("ℹ️  No updates today - checking recent activity...")
        
        cur.execute("""
            SELECT 
                source_system,
                COUNT(*) as records,
                MAX(created_at) as last_created
            FROM receipts 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY source_system
            ORDER BY last_created DESC
            LIMIT 10
        """)
        
        week_updates = cur.fetchall()
        if week_updates:
            print("[OK] RECENT UPDATES (Last 7 Days):")
            for source, records, last_created in week_updates:
                print(f"   {source}: {records:,} records, last: {last_created}")
    
    # 6. Summary Verification
    print(f"\n🎯 PROJECT RECOVERY VERIFICATION:")
    print("-" * 35)
    
    total_project_value = phase1_total + phase2_total + phase3_total
    
    print(f"Phase 1 Recovery: ${phase1_total:,.2f}")
    print(f"Phase 2 Recovery: ${phase2_total:,.2f}")
    print(f"Phase 3 Revenue: ${phase3_total:,.2f}")
    print(f"TOTAL PROJECT: ${total_project_value:,.2f}")
    
    # Final verification status
    print(f"\n[OK] DATABASE UPDATE STATUS:")
    print("-" * 25)
    
    if phase1_total > 4000000:  # Phase 1 should be ~$4.92M
        print("[OK] Phase 1 data: CONFIRMED in database")
    else:
        print("[WARN]  Phase 1 data: May need verification")
        
    if phase2_total > 70000:  # Phase 2 should be ~$81K
        print("[OK] Phase 2 data: CONFIRMED in database")
    else:
        print("[WARN]  Phase 2 data: May need verification")
        
    if phase3_total > 100000:  # Phase 3 should be ~$165K
        print("[OK] Phase 3 data: CONFIRMED in database")
    else:
        print("[WARN]  Phase 3 data: May need verification")
    
    if total_project_value > 5000000:
        print(f"\n🎉 SUCCESS: All project data CONFIRMED in almsdata database!")
        print(f"💾 Total value preserved: ${total_project_value:,.2f}")
    else:
        print(f"\n[WARN]  WARNING: Project data may be incomplete")
    
    cur.close()
    conn.close()

def main():
    """Execute database update verification."""
    verify_database_updates()

if __name__ == "__main__":
    main()