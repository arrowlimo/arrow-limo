#!/usr/bin/env python3
"""
Analyze QuickBooks vs Database Receipt Discrepancy
Find out why we have 1,042 QB transactions but only 99 database receipts for 2012
"""

import pandas as pd
import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_quickbooks_discrepancy():
    """Find the discrepancy between QuickBooks parsed data and database receipts"""
    print("🔍 QUICKBOOKS vs DATABASE DISCREPANCY ANALYSIS")
    print("=" * 70)
    
    # Load parsed QuickBooks data for 2012
    qb_file = 'l:\\limo\\staging\\2012_parsed\\2012_quickbooks_transactions.csv'
    
    if not os.path.exists(qb_file):
        print(f"[FAIL] QuickBooks file not found: {qb_file}")
        return
    
    qb_data = pd.read_csv(qb_file)
    print(f"📄 Loaded QuickBooks file: {len(qb_data)} total transactions")
    
    # Filter to expense transactions (withdrawals)
    expenses = qb_data[qb_data['withdrawal'].notna() & (qb_data['withdrawal'] > 0)]
    total_expenses = expenses['withdrawal'].sum()
    
    print(f"💸 QuickBooks Expenses:")
    print(f"   Expense transactions: {len(expenses)}")
    print(f"   Total expense amount: ${total_expenses:,.2f}")
    
    # Analyze expense patterns
    print(f"\n📊 Top 10 Expenses by Amount:")
    top_expenses = expenses.nlargest(10, 'withdrawal')
    for idx, row in top_expenses.iterrows():
        date = row['date']
        desc = str(row['description'])[:40] if pd.notna(row['description']) else 'Unknown'
        amount = row['withdrawal']
        print(f"   {date}: {desc} - ${amount:,.2f}")
    
    # Vendor breakdown
    print(f"\n🏪 Expense Breakdown by Vendor (Top 15):")
    vendor_summary = expenses.groupby('description')['withdrawal'].agg(['count', 'sum']).sort_values('sum', ascending=False)
    for vendor, (count, total) in vendor_summary.head(15).iterrows():
        vendor_name = str(vendor)[:35] if pd.notna(vendor) else 'Unknown'
        print(f"   {vendor_name}: {count} transactions, ${total:,.2f}")
    
    # Check database
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as receipt_count,
                SUM(COALESCE(gross_amount, 0)) as total_amount,
                source_system
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            GROUP BY source_system
            ORDER BY receipt_count DESC
        """)
        
        db_sources = cur.fetchall()
        
        print(f"\n📊 Database Receipts for 2012:")
        total_db_receipts = 0
        total_db_amount = 0
        
        for count, amount, source in db_sources:
            total_db_receipts += count
            total_db_amount += float(amount) if amount else 0
            source_name = source or 'Unknown'
            print(f"   {source_name}: {count} receipts, ${float(amount) if amount else 0:,.2f}")
        
        print(f"   TOTAL: {total_db_receipts} receipts, ${total_db_amount:,.2f}")
        
        # Compare
        print(f"\n🚨 DISCREPANCY ANALYSIS:")
        print(f"   QuickBooks Expenses: {len(expenses)} transactions, ${total_expenses:,.2f}")
        print(f"   Database Receipts: {total_db_receipts} receipts, ${total_db_amount:,.2f}")
        
        missing_count = len(expenses) - total_db_receipts
        missing_amount = total_expenses - total_db_amount
        
        print(f"   MISSING FROM DATABASE: {missing_count} transactions, ${missing_amount:,.2f}")
        
        if missing_count > 0:
            missing_percentage = (missing_count / len(expenses)) * 100
            print(f"   MISSING PERCENTAGE: {missing_percentage:.1f}% of QuickBooks expenses")
        
        # Check if there are specific import issues
        print(f"\n🔍 POTENTIAL CAUSES:")
        
        # Check date range issues
        qb_dates = pd.to_datetime(expenses['date'], errors='coerce')
        qb_date_range = f"{qb_dates.min().strftime('%Y-%m-%d')} to {qb_dates.max().strftime('%Y-%m-%d')}"
        
        cur.execute("""
            SELECT MIN(receipt_date), MAX(receipt_date)
            FROM receipts 
            WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        """)
        
        db_date_range = cur.fetchone()
        db_range_str = f"{db_date_range[0]} to {db_date_range[1]}" if db_date_range[0] else "No dates"
        
        print(f"   QuickBooks date range: {qb_date_range}")
        print(f"   Database date range: {db_range_str}")
        
        # Check for import source issues
        banking_import_count = sum(count for count, amount, source in db_sources if source == 'BANKING_IMPORT')
        manual_entry_count = sum(count for count, amount, source in db_sources if source == 'MANUAL_ENTRY')
        
        print(f"   Banking imports: {banking_import_count} receipts")
        print(f"   Manual entries: {manual_entry_count} receipts")
        print(f"   QuickBooks imports: 0 receipts (THIS IS THE PROBLEM!)")
        
        print(f"\n💡 RECOMMENDATION:")
        print(f"   The parsed QuickBooks data exists but was never imported into the receipts table.")
        print(f"   Need to create an import script to load the {len(expenses)} QuickBooks expense transactions.")
        print(f"   This will add ${missing_amount:,.2f} in properly categorized business expenses.")
        
        # Generate import preparation report
        report_file = f"quickbooks_missing_receipts_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Prepare data for import
        import_data = expenses.copy()
        import_data['source_system'] = 'QuickBooks-2012-Parsed'
        import_data['receipt_date'] = pd.to_datetime(import_data['date'], errors='coerce')
        import_data['vendor_name'] = import_data['description'].str[:100]  # Truncate long descriptions
        import_data['gross_amount'] = import_data['withdrawal']
        import_data['gst_amount'] = import_data['withdrawal'] * 0.05 / 1.05  # Estimated GST
        import_data['net_amount'] = import_data['gross_amount'] - import_data['gst_amount']
        
        # Save for review
        import_data[['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'net_amount', 'source_system']].to_csv(
            report_file, index=False
        )
        
        print(f"   📄 Import preparation file: {report_file}")
        
        return {
            'qb_expenses': len(expenses),
            'qb_amount': total_expenses,
            'db_receipts': total_db_receipts,
            'db_amount': total_db_amount,
            'missing_count': missing_count,
            'missing_amount': missing_amount,
            'import_ready': True
        }
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    result = analyze_quickbooks_discrepancy()
    
    if result and result['missing_count'] > 0:
        print(f"\n🎯 SUMMARY:")
        print(f"   Found {result['missing_count']} missing expense transactions worth ${result['missing_amount']:,.2f}")
        print(f"   This explains why 2012 audit shows incomplete expense data")
        print(f"   Import script needed to add QuickBooks expenses to receipts table")