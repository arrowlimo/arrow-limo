#!/usr/bin/env python3
"""
Excel vs Database E-Transfer Reconciliation
===========================================

Compares the 321 e-transfers found in Excel files with database payment records
to identify matches and gaps for reconciliation.
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_database_etransfer_summary():
    """Get e-transfer summary from database"""
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'), 
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','')
    )
    cur = conn.cursor()
    
    # Check different variations of e-transfer in database
    etransfer_patterns = [
        "etransfer",
        "e-transfer", 
        "e transfer",
        "interac",
        "transfer"
    ]
    
    results = {}
    
    for pattern in etransfer_patterns:
        # Check payments table
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(payment_date) as earliest_date,
                   MAX(payment_date) as latest_date,
                   SUM(amount) as total_amount
            FROM payments 
            WHERE payment_method ILIKE %s
        """, (f'%{pattern}%',))
        
        result = cur.fetchone()
        if result and result[0] > 0:
            results[f"payments_{pattern}"] = {
                'count': result[0],
                'earliest': result[1],
                'latest': result[2], 
                'total_amount': float(result[3]) if result[3] else 0
            }
        
        # Check charters table - no payment_method column there based on schema
        # Skip charter table search for now as payment_method is in payments table
    
    # Get sample e-transfer records
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, notes, reference_number
        FROM payments 
        WHERE payment_method ILIKE '%transfer%' OR payment_method ILIKE '%interac%'
        ORDER BY payment_date DESC
        LIMIT 10
    """)
    
    sample_records = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return results, sample_records

def analyze_employee_email_patterns():
    """Analyze employee email patterns for e-transfer matching"""
    
    # Key employees mentioned in previous business rules
    key_employees = {
        'barb_peacock': ['babarapeacock.bp@gmail.com', 'b-peacock@outlook.com'],
        'michael_richard': ['pdrichard@shaw.ca'],  # Found as Dr100
        'david_richard': ['davidwr@shaw.ca']       # Found as Dr07
    }
    
    # Domain analysis from extracted emails
    email_domains = {}
    total_emails = 102  # From previous extraction
    
    # Common domains found
    domains = ['gmail.com', 'hotmail.com', 'shaw.ca', 'telus.net', 'yahoo.com', 'outlook.com', 'live.ca']
    
    return key_employees, domains

def main():
    """Generate reconciliation report"""
    
    print("🔍 EXCEL vs DATABASE E-TRANSFER RECONCILIATION")
    print("=" * 60)
    
    # Excel summary (from previous extraction)
    excel_summary = {
        '2002-2018': 82,
        '2019-2024': 235, 
        '2025': 4,
        'total': 321
    }
    
    print("\n📊 EXCEL FILE E-TRANSFER SUMMARY:")
    print("-" * 40)
    for period, count in excel_summary.items():
        print(f"{period}: {count} e-transfers")
    
    # Database summary
    print("\n💾 DATABASE E-TRANSFER SUMMARY:")
    print("-" * 40)
    
    db_results, sample_records = get_database_etransfer_summary()
    
    total_db_transfers = 0
    for key, data in db_results.items():
        if 'payments_' in key:
            print(f"Payment method '{key.split('_')[1]}': {data['count']} records")
            print(f"  Date range: {data['earliest']} to {data['latest']}")
            print(f"  Total amount: ${data['total_amount']:,.2f}")
            total_db_transfers += data['count']
    
    print(f"\nTotal database e-transfers: {total_db_transfers}")
    
    # Sample records
    print("\n📋 SAMPLE DATABASE E-TRANSFER RECORDS:")
    print("-" * 40)
    for i, record in enumerate(sample_records[:5], 1):
        payment_id, amount, date, method, notes, ref = record
        print(f"{i}. ID:{payment_id} | ${amount} | {date} | {method}")
        if notes: print(f"   Notes: {notes[:50]}...")
        if ref: print(f"   Ref: {ref}")
    
    # Employee analysis
    print("\n👥 EMPLOYEE EMAIL ANALYSIS:")
    print("-" * 40)
    
    key_employees, domains = analyze_employee_email_patterns()
    
    print("Key employees found in email list:")
    for name, emails in key_employees.items():
        print(f"  {name.replace('_', ' ').title()}: {emails}")
    
    print(f"\nTotal employees with emails: 102")
    print("Top email domains:", domains[:5])
    
    # Reconciliation analysis
    print("\n🔗 RECONCILIATION ANALYSIS:")
    print("-" * 40)
    
    gap = excel_summary['total'] - total_db_transfers
    print(f"Excel total e-transfers: {excel_summary['total']}")
    print(f"Database total e-transfers: {total_db_transfers}")
    print(f"Gap to reconcile: {gap}")
    
    if gap > 0:
        print(f"\n[WARN]  {gap} e-transfers from Excel files need to be imported to database")
    elif gap < 0:
        print(f"\n[OK] Database has {abs(gap)} more e-transfers than Excel files")
    else:
        print(f"\n[OK] Excel and database e-transfer counts match!")
    
    # Business rule insights
    print("\n💼 BUSINESS RULE INSIGHTS:")
    print("-" * 40)
    print("Based on previous business rules:")
    print("• Barb Peacock e-transfers → Personal transactions")
    print("• Michael Richard e-transfers → Driver payments") 
    print("• David Richard e-transfers → Loan payments")
    print("• Other employee emails → Potential payroll e-transfers")
    
    print(f"\n📈 NEXT STEPS:")
    print("1. Import missing e-transfer records from Excel to database")
    print("2. Match employee emails to payment recipient fields")
    print("3. Apply business rules for transaction categorization")
    print("4. Cross-reference with banking transaction data")
    print("5. Generate audit report for CRA compliance")

if __name__ == "__main__":
    main()