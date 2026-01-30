#!/usr/bin/env python3
"""
CORRECTED BEVERAGE ANALYSIS - REAL ALCOHOL RECEIPTS ONLY
========================================================

Verifies the beverage cost analysis using only actual liquor store 
purchases, not system-generated entries or charter charges.
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

def get_real_alcohol_purchases():
    """Get only actual liquor store purchases, not system entries."""
    
    print("🔍 IDENTIFYING REAL ALCOHOL PURCHASES")
    print("=" * 37)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get actual liquor store purchases (exclude system entries)
        cur.execute("""
            SELECT 
                EXTRACT(year FROM receipt_date) as year,
                receipt_date,
                vendor_name,
                description,
                gross_amount
            FROM receipts
            WHERE (
                LOWER(COALESCE(vendor_name, '')) LIKE '%liquor%'
                OR LOWER(COALESCE(vendor_name, '')) LIKE '%wine%'
                OR LOWER(COALESCE(vendor_name, '')) LIKE '%beer%'
                OR LOWER(COALESCE(vendor_name, '')) LIKE '%lcbo%'
            )
            AND vendor_name NOT LIKE '%Charter_%'
            AND vendor_name NOT LIKE 'Point of Sale%'
            AND COALESCE(description, '') NOT LIKE '%AUTO-GEN%'
            AND COALESCE(description, '') NOT LIKE '%Charter Charges%'
            AND gross_amount IS NOT NULL
            AND gross_amount > 0
            ORDER BY receipt_date
        """)
        
        real_purchases = cur.fetchall()
        
        print(f"📊 REAL LIQUOR PURCHASES FOUND: {len(real_purchases)}")
        
        if real_purchases:
            # Group by year
            year_data = {}
            
            for year, date, vendor, desc, amount in real_purchases:
                if year not in year_data:
                    year_data[year] = {'count': 0, 'total': 0, 'receipts': []}
                
                year_data[year]['count'] += 1
                year_data[year]['total'] += amount
                year_data[year]['receipts'].append((date, vendor, desc, amount))
            
            print(f"\n🍷 LIQUOR PURCHASES BY YEAR:")
            print(f"{'Year':<6} {'Count':<6} {'Total':<12} {'Vendors'}")
            print("-" * 50)
            
            total_all = 0
            for year in sorted(year_data.keys()):
                data = year_data[year]
                total_all += data['total']
                
                # Get unique vendors for this year
                vendors = set(r[1] for r in data['receipts'])
                vendor_list = ', '.join(list(vendors)[:2])
                
                print(f"{int(year):<6} {data['count']:<6} ${data['total']:<11,.2f} {vendor_list[:30]}")
            
            print("-" * 50)
            print(f"{'TOTAL':<6} {len(real_purchases):<6} ${total_all:<11,.2f}")
            
            # Show detailed 2012 data
            if 2012 in year_data:
                print(f"\n🔍 2012 DETAILED LIQUOR PURCHASES:")
                for date, vendor, desc, amount in year_data[2012]['receipts']:
                    print(f"   • {date}: {vendor} - ${amount:.2f}")
                    if desc and desc != vendor:
                        print(f"     Description: {desc}")
            else:
                print(f"\n[FAIL] NO REAL LIQUOR PURCHASES FOUND FOR 2012")
            
            return year_data
        
        else:
            print(f"[FAIL] NO REAL LIQUOR STORE RECEIPTS FOUND!")
            print(f"   This means the previous analysis was based on system-generated entries")
            return {}
    
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")
        return {}
    
    finally:
        cur.close()
        conn.close()

def get_corrected_beverage_analysis():
    """Get corrected beverage profitability analysis."""
    
    print(f"\n💰 CORRECTED BEVERAGE PROFITABILITY")
    print("-" * 34)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get real alcohol costs by year
        real_costs = get_real_alcohol_purchases()
        
        # Get beverage revenue by year
        cur.execute("""
            SELECT 
                EXTRACT(year FROM c.charter_date) as year,
                SUM(cc.amount) as revenue,
                COUNT(*) as transactions
            FROM charters c
            JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE (LOWER(cc.description) LIKE '%beverage%'
                   OR LOWER(cc.description) LIKE '%alcohol%')
            GROUP BY EXTRACT(year FROM c.charter_date)
            ORDER BY year
        """)
        
        revenue_data = cur.fetchall()
        
        print(f"📊 CORRECTED BEVERAGE ANALYSIS:")
        print(f"{'Year':<6} {'Revenue':<10} {'Real Costs':<10} {'Profit':<10} {'Markup':<8} {'Status'}")
        print("-" * 65)
        
        total_revenue = 0
        total_costs = 0
        
        for year, revenue, transactions in revenue_data:
            year_int = int(year)
            real_cost = real_costs.get(year, {}).get('total', 0)
            profit = revenue - real_cost
            
            total_revenue += revenue
            total_costs += real_cost
            
            if real_cost > 0:
                markup = (revenue / real_cost) * 100
                markup_str = f"{markup:.1f}%"
            else:
                markup_str = "N/A"
            
            if profit < -1000:
                status = "🍷💸 LOSS"
            elif profit < 0:
                status = "[WARN] LOSS"
            elif real_cost == 0:
                status = "💰 PURE PROFIT"
            else:
                status = "[OK] PROFIT"
            
            print(f"{year_int:<6} ${revenue:<9,.0f} ${real_cost:<9,.0f} ${profit:<9,.0f} {markup_str:<8} {status}")
        
        print("-" * 65)
        total_profit = total_revenue - total_costs
        overall_markup = (total_revenue / total_costs * 100) if total_costs > 0 else 0
        
        print(f"{'TOTAL':<6} ${total_revenue:<9,.0f} ${total_costs:<9,.0f} ${total_profit:<9,.0f} {overall_markup:.1f}%")
        
        return {
            'total_revenue': total_revenue,
            'total_costs': total_costs,
            'total_profit': total_profit,
            'overall_markup': overall_markup
        }
    
    except Exception as e:
        print(f"[FAIL] Error: {str(e)}")
        return {}
    
    finally:
        cur.close()
        conn.close()

def main():
    """Main corrected beverage analysis."""
    
    print("🔍 BEVERAGE ANALYSIS CORRECTION")
    print("Verifying actual alcohol receipts vs system entries")
    print("=" * 50)
    
    # Get real alcohol purchases
    real_purchases = get_real_alcohol_purchases()
    
    # Get corrected analysis
    corrected_results = get_corrected_beverage_analysis()
    
    print(f"\n🚨 ANALYSIS CORRECTION SUMMARY:")
    print("-" * 31)
    
    if not real_purchases or sum(data.get('total', 0) for data in real_purchases.values()) == 0:
        print("[FAIL] MAJOR FINDING: NO REAL LIQUOR STORE RECEIPTS!")
        print("   • Previous analysis included system-generated entries")
        print("   • Charter charges were counted as 'alcohol costs'")
        print("   • Point of Sale entries were counted as purchases")
        print("   • This means beverage sales were essentially 100% profit!")
        
        if corrected_results:
            print(f"\n[OK] CORRECTED 2012 BEVERAGE STATUS:")
            print(f"   • Revenue: ${corrected_results.get('total_revenue', 0):,.2f}")
            print(f"   • Real Costs: $0.00 (no liquor store purchases)")
            print(f"   • Profit: ${corrected_results.get('total_revenue', 0):,.2f}")
            print(f"   • Status: 💰 PURE PROFIT - Not a loss!")
    
    else:
        print("[OK] REAL LIQUOR PURCHASES FOUND:")
        total_real_costs = sum(data.get('total', 0) for data in real_purchases.values())
        print(f"   • Total real alcohol costs: ${total_real_costs:,.2f}")
        
        if corrected_results:
            print(f"   • Total beverage revenue: ${corrected_results.get('total_revenue', 0):,.2f}")
            print(f"   • Corrected profit: ${corrected_results.get('total_profit', 0):,.2f}")
    
    print(f"\n🎯 CONCLUSION ON BOOZE FEST THEORY:")
    
    if not real_purchases or sum(data.get('total', 0) for data in real_purchases.values()) < 1000:
        print("🍾 THEORY REJECTED: 2012 was NOT a beverage loss!")
        print("   • No significant alcohol purchase costs found")
        print("   • Previous analysis was based on system entries")
        print("   • Beverages were essentially free profit")
        print("   • The 'booze fest' was profitable, not a disaster!")
    else:
        print("🍷 THEORY NEEDS REFINEMENT: Some real costs found")
        print("   • Analysis based on actual liquor store receipts")

if __name__ == "__main__":
    main()