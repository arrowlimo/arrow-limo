#!/usr/bin/env python3
"""
Analyze 2019 receipts for potential duplicates and banking reconciliation issues.
Groups by date/amount/vendor and checks for:
- Duplicate entries (same day, same amount, same vendor)
- Fuel purchases with same amount (check vehicle_id differences)
- Cash vs banking payment method verification needs
- E-transfer patterns requiring description cleanup
"""

import psycopg2
import csv
from datetime import datetime, timedelta
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def find_duplicate_groups():
    """Find receipts with same date/amount/vendor - potential duplicates."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            receipt_date, 
            COALESCE(canonical_vendor, vendor_name) AS vendor,
            gross_amount,
            category,
            COUNT(*) AS cnt,
            array_agg(receipt_id ORDER BY receipt_id) AS receipt_ids,
            array_agg(vehicle_id) AS vehicle_ids,
            array_agg(payment_method) AS pay_methods,
            array_agg(created_from_banking) AS from_banking,
            array_agg(description) AS descriptions
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
        GROUP BY receipt_date, COALESCE(canonical_vendor, vendor_name), gross_amount, category
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, gross_amount DESC, receipt_date
    """)
    
    duplicates = cur.fetchall()
    cur.close()
    conn.close()
    
    return duplicates

def analyze_banking_etransfers():
    """Analyze E-transfer patterns that need vendor normalization."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find E-transfer transactions from banking
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND (
            description ILIKE '%e-transfer%'
            OR description ILIKE '%etransfer%'
        )
        ORDER BY transaction_date, ABS(COALESCE(debit_amount, credit_amount)) DESC
    """)
    
    etransfers = cur.fetchall()
    cur.close()
    conn.close()
    
    return etransfers

def categorize_etransfer(description, amount):
    """Categorize E-transfer based on description and amount patterns."""
    desc_upper = description.upper()
    
    # David Richard patterns
    if 'DAVID RICH' in desc_upper or 'DAVID RICHARD' in desc_upper:
        return 'shareholder_loan', 'David Richard'
    
    # Float amounts (round numbers 100, 200, etc)
    if amount in [100, 200, 300, 400, 500] and amount <= 500:
        return 'driver_float', 'Driver Float'
    
    # Non-refundable deposits (typically 500 or variants for smaller vehicles)
    if amount == 500 or (amount > 400 and amount < 600):
        return 'non_refundable_deposit', 'Non-Refundable Deposit'
    
    # Look for driver names (would need employee list to match)
    # For now, flag as needing review
    return 'needs_review', 'E-Transfer Needs Classification'

def check_banking_matches(year=2019):
    """Check which receipts are matched to banking within ±3-4 days."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get receipts with their banking links
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.canonical_vendor,
            r.gross_amount,
            r.payment_method,
            r.created_from_banking,
            r.banking_transaction_id,
            bt.transaction_date,
            bt.description,
            ABS((r.receipt_date - bt.transaction_date)) AS days_diff
        FROM receipts r
        LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE EXTRACT(YEAR FROM r.receipt_date) = %s
        AND r.payment_method NOT IN ('Cash', 'cash')
        ORDER BY r.receipt_date, r.gross_amount DESC
    """, (year,))
    
    matches = cur.fetchall()
    cur.close()
    conn.close()
    
    return matches

