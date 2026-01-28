#!/usr/bin/env python3
"""
BEVERAGE ORDER CHARTER ANALYSIS - 2012 BOOZE FEST INVESTIGATION
===============================================================

Validates the theory that 2012 was a "booze fest loss" by analyzing:
1. Beverage orders matched to specific charters
2. Beverage pricing vs cost analysis  
3. Reimbursement patterns for beverage charges
4. Year-over-year beverage profitability trends
"""

import os
import psycopg2
from datetime import datetime
import pandas as pd

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_beverage_charter_matching():
    """Analyze beverage orders matched to specific charters."""
    
    print("🍾 BEVERAGE CHARTER MATCHING ANALYSIS")
    print("=" * 37)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find beverage charges linked to charters
        cur.execute("""
            SELECT 
                EXTRACT(year FROM c.charter_date) as year,
                COUNT(cc.charge_id) as beverage_charges,
                COUNT(DISTINCT c.charter_id) as charters_with_beverages,
                COUNT(DISTINCT c.charter_id) * 100.0 / 
                    (SELECT COUNT(*) FROM charters c2 
                     WHERE EXTRACT(year FROM c2.charter_date) = EXTRACT(year FROM c.charter_date)) as penetration_rate,
                ROUND(SUM(cc.amount), 2) as total_beverage_revenue,
                ROUND(AVG(cc.amount), 2) as avg_beverage_charge,
                ROUND(MIN(cc.amount), 2) as min_beverage_charge,
                ROUND(MAX(cc.amount), 2) as max_beverage_charge
            FROM charters c
            JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE LOWER(cc.description) LIKE '%beverage%'
            OR LOWER(cc.description) LIKE '%alcohol%' 
            OR LOWER(cc.description) LIKE '%drink%'
            OR LOWER(cc.description) LIKE '%champagne%'
            OR LOWER(cc.description) LIKE '%wine%'
            OR LOWER(cc.description) LIKE '%beer%'
            GROUP BY EXTRACT(year FROM c.charter_date)
            ORDER BY year
        """)
        
        beverage_by_year = cur.fetchall()
        
        print("📊 BEVERAGE CHARGES BY YEAR:")
        print(f"{'Year':<6} {'Charges':<8} {'Charters':<9} {'Penetration':<11} {'Revenue':<12} {'Avg Charge'}")
        print("-" * 75)
        
        total_beverage_revenue = 0
        booze_fest_year = None
        max_revenue = 0
        
        for year, charges, charters, penetration, revenue, avg_charge, min_charge, max_charge in beverage_by_year:
            total_beverage_revenue += revenue or 0
            
            if (revenue or 0) > max_revenue:
                max_revenue = revenue or 0
                booze_fest_year = int(year)
            
            print(f"{int(year):<6} {charges:<8} {charters:<9} {penetration:<10.1f}% ${revenue:<11,.2f} ${avg_charge:.2f}")
        
        print("-" * 75)
        print(f"{'TOTAL':<6} {'':<8} {'':<9} {'':<11} ${total_beverage_revenue:<11,.2f}")
        
        if booze_fest_year:
            print(f"\n🍺 BOOZE FEST YEAR IDENTIFIED: {booze_fest_year} (${max_revenue:,.2f} revenue)")
        
        return beverage_by_year, booze_fest_year
        
    except Exception as e:
        print(f"[FAIL] Error in beverage analysis: {str(e)}")
        return [], None
    
    finally:
        cur.close()
        conn.close()

