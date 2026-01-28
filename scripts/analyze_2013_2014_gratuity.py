#!/usr/bin/env python3
"""
Analyze 2013-2014 gratuity data to determine if direct tips treatment continued.

Compares 2013-2014 patterns against pre-2013 baseline to identify any changes
in how gratuity was handled (direct tips vs controlled tips).
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("2013-2014 GRATUITY ANALYSIS - COMPARING TO PRE-2013 BASELINE")
    print("=" * 80)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Charter gratuity comparison
    print("=" * 80)
    print("1. CHARTER GRATUITY DATA COMPARISON")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN EXTRACT(YEAR FROM charter_date) < 2013 THEN 'Pre-2013'
                WHEN EXTRACT(YEAR FROM charter_date) = 2013 THEN '2013'
                WHEN EXTRACT(YEAR FROM charter_date) = 2014 THEN '2014'
            END as period,
            COUNT(*) as charter_count,
            SUM(driver_gratuity) as total_gratuity,
            SUM(driver_total) as total_driver_pay,
            AVG(driver_gratuity) as avg_gratuity,
            AVG(driver_total) as avg_driver_pay,
            MIN(charter_date) as earliest,
            MAX(charter_date) as latest
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2007 AND 2014
        AND driver_gratuity > 0
        GROUP BY CASE 
            WHEN EXTRACT(YEAR FROM charter_date) < 2013 THEN 'Pre-2013'
            WHEN EXTRACT(YEAR FROM charter_date) = 2013 THEN '2013'
            WHEN EXTRACT(YEAR FROM charter_date) = 2014 THEN '2014'
        END
        ORDER BY MIN(charter_date)
    """)
    
    print("\nGratuity by period:")
    print(f"{'Period':<12} {'Charters':<10} {'Total Gratuity':<16} {'Avg Gratuity':<14} {'Avg Driver Pay':<16}")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<12} {row[1]:<10,} ${row[2]:<15,.2f} ${row[4]:<13,.2f} ${row[5]:<15,.2f}")
    
    # 2. Payroll-Charter linkage comparison
    print("\n" + "=" * 80)
    print("2. PAYROLL-CHARTER LINKAGE (Gratuity Inclusion Test)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN dp.year < 2013 THEN 'Pre-2013'
                WHEN dp.year = 2013 THEN '2013'
                WHEN dp.year = 2014 THEN '2014'
            END as period,
            COUNT(*) as records,
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(dp.gross_pay) as payroll_gross,
            SUM(c.driver_total - c.driver_gratuity) as charter_base_pay,
            SUM(c.driver_total) as charter_total_pay
        FROM driver_payroll dp
        JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.year BETWEEN 2007 AND 2014
        AND c.driver_gratuity > 0
        AND dp.gross_pay IS NOT NULL
        GROUP BY CASE 
            WHEN dp.year < 2013 THEN 'Pre-2013'
            WHEN dp.year = 2013 THEN '2013'
            WHEN dp.year = 2014 THEN '2014'
        END
        ORDER BY MIN(dp.year)
    """)
    
    print("\nPayroll vs Charter amounts:")
    print(f"{'Period':<12} {'Records':<10} {'Charter Grat':<15} {'Payroll Gross':<16} {'Charter Base':<15} {'Ratio':<10}")
    print("-" * 80)
    
    results = []
    for row in cur.fetchall():
        period = row[0]
        records = row[1]
        charter_grat = float(row[2]) if row[2] else 0
        payroll_gross = float(row[3]) if row[3] else 0
        charter_base = float(row[4]) if row[4] else 0
        charter_total = float(row[5]) if row[5] else 0
        
        # Calculate ratio: if gross matches base, gratuity is excluded
        # if gross matches total, gratuity is included
        if charter_base > 0:
            base_ratio = payroll_gross / charter_base
        else:
            base_ratio = 0
            
        if charter_total > 0:
            total_ratio = payroll_gross / charter_total
        else:
            total_ratio = 0
        
        # Determine which is closer
        if abs(base_ratio - 1.0) < abs(total_ratio - 1.0):
            ratio_type = f"{base_ratio:.2%} (base)"
            interpretation = "EXCLUDED" if base_ratio > 0.90 else "UNCLEAR"
        else:
            ratio_type = f"{total_ratio:.2%} (total)"
            interpretation = "INCLUDED" if total_ratio > 0.90 else "UNCLEAR"
        
        results.append((period, records, charter_grat, payroll_gross, charter_base, ratio_type, interpretation))
        print(f"{period:<12} {records:<10,} ${charter_grat:<14,.2f} ${payroll_gross:<15,.2f} ${charter_base:<14,.2f} {ratio_type:<10}")
    
    # 3. Interpretation
    print("\n" + "=" * 80)
    print("3. GRATUITY INCLUSION INTERPRETATION")
    print("=" * 80)
    
    for period, records, charter_grat, payroll_gross, charter_base, ratio_type, interpretation in results:
        print(f"\n{period}:")
        print(f"  Payroll gross pay: ${payroll_gross:,.2f}")
        print(f"  Charter base pay (excl. gratuity): ${charter_base:,.2f}")
        print(f"  Charter gratuity: ${charter_grat:,.2f}")
        print(f"  Ratio: {ratio_type}")
        
        if interpretation == "EXCLUDED":
            print(f"  ✓ INTERPRETATION: Gratuity EXCLUDED from gross_pay (direct tips)")
        elif interpretation == "INCLUDED":
            print(f"  [WARN]  INTERPRETATION: Gratuity INCLUDED in gross_pay (controlled tips)")
        else:
            print(f"  ❓ INTERPRETATION: Unclear - needs manual review")
    
    # 4. T4 Box 14 comparison
    print("\n" + "=" * 80)
    print("4. T4 BOX 14 EMPLOYMENT INCOME ANALYSIS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            year,
            COUNT(*) as records,
            COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) as has_t4,
            SUM(t4_box_14) as total_t4,
            SUM(gross_pay) as total_gross,
            SUM(t4_box_14) - SUM(gross_pay) as t4_gross_diff
        FROM driver_payroll
        WHERE year BETWEEN 2007 AND 2014
        GROUP BY year
        HAVING COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) > 0
        ORDER BY year
    """)
    
    t4_rows = cur.fetchall()
    if len(t4_rows) > 0:
        print("\nT4 Box 14 vs Gross Pay by year:")
        print(f"{'Year':<6} {'Records':<10} {'With T4':<10} {'T4 Box 14':<16} {'Gross Pay':<16} {'Difference':<14}")
        print("-" * 80)
        
        for row in t4_rows:
            year = int(row[0])
            records = row[1]
            has_t4 = row[2]
            t4 = row[3] if row[3] else 0
            gross = row[4] if row[4] else 0
            diff = row[5] if row[5] else 0
            
            print(f"{year:<6} {records:<10,} {has_t4:<10,} ${t4:<15,.2f} ${gross:<15,.2f} ${diff:<13,.2f}")
    else:
        print("\nNo T4 Box 14 data available for 2007-2014")
    
    # 5. Income ledger comparison
    print("\n" + "=" * 80)
    print("5. INCOME LEDGER REVENUE ANALYSIS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN EXTRACT(YEAR FROM c.charter_date) < 2013 THEN 'Pre-2013'
                WHEN EXTRACT(YEAR FROM c.charter_date) = 2013 THEN '2013'
                WHEN EXTRACT(YEAR FROM c.charter_date) = 2014 THEN '2014'
            END as period,
            COUNT(DISTINCT c.charter_id) as charters_with_gratuity,
            COUNT(il.income_id) as income_ledger_entries,
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(c.total_amount_due) as charter_revenue,
            SUM(il.gross_amount) as ledger_revenue
        FROM charters c
        LEFT JOIN income_ledger il ON c.charter_id = il.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2014
        AND c.driver_gratuity > 0
        GROUP BY CASE 
            WHEN EXTRACT(YEAR FROM c.charter_date) < 2013 THEN 'Pre-2013'
            WHEN EXTRACT(YEAR FROM c.charter_date) = 2013 THEN '2013'
            WHEN EXTRACT(YEAR FROM c.charter_date) = 2014 THEN '2014'
        END
        ORDER BY MIN(c.charter_date)
    """)
    
    print("\nRevenue recording by period:")
    print(f"{'Period':<12} {'Charters':<10} {'Charter Grat':<15} {'Charter Rev':<15} {'Ledger Rev':<15} {'Analysis':<20}")
    print("-" * 100)
    
    for row in cur.fetchall():
        period = row[0]
        charters = row[1]
        charter_grat = float(row[2]) if row[2] else 0
        charter_rev = float(row[3]) if row[3] else 0
        ledger_rev = float(row[4]) if row[4] else 0
        
        # If ledger_rev is close to charter_rev, gratuity not in revenue
        # If ledger_rev is close to charter_rev + gratuity, gratuity is in revenue
        if ledger_rev > 0 and charter_rev > 0:
            ledger_charter_ratio = ledger_rev / charter_rev
            ledger_with_grat_ratio = ledger_rev / (charter_rev + charter_grat) if (charter_rev + charter_grat) > 0 else 0
            
            if abs(ledger_charter_ratio - 1.0) < 0.20:
                analysis = "Grat NOT in revenue"
            elif abs(ledger_with_grat_ratio - 1.0) < 0.20:
                analysis = "Grat IN revenue"
            else:
                analysis = f"Unclear ({ledger_charter_ratio:.1%})"
        else:
            analysis = "No ledger data"
        
        print(f"{period:<12} {charters:<10,} ${charter_grat:<14,.2f} ${charter_rev:<14,.2f} ${ledger_rev:<14,.2f} {analysis:<20}")
    
    # 6. Summary comparison
    print("\n" + "=" * 80)
    print("6. SUMMARY: DID GRATUITY TREATMENT CHANGE?")
    print("=" * 80)
    
    print("\nDirect Tips Indicators (comparing 2013-2014 to Pre-2013):")
    print()
    print("Pre-2013 Baseline:")
    print("  ✓ Gratuity EXCLUDED from payroll gross_pay (95.85% base ratio)")
    print("  ✓ Gratuity SEPARATE from income ledger revenue")
    print("  ✓ No T4 Box 14 data (not reported as employment income)")
    print()
    
    # Analyze 2013
    cur.execute("""
        SELECT 
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(dp.gross_pay) as payroll_gross,
            SUM(c.driver_total - c.driver_gratuity) as charter_base_pay,
            SUM(c.driver_total) as charter_total_pay
        FROM driver_payroll dp
        JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.year = 2013
        AND c.driver_gratuity > 0
        AND dp.gross_pay IS NOT NULL
    """)
    row = cur.fetchone()
    if row and row[0]:
        charter_grat = float(row[0])
        payroll_gross = float(row[1])
        charter_base = float(row[2])
        charter_total = float(row[3])
        
        base_ratio = payroll_gross / charter_base if charter_base > 0 else 0
        total_ratio = payroll_gross / charter_total if charter_total > 0 else 0
        
        print("2013 Analysis:")
        if abs(base_ratio - 1.0) < abs(total_ratio - 1.0) and base_ratio > 0.80:
            print(f"  ✓ Gratuity EXCLUDED from payroll ({base_ratio:.2%} base ratio)")
            print("  ✓ CONCLUSION: 2013 follows pre-2013 direct tips pattern")
            tips_2013 = "DIRECT TIPS"
        elif abs(total_ratio - 1.0) < abs(base_ratio - 1.0) and total_ratio > 0.80:
            print(f"  [WARN]  Gratuity INCLUDED in payroll ({total_ratio:.2%} total ratio)")
            print("  [WARN]  CONCLUSION: 2013 may have changed to controlled tips")
            tips_2013 = "CONTROLLED TIPS"
        else:
            print(f"  ❓ Unclear pattern (base: {base_ratio:.2%}, total: {total_ratio:.2%})")
            print("  ❓ CONCLUSION: 2013 requires manual review")
            tips_2013 = "UNCLEAR"
    else:
        print("2013 Analysis:")
        print("  ℹ️  No payroll data linked to gratuity charters")
        tips_2013 = "NO DATA"
    
    print()
    
    # Analyze 2014
    cur.execute("""
        SELECT 
            SUM(c.driver_gratuity) as charter_gratuity,
            SUM(dp.gross_pay) as payroll_gross,
            SUM(c.driver_total - c.driver_gratuity) as charter_base_pay,
            SUM(c.driver_total) as charter_total_pay
        FROM driver_payroll dp
        JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE dp.year = 2014
        AND c.driver_gratuity > 0
        AND dp.gross_pay IS NOT NULL
    """)
    row = cur.fetchone()
    if row and row[0]:
        charter_grat = float(row[0])
        payroll_gross = float(row[1])
        charter_base = float(row[2])
        charter_total = float(row[3])
        
        base_ratio = payroll_gross / charter_base if charter_base > 0 else 0
        total_ratio = payroll_gross / charter_total if charter_total > 0 else 0
        
        print("2014 Analysis:")
        if abs(base_ratio - 1.0) < abs(total_ratio - 1.0) and base_ratio > 0.80:
            print(f"  ✓ Gratuity EXCLUDED from payroll ({base_ratio:.2%} base ratio)")
            print("  ✓ CONCLUSION: 2014 follows pre-2013 direct tips pattern")
            tips_2014 = "DIRECT TIPS"
        elif abs(total_ratio - 1.0) < abs(base_ratio - 1.0) and total_ratio > 0.80:
            print(f"  [WARN]  Gratuity INCLUDED in payroll ({total_ratio:.2%} total ratio)")
            print("  [WARN]  CONCLUSION: 2014 may have changed to controlled tips")
            tips_2014 = "CONTROLLED TIPS"
        else:
            print(f"  ❓ Unclear pattern (base: {base_ratio:.2%}, total: {total_ratio:.2%})")
            print("  ❓ CONCLUSION: 2014 requires manual review")
            tips_2014 = "UNCLEAR"
    else:
        print("2014 Analysis:")
        print("  ℹ️  No payroll data linked to gratuity charters")
        tips_2014 = "NO DATA"
    
    # Final recommendation
    print("\n" + "=" * 80)
    print("7. RECOMMENDATION")
    print("=" * 80)
    
    print(f"\nGratuity Treatment Summary:")
    print(f"  Pre-2013: DIRECT TIPS (confirmed)")
    print(f"  2013: {tips_2013}")
    print(f"  2014: {tips_2014}")
    print()
    
    if tips_2013 == "DIRECT TIPS" and tips_2014 == "DIRECT TIPS":
        print("[OK] RECOMMENDATION: Extend direct tips treatment through 2014")
        print("   Data shows consistent pattern: gratuity excluded from payroll")
        print("   Safe to apply same CRA classification as pre-2013")
    elif tips_2013 == "CONTROLLED TIPS" or tips_2014 == "CONTROLLED TIPS":
        print("[WARN]  RECOMMENDATION: Do NOT extend direct tips treatment")
        print("   Data shows change in handling: gratuity included in payroll")
        print("   Must treat as controlled tips (subject to payroll taxes)")
    elif tips_2013 == "UNCLEAR" or tips_2014 == "UNCLEAR":
        print("❓ RECOMMENDATION: Requires manual review")
        print("   Data patterns are ambiguous - need detailed analysis")
        print("   Conservative approach: exclude from direct tips until verified")
    else:
        print("ℹ️  RECOMMENDATION: Insufficient data")
        print("   Cannot determine gratuity treatment without payroll linkage")
        print("   Conservative approach: exclude from direct tips classification")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
