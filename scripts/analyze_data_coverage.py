#!/usr/bin/env python3
"""
Analyze Financial Data Coverage by Year

This script examines all imported financial data to determine
which years have complete information and identify gaps.
"""

import psycopg2
from collections import defaultdict
from decimal import Decimal

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres'
}

def analyze_data_coverage():
    """Analyze financial data coverage by year."""
    
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("=== FINANCIAL DATA COVERAGE BY YEAR ===\n")
    
    # Charter Payments Analysis
    print("📊 CHARTER PAYMENTS:")
    cursor.execute("""
        SELECT EXTRACT(YEAR FROM payment_date) as year, 
               COUNT(*) as records,
               MIN(payment_date) as earliest,
               MAX(payment_date) as latest,
               SUM(amount) as total_amount
        FROM charter_payments 
        WHERE payment_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    charter_data = cursor.fetchall()
    charter_years = set()
    
    for row in charter_data:
        year, count, earliest, latest, total = row
        charter_years.add(int(year))
        print(f"  {int(year)}: {count:,} payments (${total:,.2f}) - {earliest} to {latest}")
    
    # Driver Payroll Analysis
    print("\n💰 DRIVER PAYROLL:")
    cursor.execute("""
        SELECT year, month,
               COUNT(*) as records,
               COUNT(DISTINCT driver_id) as drivers,
               SUM(gross_pay) as total_gross,
               SUM(net_pay) as total_net
        FROM driver_payroll 
        GROUP BY year, month
        ORDER BY year, month
    """)
    payroll_data = cursor.fetchall()
    
    # Group by year for summary
    payroll_by_year = defaultdict(lambda: {
        'records': 0, 'months': set(), 'drivers': set(), 
        'gross': Decimal('0'), 'net': Decimal('0')
    })
    payroll_years = set()
    
    for row in payroll_data:
        year, month, records, drivers, gross, net = row
        payroll_years.add(year)
        payroll_by_year[year]['records'] += records
        payroll_by_year[year]['months'].add(month)
        payroll_by_year[year]['drivers'].add(drivers)
        payroll_by_year[year]['gross'] += gross or Decimal('0')
        payroll_by_year[year]['net'] += net or Decimal('0')
    
    for year in sorted(payroll_by_year.keys()):
        data = payroll_by_year[year]
        months = sorted(data['months'])
        drivers_count = max(data['drivers']) if data['drivers'] else 0
        month_range = f"{min(months)}-{max(months)}" if len(months) > 1 else str(months[0])
        print(f"  {year}: {data['records']:,} records, {len(months)} months ({month_range}), ~{drivers_count} drivers")
        print(f"        Gross: ${data['gross']:,.2f}, Net: ${data['net']:,.2f}")
    
    # WCB Summary Analysis
    print("\n🏢 WCB SUMMARY:")
    cursor.execute("""
        SELECT year,
               COUNT(*) as records,
               COUNT(DISTINCT driver_id) as drivers,
               COUNT(DISTINCT month) as months,
               SUM(wcb_payment) as total_wcb,
               SUM(total_gross_pay) as total_gross
        FROM wcb_summary 
        GROUP BY year
        ORDER BY year
    """)
    wcb_data = cursor.fetchall()
    wcb_years = set()
    
    for row in wcb_data:
        year, records, drivers, months, wcb_total, gross_total = row
        wcb_years.add(year)
        wcb_amt = wcb_total or Decimal('0')
        print(f"  {year}: {records} records, {drivers} drivers, {months} months - WCB: ${wcb_amt:,.2f}")
    
    # Financial Documents Analysis
    print("\n📄 FINANCIAL DOCUMENTS:")
    cursor.execute("""
        SELECT EXTRACT(YEAR FROM document_date) as year,
               document_type,
               COUNT(*) as count
        FROM financial_documents 
        WHERE document_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM document_date), document_type
        ORDER BY year, document_type
    """)
    docs_data = cursor.fetchall()
    
    # Group by year
    docs_by_year = defaultdict(lambda: defaultdict(int))
    doc_years = set()
    
    for row in docs_data:
        year, doc_type, count = row
        year_int = int(year)
        doc_years.add(year_int)
        docs_by_year[year_int][doc_type] = count
    
    for year in sorted(docs_by_year.keys()):
        types = docs_by_year[year]
        total = sum(types.values())
        type_summary = ', '.join([f"{k}: {v}" for k, v in sorted(types.items())])
        print(f"  {year}: {total} documents - {type_summary}")
    
    # Invoice Tracking Analysis
    print("\n📋 INVOICE TRACKING:")
    cursor.execute("""
        SELECT EXTRACT(YEAR FROM invoice_date) as year,
               COUNT(*) as invoices,
               COUNT(CASE WHEN amount IS NOT NULL THEN 1 END) as with_amounts,
               SUM(amount) as total_amount
        FROM invoice_tracking 
        WHERE invoice_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM invoice_date)
        ORDER BY year
    """)
    invoice_data = cursor.fetchall()
    invoice_years = set()
    
    for row in invoice_data:
        year, invoices, with_amounts, total = row
        invoice_years.add(int(year))
        total_amt = total or Decimal('0')
        print(f"  {int(year)}: {invoices} invoices ({with_amounts} with amounts) - ${total_amt:,.2f}")
    
    # Check existing database for other data
    print("\n🔍 OTHER DATABASE TABLES:")
    
    # Check if there are existing tables we haven't accounted for
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    all_tables = [row[0] for row in cursor.fetchall()]
    
    financial_tables = {'charter_payments', 'driver_payroll', 'wcb_summary', 'financial_documents', 'invoice_tracking'}
    other_tables = [t for t in all_tables if t not in financial_tables]
    
    for table in other_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,} records")
        except Exception as e:
            print(f"  {table}: Error reading - {e}")
    
    # Summary Analysis
    print("\n" + "="*60)
    print("📈 YEAR-BY-YEAR COMPLETENESS ANALYSIS")
    print("="*60)
    
    # Find all years with any data
    all_years = charter_years | payroll_years | wcb_years | doc_years | invoice_years
    
    for year in sorted(all_years):
        print(f"\n📅 YEAR {year}:")
        
        # Charter data
        if year in charter_years:
            charter_info = next((row for row in charter_data if int(row[0]) == year), None)
            if charter_info:
                amount = charter_info[4] or Decimal('0')
                print(f"  [OK] Charter Payments: {charter_info[1]:,} records (${amount:,.2f})")
        else:
            print(f"  [FAIL] Charter Payments: NO DATA")
        
        # Payroll data
        if year in payroll_years:
            payroll_info = payroll_by_year[year]
            months = len(payroll_info['months'])
            print(f"  [OK] Payroll: {payroll_info['records']:,} records across {months} months")
        else:
            print(f"  [FAIL] Payroll: NO DATA")
        
        # WCB data
        if year in wcb_years:
            wcb_info = next((row for row in wcb_data if row[0] == year), None)
            if wcb_info:
                print(f"  [OK] WCB: {wcb_info[1]} records for {wcb_info[2]} drivers")
        else:
            print(f"  [FAIL] WCB: NO DATA")
        
        # Document data
        if year in doc_years:
            doc_count = sum(docs_by_year[year].values())
            print(f"  [OK] Financial Documents: {doc_count} documents")
        else:
            print(f"  [FAIL] Financial Documents: NO DATA")
        
        # Completeness assessment
        data_types = []
        if year in charter_years:
            data_types.append("Charters")
        if year in payroll_years:
            data_types.append("Payroll")
        if year in wcb_years:
            data_types.append("WCB")
        if year in doc_years:
            data_types.append("Documents")
        
        completeness = len(data_types) / 4.0 * 100
        status = "🟢 COMPLETE" if completeness >= 75 else "🟡 PARTIAL" if completeness >= 50 else "🔴 INCOMPLETE"
        
        print(f"  📊 Data Coverage: {completeness:.0f}% - {status}")
        print(f"     Available: {', '.join(data_types) if data_types else 'None'}")
    
    conn.close()

if __name__ == "__main__":
    analyze_data_coverage()