def analyze_2012_beverage_details():
    """Deep dive into 2012 beverage operations."""
    
    print(f"\n🔍 2012 BEVERAGE DEEP DIVE ANALYSIS")
    print("-" * 33)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get detailed 2012 beverage data
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.rate as charter_rate,
                cc.description as beverage_description,
                cc.amount as beverage_charge,
                c.notes,
                EXTRACT(month FROM c.charter_date) as month
            FROM charters c
            JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE EXTRACT(year FROM c.charter_date) = 2012
            AND (LOWER(cc.description) LIKE '%beverage%'
                 OR LOWER(cc.description) LIKE '%alcohol%' 
                 OR LOWER(cc.description) LIKE '%drink%'
                 OR LOWER(cc.description) LIKE '%champagne%'
                 OR LOWER(cc.description) LIKE '%wine%'
                 OR LOWER(cc.description) LIKE '%beer%')
            ORDER BY c.charter_date
        """)
        
        beverage_2012 = cur.fetchall()
        
        if not beverage_2012:
            print("[FAIL] No beverage charges found for 2012")
            return
        
        print(f"📊 FOUND {len(beverage_2012):,} BEVERAGE CHARGES IN 2012")
        
        # Monthly breakdown
        monthly_stats = {}
        beverage_types = {}
        
        for charter_id, reserve_no, date, charter_rate, desc, charge, notes, month in beverage_2012:
            if month not in monthly_stats:
                monthly_stats[month] = {'count': 0, 'revenue': 0, 'charters': set()}
            
            monthly_stats[month]['count'] += 1
            monthly_stats[month]['revenue'] += charge or 0
            monthly_stats[month]['charters'].add(charter_id)
            
            # Categorize beverage type
            desc_lower = (desc or '').lower()
            if 'champagne' in desc_lower or 'wine' in desc_lower:
                beverage_types['Premium (Wine/Champagne)'] = beverage_types.get('Premium (Wine/Champagne)', 0) + (charge or 0)
            elif 'beer' in desc_lower:
                beverage_types['Beer'] = beverage_types.get('Beer', 0) + (charge or 0)
            elif 'alcohol' in desc_lower:
                beverage_types['General Alcohol'] = beverage_types.get('General Alcohol', 0) + (charge or 0)
            else:
                beverage_types['Beverage (General)'] = beverage_types.get('Beverage (General)', 0) + (charge or 0)
        
        print(f"\n📅 2012 MONTHLY BEVERAGE BREAKDOWN:")
        print(f"{'Month':<12} {'Charges':<8} {'Charters':<9} {'Revenue'}")
        print("-" * 45)
        
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for month in sorted(monthly_stats.keys()):
            stats = monthly_stats[month]
            month_name = month_names[int(month)]
            print(f"{month_name:<12} {stats['count']:<8} {len(stats['charters']):<9} ${stats['revenue']:.2f}")
        
        print(f"\n🍷 2012 BEVERAGE TYPE BREAKDOWN:")
        for bev_type, revenue in sorted(beverage_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {bev_type}: ${revenue:,.2f}")
        
        # Show sample high-value beverage charges
        print(f"\n💰 TOP 2012 BEVERAGE CHARGES:")
        beverage_2012_sorted = sorted(beverage_2012, key=lambda x: x[5] or 0, reverse=True)
        
        for i, (charter_id, reserve_no, date, charter_rate, desc, charge, notes, month) in enumerate(beverage_2012_sorted[:10]):
            print(f"   {i+1}. {reserve_no}: {desc} - ${charge:.2f} ({date})")
        
        return beverage_2012
        
    except Exception as e:
        print(f"[FAIL] Error in 2012 analysis: {str(e)}")
        return []
    
    finally:
        cur.close()
        conn.close()

def analyze_beverage_cost_vs_pricing():
    """Analyze beverage costs vs pricing to determine profitability."""
    
    print(f"\n💰 BEVERAGE COST VS PRICING ANALYSIS")
    print("-" * 34)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find beverage purchases (receipts) vs beverage sales (charges)
        cur.execute("""
            WITH beverage_sales AS (
                SELECT 
                    EXTRACT(year FROM c.charter_date) as year,
                    SUM(cc.amount) as sales_revenue,
                    COUNT(*) as sale_transactions
                FROM charters c
                JOIN charter_charges cc ON c.charter_id = cc.charter_id
                WHERE LOWER(cc.description) LIKE '%beverage%'
                OR LOWER(cc.description) LIKE '%alcohol%'
                GROUP BY EXTRACT(year FROM c.charter_date)
            ),
            beverage_costs AS (
                SELECT 
                    EXTRACT(year FROM receipt_date) as year,
                    SUM(gross_amount) as cost_amount,
                    COUNT(*) as purchase_transactions
                FROM receipts
                WHERE LOWER(COALESCE(vendor_name, '')) LIKE '%liquor%'
                OR LOWER(COALESCE(vendor_name, '')) LIKE '%beer%'
                OR LOWER(COALESCE(vendor_name, '')) LIKE '%wine%'
                OR LOWER(COALESCE(description, '')) LIKE '%alcohol%'
                OR LOWER(COALESCE(description, '')) LIKE '%beverage%'
                OR LOWER(COALESCE(description, '')) LIKE '%champagne%'
                GROUP BY EXTRACT(year FROM receipt_date)
            )
            SELECT 
                COALESCE(s.year, c.year) as year,
                COALESCE(s.sales_revenue, 0) as revenue,
                COALESCE(s.sale_transactions, 0) as sales_count,
                COALESCE(c.cost_amount, 0) as costs,
                COALESCE(c.purchase_transactions, 0) as purchase_count,
                COALESCE(s.sales_revenue, 0) - COALESCE(c.cost_amount, 0) as profit,
                CASE WHEN c.cost_amount > 0 THEN 
                    (s.sales_revenue / c.cost_amount) * 100 
                ELSE NULL END as markup_percentage
            FROM beverage_sales s
            FULL OUTER JOIN beverage_costs c ON s.year = c.year
            WHERE COALESCE(s.year, c.year) BETWEEN 2007 AND 2025
            ORDER BY year
        """)
        
        cost_analysis = cur.fetchall()
        
        print("📊 BEVERAGE PROFITABILITY BY YEAR:")
        print(f"{'Year':<6} {'Revenue':<10} {'Costs':<10} {'Profit':<10} {'Markup %':<10} {'Status'}")
        print("-" * 70)
        
        worst_year = None
        worst_profit = float('inf')
        best_year = None
        best_profit = float('-inf')
        
        total_revenue = 0
        total_costs = 0
        
        for year, revenue, sales_count, costs, purchase_count, profit, markup in cost_analysis:
            if year and revenue and costs:  # Only count years with both data
                total_revenue += revenue
                total_costs += costs
                
                if profit < worst_profit:
                    worst_profit = profit
                    worst_year = int(year)
                
                if profit > best_profit:
                    best_profit = profit
                    best_year = int(year)
                
                # Determine status
                if profit < -1000:
                    status = "🍷💸 BOOZE LOSS"
                elif profit < 0:
                    status = "[WARN] LOSS"
                elif markup and markup > 200:
                    status = "💰 HIGH PROFIT"
                elif profit > 1000:
                    status = "[OK] PROFITABLE"
                else:
                    status = "📊 BREAK EVEN"
                
                markup_str = f"{markup:.1f}%" if markup else "N/A"
                
                print(f"{int(year):<6} ${revenue:<9,.0f} ${costs:<9,.0f} ${profit:<9,.0f} {markup_str:<10} {status}")
        
        print("-" * 70)
        total_profit = total_revenue - total_costs
        overall_markup = (total_revenue / total_costs * 100) if total_costs > 0 else 0
        
        print(f"{'TOTAL':<6} ${total_revenue:<9,.0f} ${total_costs:<9,.0f} ${total_profit:<9,.0f} {overall_markup:.1f}%")
        
        # Analysis summary
        print(f"\n🍺 BOOZE FEST ANALYSIS RESULTS:")
        
        if worst_year:
            print(f"   📉 WORST YEAR: {worst_year} (${worst_profit:,.0f} loss)")
        if best_year:
            print(f"   📈 BEST YEAR: {best_year} (${best_profit:,.0f} profit)")
        
        if total_profit < 0:
            print(f"   🚨 OVERALL STATUS: LOSS of ${abs(total_profit):,.0f}")
        else:
            print(f"   [OK] OVERALL STATUS: PROFIT of ${total_profit:,.0f}")
        
        print(f"   📊 OVERALL MARKUP: {overall_markup:.1f}%")
        
        return cost_analysis, worst_year, worst_profit
        
    except Exception as e:
        print(f"[FAIL] Error in cost analysis: {str(e)}")
        return [], None, None
    
    finally:
        cur.close()
        conn.close()

def analyze_beverage_reimbursements():
    """Analyze patterns of beverage reimbursements and refunds."""
    
    print(f"\n🔄 BEVERAGE REIMBURSEMENT ANALYSIS")
    print("-" * 32)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Find negative beverage charges (potential reimbursements)
        cur.execute("""
            SELECT 
                EXTRACT(year FROM c.charter_date) as year,
                COUNT(CASE WHEN cc.amount < 0 THEN 1 END) as negative_charges,
                COUNT(CASE WHEN cc.amount >= 0 THEN 1 END) as positive_charges,
                SUM(CASE WHEN cc.amount < 0 THEN cc.amount ELSE 0 END) as total_refunds,
                SUM(CASE WHEN cc.amount >= 0 THEN cc.amount ELSE 0 END) as total_charges,
                SUM(cc.amount) as net_beverage_revenue
            FROM charters c
            JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE LOWER(cc.description) LIKE '%beverage%'
            OR LOWER(cc.description) LIKE '%alcohol%'
            GROUP BY EXTRACT(year FROM c.charter_date)
            ORDER BY year
        """)
        
        reimbursement_data = cur.fetchall()
        
        print("📊 BEVERAGE REFUND PATTERNS:")
        print(f"{'Year':<6} {'Refunds':<8} {'Charges':<8} {'Refund $':<10} {'Charge $':<10} {'Net $':<10} {'Refund %'}")
        print("-" * 75)
        
        highest_refund_year = None
        highest_refund_rate = 0
        
        for year, negative, positive, refunds, charges, net in reimbursement_data:
            if year and (negative > 0 or positive > 0):
                total_transactions = negative + positive
                refund_rate = (negative / total_transactions * 100) if total_transactions > 0 else 0
                
                if refund_rate > highest_refund_rate:
                    highest_refund_rate = refund_rate
                    highest_refund_year = int(year)
                
                print(f"{int(year):<6} {negative:<8} {positive:<8} ${refunds:<9,.0f} ${charges:<9,.0f} ${net:<9,.0f} {refund_rate:.1f}%")
        
        if highest_refund_year:
            print(f"\n🚨 HIGHEST REFUND YEAR: {highest_refund_year} ({highest_refund_rate:.1f}% refund rate)")
        
        # Find specific high-value refunds
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                cc.description,
                cc.amount,
                c.notes
            FROM charters c
            JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE (LOWER(cc.description) LIKE '%beverage%'
                   OR LOWER(cc.description) LIKE '%alcohol%')
            AND cc.amount < -50  -- Significant refunds
            ORDER BY cc.amount ASC
            LIMIT 10
        """)
        
        large_refunds = cur.fetchall()
        
        if large_refunds:
            print(f"\n💸 LARGEST BEVERAGE REFUNDS:")
            for charter_id, reserve_no, date, desc, amount, notes in large_refunds:
                notes_short = (notes[:50] + '...') if notes and len(notes) > 50 else (notes or 'No notes')
                print(f"   • {reserve_no}: ${amount:.2f} - {desc} ({date})")
                print(f"     Notes: {notes_short}")
        
        return reimbursement_data, highest_refund_year
        
    except Exception as e:
        print(f"[FAIL] Error in reimbursement analysis: {str(e)}")
        return [], None
    
    finally:
        cur.close()
        conn.close()

