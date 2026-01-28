#!/usr/bin/env python3
"""
Check if Paul's 2012 income was below the basic personal amount (non-taxable threshold).

Canadian Basic Personal Amount History:
- 2012: $10,822 federal basic personal amount
- 2012 Alberta: $17,282 provincial basic personal amount

If income is below these thresholds, NO tax is owed, so T4 Box 14 could legitimately be $0
or the income wouldn't need to be reported.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )

def check_tax_exemption():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("2012 TAX EXEMPTION ANALYSIS - PAUL D RICHARD")
    print("=" * 80)
    
    # Canadian tax thresholds for 2012
    FEDERAL_BASIC_2012 = 10822
    ALBERTA_BASIC_2012 = 17282
    
    print(f"\n📊 2012 CANADIAN TAX THRESHOLDS:")
    print(f"   Federal Basic Personal Amount: ${FEDERAL_BASIC_2012:,.2f}")
    print(f"   Alberta Provincial Basic Amount: ${ALBERTA_BASIC_2012:,.2f}")
    print(f"   Effective Non-Taxable Threshold: ${ALBERTA_BASIC_2012:,.2f} (higher of two)")
    
    # Get Paul's 2012 payroll
    cur.execute("""
        SELECT 
            SUM(gross_pay) as total_gross,
            SUM(cpp) as total_cpp,
            SUM(ei) as total_ei,
            SUM(tax) as total_tax,
            SUM(net_pay) as total_net,
            COUNT(*) as entry_count
        FROM driver_payroll
        WHERE year = 2012
          AND (employee_id = 143 OR driver_id = '8000001B-1412267705' OR driver_id = 'Dr26')
    """)
    
    result = cur.fetchone()
    
    if result and result['total_gross']:
        gross = float(result['total_gross'])
        cpp = float(result['total_cpp'] or 0)
        ei = float(result['total_ei'] or 0)
        tax = float(result['total_tax'] or 0)
        
        print(f"\n💰 PAUL'S 2012 ACTUAL INCOME:")
        print(f"   Gross Pay: ${gross:,.2f}")
        print(f"   CPP Deducted: ${cpp:,.2f}")
        print(f"   EI Deducted: ${ei:,.2f}")
        print(f"   Tax Deducted: ${tax:,.2f}")
        print(f"   Entry Count: {result['entry_count']}")
        
        print(f"\n🔍 COMPARISON TO TAX THRESHOLDS:")
        print("-" * 80)
        
        # Federal comparison
        federal_diff = gross - FEDERAL_BASIC_2012
        if gross < FEDERAL_BASIC_2012:
            print(f"   Federal: ${gross:,.2f} < ${FEDERAL_BASIC_2012:,.2f}")
            print(f"   [OK] BELOW federal threshold by ${abs(federal_diff):,.2f}")
            print(f"   [OK] NO FEDERAL TAX OWED")
        else:
            print(f"   Federal: ${gross:,.2f} > ${FEDERAL_BASIC_2012:,.2f}")
            print(f"   [WARN]  ABOVE federal threshold by ${federal_diff:,.2f}")
            print(f"   Federal tax would apply to ${federal_diff:,.2f}")
        
        print()
        
        # Alberta comparison
        alberta_diff = gross - ALBERTA_BASIC_2012
        if gross < ALBERTA_BASIC_2012:
            print(f"   Alberta: ${gross:,.2f} < ${ALBERTA_BASIC_2012:,.2f}")
            print(f"   [OK] BELOW Alberta threshold by ${abs(alberta_diff):,.2f}")
            print(f"   [OK] NO ALBERTA TAX OWED")
        else:
            print(f"   Alberta: ${gross:,.2f} > ${ALBERTA_BASIC_2012:,.2f}")
            print(f"   [WARN]  ABOVE Alberta threshold by ${alberta_diff:,.2f}")
            print(f"   Alberta tax would apply to ${alberta_diff:,.2f}")
        
        # Overall assessment
        print(f"\n" + "=" * 80)
        print("ASSESSMENT:")
        print("=" * 80)
        
        if gross < ALBERTA_BASIC_2012:
            print(f"\n[OK] Paul's 2012 income (${gross:,.2f}) was BELOW the basic personal amount")
            print(f"   (${ALBERTA_BASIC_2012:,.2f} in Alberta)")
            print(f"\n   This means:")
            print(f"   • NO income tax should have been owed")
            print(f"   • T4 Box 14 = $0 could be LEGITIMATE")
            print(f"   • Income tax deducted (${tax:,.2f}) should have been REFUNDED")
            print(f"   • CPP (${cpp:,.2f}) and EI (${ei:,.2f}) still required")
            
            if tax > 0:
                print(f"\n   [WARN]  ISSUE: ${tax:,.2f} in tax was deducted but shouldn't have been")
                print(f"   💡 RECOMMENDATION: File T4 to claim ${tax:,.2f} tax refund")
            
            print(f"\n   📝 BUSINESS CONTEXT:")
            print(f"   • Owner may have intentionally taken minimal salary")
            print(f"   • Business may have retained profits instead of paying salary")
            print(f"   • Common strategy for small business owners in startup/growth phase")
            
        else:
            print(f"\n[WARN]  Paul's 2012 income (${gross:,.2f}) was ABOVE the basic personal amount")
            print(f"   • Federal tax threshold: ${FEDERAL_BASIC_2012:,.2f}")
            print(f"   • Alberta tax threshold: ${ALBERTA_BASIC_2012:,.2f}")
            print(f"   • Tax was properly deducted: ${tax:,.2f}")
            print(f"   • T4 SHOULD have been filed to report this income")
            
            if tax > 0:
                print(f"\n   💡 RECOMMENDATION: File missing T4 for 2012")
                print(f"      This is required even though tax was already withheld")
    
    # Check other years too
    print(f"\n\n" + "=" * 80)
    print("ALL YEARS COMPARISON (2011-2015):")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            year,
            SUM(gross_pay) as total_gross,
            SUM(tax) as total_tax,
            SUM(t4_box_14) as t4_reported
        FROM driver_payroll
        WHERE (employee_id = 143 OR driver_id = '8000001B-1412267705' OR driver_id = 'Dr26')
          AND year BETWEEN 2011 AND 2015
        GROUP BY year
        ORDER BY year
    """)
    
    yearly = cur.fetchall()
    
    # Tax thresholds by year (Alberta basic personal amount)
    thresholds = {
        2011: 16977,
        2012: 17282,
        2013: 17593,
        2014: 18214,
        2015: 18451
    }
    
    print(f"\n{'Year':<6} {'Gross Pay':<12} {'Tax Deducted':<12} {'T4 Reported':<12} "
          f"{'Threshold':<12} {'Status':<20}")
    print("-" * 90)
    
    for year_data in yearly:
        year = year_data['year']
        gross = float(year_data['total_gross'] or 0)
        tax = float(year_data['total_tax'] or 0)
        t4 = float(year_data['t4_reported'] or 0)
        threshold = thresholds.get(year, 17000)
        
        if gross < threshold:
            status = "[OK] Below threshold"
        else:
            status = "[WARN]  Above threshold"
        
        print(f"{year:<6} ${gross:>10,.2f} ${tax:>10,.2f} ${t4:>10,.2f} "
              f"${threshold:>10,.2f} {status:<20}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_tax_exemption()
