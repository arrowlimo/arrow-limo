#!/usr/bin/env python3
"""
Phase 3 Enhancement Strategy: Data Quality & Gap Analysis

Based on discovery showing comprehensive 2017-2025 coverage, 
focus on data quality improvements and specialized enhancements.

Current 2017-2025 status:
- Receipts: 46,246 records, $15.9M 
- Charters: 6,800 records, $1.6M
- Payments: 22,886 records, $11.1M
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
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_data_quality_opportunities():
    """Analyze opportunities for data quality improvements."""
    
    print("PHASE 3 ENHANCEMENT STRATEGY - DATA QUALITY ANALYSIS")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Charter Revenue Completion Analysis
    print("🔍 CHARTER REVENUE COMPLETION ANALYSIS:")
    print("-" * 40)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total_charters,
            COUNT(CASE WHEN total_amount_due > 0 THEN 1 END) as charters_with_amount,
            SUM(COALESCE(total_amount_due, 0)) as total_revenue,
            AVG(COALESCE(total_amount_due, 0)) as avg_amount
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    charter_analysis = cur.fetchall()
    charter_gaps = []
    
    for year, total, with_amount, revenue, avg_amount in charter_analysis:
        year_int = int(year) if year else 0
        completion_pct = (with_amount / total * 100) if total > 0 else 0
        
        print(f"{year_int}: {total:,} charters, {with_amount:,} with amounts ({completion_pct:.1f}%)")
        print(f"      Revenue: ${revenue or 0:,.2f}, Avg: ${avg_amount or 0:.2f}")
        
        if completion_pct < 80:  # Less than 80% completion
            charter_gaps.append({
                'year': year_int,
                'total_charters': total,
                'missing_amounts': total - with_amount,
                'completion_pct': completion_pct
            })
    
    # 2. Receipt Categorization Analysis
    print(f"\n📊 RECEIPT CATEGORIZATION ANALYSIS:")
    print("-" * 35)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as total_receipts,
            COUNT(CASE WHEN category IS NULL OR category = '' THEN 1 END) as uncategorized,
            COUNT(DISTINCT category) as unique_categories
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    categorization_analysis = cur.fetchall()
    categorization_gaps = []
    
    for year, total, uncategorized, categories in categorization_analysis:
        year_int = int(year) if year else 0
        categorized_pct = ((total - uncategorized) / total * 100) if total > 0 else 0
        
        print(f"{year_int}: {total:,} receipts, {uncategorized:,} uncategorized ({100-categorized_pct:.1f}%)")
        print(f"      Categories used: {categories}")
        
        if categorized_pct < 90:  # Less than 90% categorized
            categorization_gaps.append({
                'year': year_int,
                'total_receipts': total,
                'uncategorized': uncategorized,
                'categorized_pct': categorized_pct
            })
    
    # 3. Payment-Charter Linkage Analysis
    print(f"\n🔗 PAYMENT-CHARTER LINKAGE ANALYSIS:")
    print("-" * 35)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as total_payments,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked_to_charters,
            COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as linked_to_reserves
        FROM payments 
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    
    linkage_analysis = cur.fetchall()
    linkage_gaps = []
    
    for year, total, charter_linked, reserve_linked in linkage_analysis:
        year_int = int(year) if year else 0
        charter_link_pct = (charter_linked / total * 100) if total > 0 else 0
        reserve_link_pct = (reserve_linked / total * 100) if total > 0 else 0
        
        print(f"{year_int}: {total:,} payments")
        print(f"      Charter linked: {charter_linked:,} ({charter_link_pct:.1f}%)")
        print(f"      Reserve linked: {reserve_linked:,} ({reserve_link_pct:.1f}%)")
        
        if reserve_link_pct < 70:  # Less than 70% linked to reserves
            linkage_gaps.append({
                'year': year_int,
                'total_payments': total,
                'unlinked': total - reserve_linked,
                'link_pct': reserve_link_pct
            })
    
    # 4. Data Source Diversity Analysis
    print(f"\n📈 DATA SOURCE DIVERSITY ANALYSIS:")
    print("-" * 35)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(DISTINCT source_system) as source_count,
            string_agg(DISTINCT source_system, ', ' ORDER BY source_system) as sources
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    source_analysis = cur.fetchall()
    
    for year, source_count, sources in source_analysis:
        year_int = int(year) if year else 0
        print(f"{year_int}: {source_count} sources")
        print(f"      Sources: {sources}")
    
    return {
        'charter_gaps': charter_gaps,
        'categorization_gaps': categorization_gaps,
        'linkage_gaps': linkage_gaps
    }

def analyze_banking_integration_opportunities():
    """Analyze opportunities for banking data integration enhancement."""
    
    print(f"\n💳 BANKING INTEGRATION OPPORTUNITIES:")
    print("-" * 40)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check banking transaction coverage
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as transactions,
            SUM(COALESCE(debit_amount, 0)) as total_debits,
            SUM(COALESCE(credit_amount, 0)) as total_credits,
            COUNT(CASE WHEN category IS NULL THEN 1 END) as uncategorized
        FROM banking_transactions 
        WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    
    banking_data = cur.fetchall()
    
    if banking_data:
        print("Banking transaction coverage:")
        for year, transactions, debits, credits, uncategorized in banking_data:
            year_int = int(year) if year else 0
            categorized_pct = ((transactions - uncategorized) / transactions * 100) if transactions > 0 else 0
            print(f"{year_int}: {transactions:,} transactions, ${debits:,.2f} debits, ${credits:,.2f} credits")
            print(f"      Categorized: {categorized_pct:.1f}%")
    else:
        print("No banking transaction data found for 2017-2025")
        print("Opportunity: Import recent banking data for enhanced reconciliation")
    
    # Check email financial events
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM email_date) as year,
            COUNT(*) as email_events,
            SUM(COALESCE(amount, 0)) as total_amount,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as matched_to_banking
        FROM email_financial_events 
        WHERE EXTRACT(YEAR FROM email_date) BETWEEN 2017 AND 2025
        GROUP BY EXTRACT(YEAR FROM email_date)
        ORDER BY year
    """)
    
    email_data = cur.fetchall()
    
    if email_data:
        print(f"\nEmail financial events coverage:")
        for year, events, amount, matched in email_data:
            year_int = int(year) if year else 0
            match_pct = (matched / events * 100) if events > 0 else 0
            print(f"{year_int}: {events:,} events, ${amount:,.2f} total")
            print(f"      Matched to banking: {matched:,} ({match_pct:.1f}%)")
    else:
        print(f"\nNo email financial events found for 2017-2025")
        print("Opportunity: Process recent emails for financial event extraction")

