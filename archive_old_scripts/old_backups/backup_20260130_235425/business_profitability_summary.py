#!/usr/bin/env python3
"""
CHARTER BUSINESS PROFITABILITY SUMMARY
======================================

Clean summary of charter revenue vs vehicle operating costs with key insights.
"""

import os
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def business_profitability_summary():
    print("🚗 CHARTER BUSINESS PROFITABILITY SUMMARY")
    print("=" * 45)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Key insights from the analysis
    print("\n💰 TOTAL BUSINESS PERFORMANCE (2007-2026):")
    print("-" * 42)
    print("   Charter Revenue (adj. for beverages): $4,680,305")
    print("   Vehicle Operating Costs:              $9,030,829")
    print("   Net Operating Loss:                  ($4,350,524)")
    print("   Operating Margin:                         -93.0%")
    print("   Cost per Revenue Dollar:                   $1.93")
    
    print("\n📊 COST BREAKDOWN:")
    print("-" * 18)
    print("   Fuel:            $786,403   (16.8% of revenue)")
    print("   Maintenance:   $4,766,296  (101.8% of revenue) [WARN]")
    print("   Lease/Finance: $2,158,628   (46.1% of revenue)")
    print("   Insurance:     $1,319,502   (28.2% of revenue)")
    
    print("\n🔥 PROBLEM YEARS (Massive Maintenance Costs):")
    print("-" * 45)
    print("   2013: $1,886,372 maintenance (1,649 receipts)")
    print("   2015: $1,916,241 maintenance (1,376 receipts)")
    print("   2016:   $742,526 maintenance (262 receipts)")
    print("         These 3 years: $4.5M+ in maintenance costs!")
    
    print("\n[OK] PROFITABLE YEARS:")
    print("-" * 20)
    print("   2007-2011: $941,178 profit (no major vehicle costs)")
    print("   2014:       $187,797 profit (reasonable costs)")
    print("   2018:       $104,417 profit (controlled costs)")
    print("   2023:        $30,690 profit (costs under control)")
    
    print("\n📈 YEAR-BY-YEAR PROFITABILITY:")
    print("-" * 30)
    
    # Simple profitability by year
    yearly_data = [
        (2007, 155174, 70, 155104),
        (2008, 167812, 0, 167812),
        (2009, 163488, 0, 163488),
        (2010, 179723, 0, 179723),
        (2011, 275051, 0, 275051),
        (2012, 354084, 497197, -143113),
        (2013, 341348, 2426582, -2085233),
        (2014, 355820, 168023, 187797),
        (2015, 332351, 1993937, -1661586),
        (2016, 213116, 742596, -529481),
        (2017, 232780, 257268, -24488),
        (2018, 249336, 144918, 104417),
        (2019, 262332, 834901, -572569),
        (2020, 137700, 292697, -154997),
        (2021, 178383, 409017, -230635),
        (2022, 257273, 392916, -135643),
        (2023, 315113, 284423, 30690),
        (2024, 290052, 303618, -13566),
        (2025, 218211, 282666, -64454)
    ]
    
    print("   Year | Revenue | Costs   | Profit   | Margin")
    print("   -----|---------|---------|----------|-------")
    
    profitable_years = 0
    total_profit_years = 0
    total_loss_years = 0
    
    for year, revenue, costs, profit in yearly_data:
        margin = (profit / revenue * 100) if revenue > 0 else 0
        status = "[OK]" if profit > 0 else "[FAIL]"
        
        if profit > 0:
            profitable_years += 1
            total_profit_years += profit
        else:
            total_loss_years += abs(profit)
        
        print(f"   {year} |${revenue:7,.0f} |${costs:7,.0f} |${profit:8,.0f} |{margin:6.1f}% {status}")
    
    print("   -----|---------|---------|----------|-------")
    
    print(f"\n🎯 KEY INSIGHTS:")
    print("-" * 15)
    print(f"   • Profitable Years: {profitable_years}/19 ({profitable_years/19*100:.1f}%)")
    print(f"   • Total Profits: ${total_profit_years:,.0f}")
    print(f"   • Total Losses: ${total_loss_years:,.0f}")
    print(f"   • Net Result: ${total_profit_years - total_loss_years:,.0f}")
    
    print(f"\n[WARN]  CRITICAL ISSUES:")
    print("-" * 18)
    print("   1. MAINTENANCE EXPLOSION (2013-2016):")
    print("      - 2013: 1,649 receipts averaging $1,144 each")
    print("      - 2015: 1,376 receipts averaging $1,393 each")
    print("      - Suggests major fleet overhaul or poor tracking")
    
    print("\n   2. LEASE/FINANCING BURDEN:")
    print("      - $2.16M total over 19 years")
    print("      - Peak: 2019 with $483K (62% of revenue)")
    
    print("\n   3. INSURANCE ESCALATION:")
    print("      - 2012: $466/payment average")
    print("      - 2024: $7,582/payment average (16x increase!)")
    
    print(f"\n💡 BUSINESS MODEL ANALYSIS:")
    print("-" * 26)
    print("   • Early Years (2007-2011): Highly profitable (owned vehicles)")
    print("   • Growth Phase (2012-2016): Heavy capital investment, losses")
    print("   • Recovery (2017-2025): Struggling with legacy costs")
    print("   • Current Challenge: $282K annual vehicle costs vs $218K revenue")
    
    print(f"\n🚀 RECOMMENDATIONS:")
    print("-" * 18)
    print("   1. Investigate 2013-2016 maintenance records for accuracy")
    print("   2. Review insurance costs - 16x increase needs explanation")
    print("   3. Consider fleet ownership vs leasing analysis")
    print("   4. Focus on premium charters to improve per-trip revenue")
    print("   5. Implement preventive maintenance to control costs")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    business_profitability_summary()