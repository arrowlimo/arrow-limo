#!/usr/bin/env python3
"""
Analyze uncategorized e-transfers to identify patterns for new categories.
Looks at banking descriptions and receipt vendor names for frequent payments.
"""

import psycopg2
import sys
from collections import defaultdict
import re

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def normalize_vendor(vendor_name):
    """Normalize vendor name for grouping."""
    if not vendor_name:
        return ""
    
    vendor = vendor_name.upper().strip()
    
    # Remove common prefixes
    prefixes = ['PURCHASE', 'E-TRANSFER', 'INTERNET BANKING', 'DEBIT MEMO', 
                'CREDIT MEMO', 'CHEQUE', 'CHQ', 'PRE-AUTH', 'PAD']
    for prefix in prefixes:
        if vendor.startswith(prefix):
            vendor = vendor[len(prefix):].strip()
    
    # Remove card numbers
    vendor = re.sub(r'\d{4}\*+\d{3,4}', '', vendor)
    
    # Remove location codes
    vendor = re.sub(r'\b(RED DEER|LETHBRIDGE|CALGARY|EDMONTON|AB)\b', '', vendor)
    
    # Remove store numbers
    vendor = re.sub(r'#\d+', '', vendor)
    
    # Clean up whitespace
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    
    return vendor

