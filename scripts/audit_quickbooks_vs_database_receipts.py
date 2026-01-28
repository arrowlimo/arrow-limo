#!/usr/bin/env python3
"""
QuickBooks vs Database Receipt Audit
Compare receipts in database against QuickBooks archives to find missing data
"""

import psycopg2
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
import csv

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_database_receipts(cur, year):
    """Analyze receipts in database for specific year"""
    print(f"\n📊 DATABASE RECEIPTS ANALYSIS - {year}")
    print("=" * 50)
    
    # Receipt counts by source
    cur.execute("""
        SELECT 
            source_system,
            COUNT(*) as receipt_count,
            SUM(COALESCE(gross_amount, 0)) as total_amount,
            MIN(receipt_date) as earliest_date,
            MAX(receipt_date) as latest_date
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        GROUP BY source_system
        ORDER BY receipt_count DESC
    """, (year,))
    
    source_breakdown = cur.fetchall()
    
    print(f"Receipt Sources for {year}:")
    total_receipts = 0
    total_amount = 0
    
    for source, count, amount, earliest, latest in source_breakdown:
        total_receipts += count
        total_amount += float(amount) if amount else 0
        print(f"  {source or 'Unknown'}: {count} receipts, ${float(amount) if amount else 0:,.2f}")
        print(f"    Date range: {earliest} to {latest}")
    
    print(f"\nTOTAL: {total_receipts} receipts, ${total_amount:,.2f}")
    
    # Check for specific expense categories that should have more entries
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as count,
            SUM(COALESCE(gross_amount, 0)) as total
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = %s
        AND category IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
    """, (year,))
    
    categories = cur.fetchall()
    print(f"\nExpense Categories:")
    for category, count, total in categories:
        print(f"  {category}: {count} receipts, ${float(total):,.2f}")
    
    return source_breakdown, categories

def extract_quickbooks_transactions(zip_path):
    """Extract transaction data from QuickBooks XML export"""
    print(f"\n🔍 ANALYZING QUICKBOOKS DATA: {zip_path}")
    print("=" * 60)
    
    transactions = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Look for Transactions.xml
            if 'Transactions.xml' in zip_ref.namelist():
                with zip_ref.open('Transactions.xml') as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Count different transaction types
                    transaction_counts = {}
                    expense_transactions = []
                    
                    for transaction in root.findall('.//Transaction'):
                        trans_type = transaction.get('type', 'Unknown')
                        transaction_counts[trans_type] = transaction_counts.get(trans_type, 0) + 1
                        
                        # Look for expense-type transactions
                        if trans_type in ['Bill', 'Check', 'CreditCardCharge', 'Expense']:
                            date_elem = transaction.find('.//Date')
                            amount_elem = transaction.find('.//Amount')
                            vendor_elem = transaction.find('.//VendorRef')
                            memo_elem = transaction.find('.//Memo')
                            
                            if date_elem is not None:
                                trans_date = date_elem.text
                                amount = amount_elem.text if amount_elem is not None else '0'
                                vendor = vendor_elem.text if vendor_elem is not None else 'Unknown'
                                memo = memo_elem.text if memo_elem is not None else ''
                                
                                expense_transactions.append({
                                    'type': trans_type,
                                    'date': trans_date,
                                    'amount': amount,
                                    'vendor': vendor,
                                    'memo': memo
                                })
                    
                    print(f"Transaction Type Breakdown:")
                    for trans_type, count in sorted(transaction_counts.items()):
                        print(f"  {trans_type}: {count}")
                    
                    # Focus on 2012-2014 expenses
                    year_expenses = {}
                    for trans in expense_transactions:
                        if trans['date']:
                            try:
                                year = int(trans['date'][:4])
                                if 2012 <= year <= 2014:
                                    if year not in year_expenses:
                                        year_expenses[year] = []
                                    year_expenses[year].append(trans)
                            except:
                                pass
                    
                    print(f"\nExpense Transactions by Year:")
                    for year in sorted(year_expenses.keys()):
                        expenses = year_expenses[year]
                        total_amount = sum(float(t['amount']) for t in expenses if t['amount'].replace('.','').replace('-','').isdigit())
                        print(f"  {year}: {len(expenses)} transactions, ${total_amount:,.2f}")
                    
                    return year_expenses
    
    except Exception as e:
        print(f"[FAIL] Error processing {zip_path}: {str(e)}")
        return {}

def compare_database_vs_quickbooks():
    """Compare database receipts against QuickBooks data"""
    print("🔍 QUICKBOOKS vs DATABASE RECEIPT AUDIT")
    print("=" * 70)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Analyze database receipts for each year
        db_data = {}
        for year in [2012, 2013, 2014]:
            source_breakdown, categories = analyze_database_receipts(cur, year)
            db_data[year] = {
                'sources': source_breakdown,
                'categories': categories,
                'total_receipts': sum(row[1] for row in source_breakdown),
                'total_amount': sum(float(row[2]) if row[2] else 0 for row in source_breakdown)
            }
        
        # Analyze QuickBooks archives
        qb_archives = [
            'l:\\limo\\quickbooks\\already_imported\\CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip',
            'l:\\limo\\quickbooks\\already_imported\\CRAauditexport__2002-01-01_2025-12-31__20251019T205042.zip'
        ]
        
        qb_data = {}
        for archive_path in qb_archives:
            if os.path.exists(archive_path):
                year_expenses = extract_quickbooks_transactions(archive_path)
                for year, expenses in year_expenses.items():
                    if year not in qb_data:
                        qb_data[year] = []
                    qb_data[year].extend(expenses)
        
        # Compare findings
        print(f"\n📊 COMPARISON SUMMARY")
        print("=" * 50)
        
        for year in [2012, 2013, 2014]:
            db_receipts = db_data[year]['total_receipts']
            db_amount = db_data[year]['total_amount']
            qb_expenses = len(qb_data.get(year, []))
            qb_amount = sum(float(t['amount']) for t in qb_data.get(year, []) if t['amount'].replace('.','').replace('-','').isdigit())
            
            print(f"\n{year}:")
            print(f"  Database: {db_receipts} receipts, ${db_amount:,.2f}")
            print(f"  QuickBooks: {qb_expenses} expense transactions, ${qb_amount:,.2f}")
            print(f"  Variance: {qb_expenses - db_receipts} transactions, ${qb_amount - db_amount:,.2f}")
            
            if qb_expenses > db_receipts:
                print(f"  🚨 MISSING: {qb_expenses - db_receipts} transactions from QuickBooks not in database!")
        
        # Generate detailed report
        report_file = f"quickbooks_vs_database_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(report_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Source', 'Year', 'Count', 'Amount', 'Notes'])
            
            for year in [2012, 2013, 2014]:
                # Database data
                db_receipts = db_data[year]['total_receipts']
                db_amount = db_data[year]['total_amount']
                writer.writerow(['Database', year, db_receipts, db_amount, 'Current receipt records'])
                
                # QuickBooks data
                qb_expenses = len(qb_data.get(year, []))
                qb_amount = sum(float(t['amount']) for t in qb_data.get(year, []) if t['amount'].replace('.','').replace('-','').isdigit())
                writer.writerow(['QuickBooks', year, qb_expenses, qb_amount, 'QB expense transactions'])
        
        print(f"\n📄 DETAILED REPORT: {report_file}")
        
        return db_data, qb_data
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    compare_database_vs_quickbooks()