def validate_booze_fest_theory():
    """Final validation of the 2012 booze fest loss theory."""
    
    print(f"\n🔬 BOOZE FEST THEORY VALIDATION")
    print("-" * 30)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get comprehensive 2012 beverage metrics
        cur.execute("""
            WITH charter_2012 AS (
                SELECT COUNT(*) as total_charters,
                       SUM(rate) as total_charter_revenue
                FROM charters 
                WHERE EXTRACT(year FROM charter_date) = 2012
            ),
            beverage_2012 AS (
                SELECT COUNT(*) as beverage_transactions,
                       SUM(cc.amount) as beverage_revenue,
                       COUNT(DISTINCT c.charter_id) as charters_with_beverages
                FROM charters c
                JOIN charter_charges cc ON c.charter_id = cc.charter_id
                WHERE EXTRACT(year FROM c.charter_date) = 2012
                AND (LOWER(cc.description) LIKE '%beverage%'
                     OR LOWER(cc.description) LIKE '%alcohol%')
            ),
            beverage_costs_2012 AS (
                SELECT SUM(gross_amount) as beverage_purchase_costs
                FROM receipts
                WHERE EXTRACT(year FROM receipt_date) = 2012
                AND (LOWER(COALESCE(vendor_name, '')) LIKE '%liquor%'
                     OR LOWER(COALESCE(description, '')) LIKE '%alcohol%'
                     OR LOWER(COALESCE(description, '')) LIKE '%beverage%')
            )
            SELECT 
                c.total_charters,
                c.total_charter_revenue,
                b.beverage_transactions,
                b.beverage_revenue,
                b.charters_with_beverages,
                bc.beverage_purchase_costs,
                b.beverage_revenue - COALESCE(bc.beverage_purchase_costs, 0) as beverage_profit,
                (b.charters_with_beverages * 100.0 / c.total_charters) as beverage_penetration,
                (b.beverage_revenue * 100.0 / c.total_charter_revenue) as beverage_revenue_share
            FROM charter_2012 c, beverage_2012 b, beverage_costs_2012 bc
        """)
        
        validation_data = cur.fetchone()
        
        if validation_data:
            (total_charters, charter_revenue, bev_transactions, bev_revenue, 
             charters_with_bev, bev_costs, bev_profit, bev_penetration, bev_revenue_share) = validation_data
            
            print(f"📊 2012 COMPREHENSIVE BEVERAGE METRICS:")
            print(f"   🎯 Total Charters: {total_charters:,}")
            print(f"   💰 Charter Revenue: ${charter_revenue:,.2f}")
            print(f"   🍾 Beverage Transactions: {bev_transactions:,}")
            print(f"   🍷 Charters with Beverages: {charters_with_bev:,}")
            print(f"   📊 Beverage Penetration: {bev_penetration:.1f}%")
            print(f"   💵 Beverage Revenue: ${bev_revenue:,.2f}")
            print(f"   📈 Beverage Revenue Share: {bev_revenue_share:.1f}% of total")
            print(f"   💸 Beverage Costs: ${bev_costs:,.2f}" if bev_costs else "   💸 Beverage Costs: $0.00 (no data)")
            print(f"   💰 Beverage Profit: ${bev_profit:,.2f}" if bev_profit else "   💰 Beverage Profit: Revenue only")
            
            # Theory validation
            print(f"\n🔬 THEORY VALIDATION RESULTS:")
            
            if bev_penetration and bev_penetration > 50:
                print(f"   [OK] HIGH BEVERAGE PENETRATION: {bev_penetration:.1f}% confirms active beverage service")
            else:
                print(f"   [WARN] MODERATE BEVERAGE PENETRATION: {bev_penetration:.1f}%")
            
            if bev_revenue_share and bev_revenue_share > 10:
                print(f"   🍾 SIGNIFICANT BEVERAGE REVENUE: {bev_revenue_share:.1f}% of total charter revenue")
            
            if bev_profit is not None:
                if bev_profit < -5000:
                    print(f"   🚨 CONFIRMED: SIGNIFICANT BEVERAGE LOSS of ${abs(bev_profit):,.2f}")
                    print(f"   🍷💸 BOOZE FEST THEORY: VALIDATED - Major losses confirmed")
                elif bev_profit < 0:
                    print(f"   [WARN] MINOR BEVERAGE LOSS: ${abs(bev_profit):,.2f}")
                    print(f"   🍷📊 BOOZE FEST THEORY: PARTIALLY VALIDATED - Some losses")
                else:
                    print(f"   [OK] BEVERAGE PROFIT: ${bev_profit:,.2f}")
                    print(f"   🍷💰 BOOZE FEST THEORY: REJECTED - Actually profitable!")
            else:
                print(f"   📊 INSUFFICIENT COST DATA: Can't determine profitability")
                print(f"   🍷❓ BOOZE FEST THEORY: INCONCLUSIVE - Need cost data")
            
            return validation_data
        
    except Exception as e:
        print(f"[FAIL] Error in theory validation: {str(e)}")
        return None
    
    finally:
        cur.close()
        conn.close()