def main():
    print("="*80)
    print("2019 RECEIPTS DUPLICATE & BANKING ANALYSIS")
    print("="*80)
    
    # 1. Find potential duplicates
    print("\n1. POTENTIAL DUPLICATES (Same Date/Amount/Vendor)")
    print("-"*80)
    duplicates = find_duplicate_groups()
    
    fuel_same_amount = []
    likely_duplicates = []
    needs_manual_check = []
    
    for dup in duplicates[:50]:  # Top 50 duplicate groups
        date, vendor, amount, category, cnt, ids, vehicles, pays, from_bank, descs = dup
        
        # Check if it's fuel with same amount
        is_fuel = category and 'fuel' in category.lower()
        different_vehicles = len(set([v for v in vehicles if v])) > 1
        has_cash = 'Cash' in pays or 'cash' in pays
        
        if is_fuel and different_vehicles:
            fuel_same_amount.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'count': cnt,
                'vehicles': vehicles,
                'status': '✅ OK - Different vehicles'
            })
        elif has_cash:
            needs_manual_check.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'count': cnt,
                'payment_methods': pays,
                'status': '⚠️ NEEDS MANUAL - Cash payment'
            })
        else:
            likely_duplicates.append({
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'count': cnt,
                'receipt_ids': ids,
                'from_banking': from_bank,
                'status': '❌ LIKELY DUPLICATE'
            })
    
    print(f"\nFuel - Same Amount, Different Vehicles (OK): {len(fuel_same_amount)}")
    for item in fuel_same_amount[:10]:
        print(f"  {item['date']} | {item['vendor']} | ${item['amount']:.2f} | {item['status']}")
    
    print(f"\nCash Payments Needing Manual Verification: {len(needs_manual_check)}")
    for item in needs_manual_check[:10]:
        print(f"  {item['date']} | {item['vendor']} | ${item['amount']:.2f} | {item['status']}")
    
    print(f"\nLikely Duplicates (QuickBooks or Import Issues): {len(likely_duplicates)}")
    for item in likely_duplicates[:20]:
        print(f"  {item['date']} | {item['vendor']} | ${item['amount']:.2f} | IDs: {item['receipt_ids']}")
    
    # 2. E-transfer analysis
    print("\n\n2. E-TRANSFER PATTERN ANALYSIS")
    print("-"*80)
    etransfers = analyze_banking_etransfers()
    
    etransfer_categories = defaultdict(list)
    
    for txn_id, date, desc, debit, credit, vendor in etransfers:
        amount = abs(debit or credit or 0)
        category, suggested_vendor = categorize_etransfer(desc, amount)
        
        etransfer_categories[category].append({
            'date': date,
            'description': desc[:60],
            'amount': amount,
            'suggested_vendor': suggested_vendor
        })
    
    for category, items in etransfer_categories.items():
        print(f"\n{category.upper().replace('_', ' ')}: {len(items)} transactions")
        for item in items[:5]:
            print(f"  {item['date']} | ${item['amount']:,.2f} | {item['description']} → {item['suggested_vendor']}")
    
    # 3. Banking match coverage
    print("\n\n3. BANKING MATCH COVERAGE (±3-4 days)")
    print("-"*80)
    matches = check_banking_matches(2019)
    
    matched_within_3 = sum(1 for m in matches if m[7] and m[10] and m[10] <= 3)
    matched_within_4 = sum(1 for m in matches if m[7] and m[10] and m[10] <= 4)
    unmatched = sum(1 for m in matches if not m[7])
    total_non_cash = len(matches)
    
    print(f"\nTotal non-cash receipts: {total_non_cash}")
    print(f"Matched within 3 days: {matched_within_3} ({matched_within_3/total_non_cash*100:.1f}%)")
    print(f"Matched within 4 days: {matched_within_4} ({matched_within_4/total_non_cash*100:.1f}%)")
    print(f"Unmatched: {unmatched} ({unmatched/total_non_cash*100:.1f}%)")
    
    # Show sample unmatched
    print("\nSample Unmatched Non-Cash Receipts:")
    unmatched_items = [m for m in matches if not m[7]]
    for item in unmatched_items[:15]:
        rid, rdate, vname, canonical, amount, payment, from_bank, *_ = item
        print(f"  ID:{rid} | {rdate} | {canonical or vname} | ${amount:.2f} | {payment}")
    
    # 4. Export findings
    print("\n\n4. EXPORTING FINDINGS TO CSV")
    print("-"*80)
    
    with open('l:/limo/data/2019_duplicate_analysis.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Type', 'Date', 'Vendor', 'Amount', 'Count', 'IDs', 'Status', 'Notes'])
        
        for item in fuel_same_amount:
            writer.writerow(['Fuel-Multi-Vehicle', item['date'], item['vendor'], 
                           item['amount'], item['count'], '', item['status'], 
                           f"Vehicles: {item['vehicles']}"])
        
        for item in needs_manual_check:
            writer.writerow(['Cash-Manual-Check', item['date'], item['vendor'],
                           item['amount'], item['count'], '', item['status'],
                           f"Payment: {item['payment_methods']}"])
        
        for item in likely_duplicates:
            writer.writerow(['Likely-Duplicate', item['date'], item['vendor'],
                           item['amount'], item['count'], str(item['receipt_ids']),
                           item['status'], f"From banking: {item['from_banking']}"])
    
    print("✅ Exported to: l:/limo/data/2019_duplicate_analysis.csv")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Legitimate multi-vehicle fuel: {len(fuel_same_amount)}")
    print(f"⚠️ Cash payments need manual check: {len(needs_manual_check)}")
    print(f"❌ Likely duplicates to review: {len(likely_duplicates)}")
    print(f"🔍 E-transfers needing classification: {len(etransfer_categories.get('needs_review', []))}")
    print(f"📊 Banking match rate: {matched_within_4/total_non_cash*100:.1f}% (±4 days)")

if __name__ == '__main__':
    main()