def analyze_uncategorized_etransfers():
    """Analyze uncategorized e-transfers by banking description patterns."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("UNCATEGORIZED E-TRANSFER PATTERN ANALYSIS")
    print("=" * 100)
    
    # Get uncategorized e-transfers with banking descriptions
    cur.execute("""
        SELECT 
            et.etransfer_id,
            et.direction,
            et.amount,
            et.transaction_date,
            bt.description
        FROM etransfer_transactions et
        JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
        WHERE et.category IS NULL
        AND bt.description IS NOT NULL
        ORDER BY et.transaction_date
    """)
    
    uncategorized = cur.fetchall()
    print(f"\nTotal uncategorized e-transfers with banking descriptions: {len(uncategorized):,}")
    
    # Group by normalized vendor/description
    vendor_groups = defaultdict(lambda: {'count': 0, 'total': 0, 'transactions': [], 'in': 0, 'out': 0})
    
    for etrans_id, direction, amount, tdate, description in uncategorized:
        # Try to extract meaningful vendor name
        vendor = normalize_vendor(description)
        
        if vendor:
            vendor_groups[vendor]['count'] += 1
            vendor_groups[vendor]['total'] += float(amount)
            vendor_groups[vendor]['transactions'].append({
                'id': etrans_id,
                'direction': direction,
                'amount': float(amount),
                'date': tdate,
                'description': description
            })
            if direction == 'IN':
                vendor_groups[vendor]['in'] += 1
            else:
                vendor_groups[vendor]['out'] += 1
    
    # Sort by frequency
    sorted_vendors = sorted(vendor_groups.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print("\n" + "=" * 100)
    print("TOP VENDORS/RECIPIENTS BY FREQUENCY (10+ transactions)")
    print("=" * 100)
    print(f"{'Vendor/Recipient':<50} | {'Count':>6} | {'Total':>12} | {'IN':>5} | {'OUT':>5}")
    print("-" * 100)
    
    for vendor, data in sorted_vendors:
        if data['count'] >= 10:  # Only show frequent patterns
            print(f"{vendor[:50]:<50} | {data['count']:>6} | ${data['total']:>11,.2f} | {data['in']:>5} | {data['out']:>5}")
    
    # Show samples for top patterns
    print("\n" + "=" * 100)
    print("SAMPLE TRANSACTIONS FOR TOP PATTERNS")
    print("=" * 100)
    
    for vendor, data in sorted_vendors[:20]:  # Top 20 patterns
        if data['count'] >= 5:
            print(f"\n{vendor} ({data['count']} transactions, ${data['total']:,.2f})")
            print("-" * 100)
            
            # Show first 5 transactions
            for trans in data['transactions'][:5]:
                print(f"  {trans['direction']:>3} | {trans['date']} | ${trans['amount']:>10,.2f} | {trans['description'][:70]}")
            
            if len(data['transactions']) > 5:
                print(f"  ... and {len(data['transactions']) - 5} more")
    
    cur.close()
    conn.close()

def analyze_receipt_patterns():
    """Analyze receipt vendor patterns for uncategorized items."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n\n" + "=" * 100)
    print("RECEIPT VENDOR PATTERN ANALYSIS")
    print("=" * 100)
    
    # Get receipts without category or with 'uncategorized'
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE (category IS NULL OR category = 'uncategorized')
        AND vendor_name IS NOT NULL
        GROUP BY vendor_name
        HAVING COUNT(*) >= 5
        ORDER BY COUNT(*) DESC
        LIMIT 50
    """)
    
    vendors = cur.fetchall()
    
    print(f"\nVendors with 5+ uncategorized receipts:")
    print(f"{'Vendor Name':<40} | {'Count':>6} | {'Total':>12} | {'First Date'} | {'Last Date'}")
    print("-" * 100)
    
    for vendor, count, total, first_date, last_date in vendors:
        print(f"{vendor[:40]:<40} | {count:>6} | ${float(total):>11,.2f} | {first_date} | {last_date}")
    
    # Get sample receipts for top vendors
    print("\n" + "=" * 100)
    print("SAMPLE RECEIPTS FOR TOP UNCATEGORIZED VENDORS")
    print("=" * 100)
    
    for vendor, count, total, first_date, last_date in vendors[:15]:
        print(f"\n{vendor} ({count} receipts, ${float(total):,.2f})")
        print("-" * 100)
        
        cur.execute("""
            SELECT receipt_date, gross_amount, description
            FROM receipts
            WHERE vendor_name = %s
            AND (category IS NULL OR category = 'uncategorized')
            ORDER BY receipt_date DESC
            LIMIT 5
        """, (vendor,))
        
        samples = cur.fetchall()
        for rdate, amount, desc in samples:
            print(f"  {rdate} | ${float(amount):>10,.2f} | {desc[:60] if desc else ''}")
    
    cur.close()
    conn.close()

def analyze_banking_debit_patterns():
    """Analyze banking transaction debit patterns (expenses)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n\n" + "=" * 100)
    print("BANKING DEBIT PATTERN ANALYSIS (Non-E-Transfer Expenses)")
    print("=" * 100)
    
    # Get banking debits that aren't linked to e-transfers or receipts
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount
        FROM banking_transactions bt
        WHERE bt.debit_amount > 0
        AND bt.transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM etransfer_transactions 
            WHERE banking_transaction_id IS NOT NULL
        )
        AND bt.transaction_id NOT IN (
            SELECT banking_transaction_id
            FROM banking_receipt_matching_ledger
            WHERE banking_transaction_id IS NOT NULL
        )
        ORDER BY bt.transaction_date
    """)
    
    unlinked_debits = cur.fetchall()
    print(f"\nTotal unlinked banking debits: {len(unlinked_debits):,}")
    
    # Group by normalized description
    debit_groups = defaultdict(lambda: {'count': 0, 'total': 0, 'transactions': []})
    
    for trans_id, tdate, description, amount in unlinked_debits:
        vendor = normalize_vendor(description)
        
        if vendor:
            debit_groups[vendor]['count'] += 1
            debit_groups[vendor]['total'] += float(amount)
            debit_groups[vendor]['transactions'].append({
                'id': trans_id,
                'date': tdate,
                'amount': float(amount),
                'description': description
            })
    
    # Sort by frequency
    sorted_debits = sorted(debit_groups.items(), key=lambda x: x[1]['count'], reverse=True)
    
    print("\n" + "=" * 100)
    print("TOP UNLINKED BANKING DEBITS BY FREQUENCY (5+ transactions)")
    print("=" * 100)
    print(f"{'Vendor/Description':<50} | {'Count':>6} | {'Total':>12}")
    print("-" * 100)
    
    for vendor, data in sorted_debits:
        if data['count'] >= 5:
            print(f"{vendor[:50]:<50} | {data['count']:>6} | ${data['total']:>11,.2f}")
    
    # Show samples
    print("\n" + "=" * 100)
    print("SAMPLE TRANSACTIONS FOR TOP UNLINKED DEBIT PATTERNS")
    print("=" * 100)
    
    for vendor, data in sorted_debits[:15]:
        if data['count'] >= 5:
            print(f"\n{vendor} ({data['count']} transactions, ${data['total']:,.2f})")
            print("-" * 100)
            
            for trans in data['transactions'][:5]:
                print(f"  {trans['date']} | ${trans['amount']:>10,.2f} | {trans['description'][:70]}")
            
            if len(data['transactions']) > 5:
                print(f"  ... and {len(data['transactions']) - 5} more")
    
    cur.close()
    conn.close()

def suggest_categories():
    """Suggest potential categories based on patterns."""
    print("\n\n" + "=" * 100)
    print("SUGGESTED CATEGORIES BASED ON PATTERNS")
    print("=" * 100)
    
    suggestions = {
        'utilities': ['FORTIS', 'ENMAX', 'ATCO', 'DIRECT ENERGY', 'EPCOR', 'GAS', 'ELECTRIC', 'WATER'],
        'telecommunications': ['TELUS', 'ROGERS', 'BELL', 'SASKTEL', 'SHAW', 'FREEDOM'],
        'office_rent': ['RENT', 'LANDLORD', 'PROPERTY', 'LEASE'],
        'vehicle_maintenance': ['TIRE', 'OIL CHANGE', 'REPAIR', 'AUTO', 'JIFFY', 'MIDAS', 'CANADIAN TIRE'],
        'fuel': ['SHELL', 'ESSO', 'PETRO', 'HUSKY', 'CENTEX', 'FAS GAS', 'CO-OP', 'CHEVRON'],
        'banking_fees': ['FEE', 'SERVICE CHARGE', 'NSF', 'OVERDRAFT', 'MONTHLY FEE'],
        'insurance': ['INSURANCE', 'SGI', 'AVIVA', 'JEVCO', 'INTACT'],
        'professional_services': ['LAWYER', 'ACCOUNTANT', 'CONSULTANT', 'LEGAL', 'BOOKKEEP'],
        'office_supplies': ['STAPLES', 'OFFICE DEPOT', 'SUPPLIES'],
        'advertising': ['GOOGLE', 'FACEBOOK', 'ADVERTISING', 'MARKETING', 'PRINT'],
        'subscriptions': ['SUBSCRIPTION', 'MONTHLY', 'SOFTWARE', 'LICENSE'],
        'vehicle_registration': ['REGISTRY', 'REGISTRATION', 'PLATE', 'LICENSE']
    }
    
    print("\nPattern-based category suggestions:")
    print("(Review transaction samples above to verify these make sense)\n")
    
    for category, keywords in suggestions.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        print(f"  Keywords: {', '.join(keywords)}")
        print(f"  Suggested for: Transactions containing these terms in description/vendor")
    
    print("\n" + "=" * 100)
    print("NEXT STEPS:")
    print("=" * 100)
    print("1. Review the pattern analysis above")
    print("2. Identify which vendors/patterns should be categorized")
    print("3. Create categorization rules similar to categorize_etransfer_by_name.py")
    print("4. Apply categories to e-transfers, receipts, and banking transactions")
    print("=" * 100)

if __name__ == "__main__":
    try:
        analyze_uncategorized_etransfers()
        analyze_receipt_patterns()
        analyze_banking_debit_patterns()
        suggest_categories()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