def main():
    """Main beverage analysis and booze fest theory validation."""
    
    print("🍾 BEVERAGE ORDER CHARTER ANALYSIS")
    print("🍷 2012 BOOZE FEST THEORY INVESTIGATION")
    print("=" * 45)
    
    # Step 1: Analyze beverage charges matched to charters
    beverage_data, booze_fest_year = analyze_beverage_charter_matching()
    
    # Step 2: Deep dive into the identified booze fest year
    if booze_fest_year == 2012:
        print(f"\n🎯 CONFIRMED: 2012 was the peak beverage year!")
        analyze_2012_beverage_details()
    elif booze_fest_year:
        print(f"\n🤔 PLOT TWIST: {booze_fest_year} was the peak beverage year, not 2012!")
    
    # Step 3: Analyze costs vs pricing
    cost_data, worst_year, worst_loss = analyze_beverage_cost_vs_pricing()
    
    # Step 4: Analyze reimbursement patterns  
    refund_data, highest_refund_year = analyze_beverage_reimbursements()
    
    # Step 5: Validate the booze fest theory
    validation_result = validate_booze_fest_theory()
    
    # Final summary
    print(f"\n🏆 FINAL BOOZE FEST INVESTIGATION RESULTS")
    print("=" * 42)
    
    if booze_fest_year == 2012:
        print(f"[OK] THEORY CONFIRMED: 2012 was peak beverage activity year")
    else:
        print(f"[FAIL] THEORY ADJUSTED: {booze_fest_year or 'Unknown'} was peak beverage year")
    
    if worst_year == 2012 and worst_loss and worst_loss < -1000:
        print(f"🍷💸 LOSS CONFIRMED: 2012 had ${abs(worst_loss):,.0f} beverage loss")
    elif worst_year and worst_loss and worst_loss < 0:
        print(f"[WARN] LOSS FOUND: {worst_year} had ${abs(worst_loss):,.0f} beverage loss")
    else:
        print(f"💰 SURPRISE: Beverage operations were profitable overall!")
    
    if highest_refund_year == 2012:
        print(f"🔄 REIMBURSEMENT ISSUES: 2012 had highest refund rate")
    
    print(f"\n🎖️ BEVERAGE INVESTIGATION COMPLETE!")

if __name__ == "__main__":
    # Set database environment
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    main()