def generate_phase3_enhancement_plan(analysis_results):
    """Generate specific enhancement recommendations."""
    
    print(f"\n🎯 PHASE 3 ENHANCEMENT PLAN:")
    print("=" * 30)
    
    priorities = []
    
    # Charter revenue completion priorities
    if analysis_results['charter_gaps']:
        print("🏆 HIGH PRIORITY: Charter Revenue Completion")
        for gap in analysis_results['charter_gaps']:
            year = gap['year']
            missing = gap['missing_amounts']
            pct = gap['completion_pct']
            print(f"   {year}: {missing:,} charters missing amounts ({pct:.1f}% complete)")
            
        priorities.append({
            'priority': 'HIGH',
            'task': 'Charter Revenue Completion',
            'description': f'Complete revenue data for {len(analysis_results["charter_gaps"])} years with gaps',
            'estimated_impact': 'Improved revenue tracking and business intelligence'
        })
    
    # Receipt categorization priorities
    if analysis_results['categorization_gaps']:
        print(f"\n📊 MEDIUM PRIORITY: Receipt Categorization")
        for gap in analysis_results['categorization_gaps']:
            year = gap['year']
            uncategorized = gap['uncategorized']
            pct = gap['categorized_pct']
            print(f"   {year}: {uncategorized:,} uncategorized receipts ({pct:.1f}% categorized)")
            
        priorities.append({
            'priority': 'MEDIUM',
            'task': 'Receipt Categorization Enhancement',
            'description': f'Categorize receipts for {len(analysis_results["categorization_gaps"])} years',
            'estimated_impact': 'Enhanced expense reporting and CRA compliance'
        })
    
    # Payment linkage priorities
    if analysis_results['linkage_gaps']:
        print(f"\n🔗 MEDIUM PRIORITY: Payment-Charter Linkage")
        for gap in analysis_results['linkage_gaps']:
            year = gap['year']
            unlinked = gap['unlinked']
            pct = gap['link_pct']
            print(f"   {year}: {unlinked:,} unlinked payments ({pct:.1f}% linked)")
            
        priorities.append({
            'priority': 'MEDIUM',
            'task': 'Payment-Charter Linkage Enhancement',
            'description': f'Link payments to charters for {len(analysis_results["linkage_gaps"])} years',
            'estimated_impact': 'Complete revenue reconciliation and audit trail'
        })
    
    # Strategic opportunities
    print(f"\n💡 STRATEGIC OPPORTUNITIES:")
    print("   • Banking Data Integration: Enhanced transaction reconciliation")
    print("   • Email Processing: Automated financial event extraction")
    print("   • Real-time Analytics: Dashboard development for operational insights")
    print("   • API Enhancement: Modern FastAPI endpoints for business intelligence")
    
    return priorities

def main():
    """Execute Phase 3 enhancement strategy analysis."""
    
    print("Building on Phase 1 ($4.92M) + Phase 2 ($81K) = $5M+ Recovery Success")
    print("Focus: Data quality improvements and strategic enhancements")
    print()
    
    # Analyze current data quality
    analysis_results = analyze_data_quality_opportunities()
    
    # Analyze banking integration opportunities  
    analyze_banking_integration_opportunities()
    
    # Generate enhancement plan
    priorities = generate_phase3_enhancement_plan(analysis_results)
    
    print(f"\n🚀 PHASE 3 EXECUTION READY:")
    print("=" * 30)
    if priorities:
        print(f"[OK] {len(priorities)} enhancement priorities identified")
        print(f"📊 Focus on data quality improvements over new data discovery")
        print(f"💎 Strategic value: Enhanced business intelligence and compliance")
    else:
        print(f"[OK] Excellent data quality detected")
        print(f"💡 Focus on strategic enhancements and process automation")
    
    print(f"\n💪 COMPREHENSIVE DATA RECOVERY PROJECT STATUS:")
    print(f"• Phase 1: HISTORIC SUCCESS - $4.92M recovered")
    print(f"• Phase 2: EXCELLENT COMPLETION - $81K specialized data")  
    print(f"• Phase 3: ENHANCEMENT FOCUS - Quality & intelligence improvements")
    print(f"• TOTAL PROJECT VALUE: $5M+ data recovery + quality enhancement")

if __name__ == "__main__":
    main()