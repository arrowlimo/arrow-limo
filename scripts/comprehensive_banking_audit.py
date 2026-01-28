#!/usr/bin/env python3
"""Comprehensive banking audit: balances, receipts, recurring payments."""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("="*100)
print("COMPREHENSIVE BANKING AUDIT - December 5, 2025")
print("="*100)

# ============================================================================
# PART 1: BANKING BALANCE VERIFICATION
# ============================================================================
print("\n" + "="*100)
print("PART 1: BANKING BALANCE CONFIRMATION")
print("="*100)

# Check CIBC account balances
print("\n1️⃣ CIBC CHECKING (Account 0228362):")
print("-"*100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as transactions,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '0228362'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year DESC
""")

for row in cur.fetchall():
    year, txns, debits, credits, first, last = row
    print(f"  {year}: {txns:5} transactions | Debits: ${debits:>12,.2f} | Credits: ${credits:>12,.2f}")
    print(f"         Range: {first} to {last}")

# Check Scotia account balances
print("\n2️⃣ SCOTIA BANK (Account 903990106011):")
print("-"*100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as transactions,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '903990106011'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year DESC
""")

scotias = cur.fetchall()
if scotias:
    for row in scotias:
        year, txns, debits, credits, first, last = row
        print(f"  {year}: {txns:5} transactions | Debits: ${debits:>12,.2f} | Credits: ${credits:>12,.2f}")
        print(f"         Range: {first} to {last}")
else:
    print("  No Scotia transactions found")

# ============================================================================
# PART 2: UNMATCHED RECEIPTS STATUS
# ============================================================================
print("\n" + "="*100)
print("PART 2: RECEIPTS-BANKING MATCHING STATUS")
print("="*100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM r.receipt_date) as year,
        COUNT(DISTINCT r.receipt_id) as total_receipts,
        COUNT(DISTINCT CASE WHEN bm.receipt_id IS NOT NULL THEN r.receipt_id END) as matched,
        COUNT(DISTINCT CASE WHEN bm.receipt_id IS NULL THEN r.receipt_id END) as unmatched,
        ROUND(100.0 * COUNT(DISTINCT CASE WHEN bm.receipt_id IS NOT NULL THEN r.receipt_id END) / 
              COUNT(DISTINCT r.receipt_id), 1) as match_percent,
        SUM(r.gross_amount) as total_amount,
        SUM(CASE WHEN bm.receipt_id IS NOT NULL THEN r.gross_amount ELSE 0 END) as matched_amount
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
    WHERE r.gross_amount > 0
    GROUP BY EXTRACT(YEAR FROM r.receipt_date)
    ORDER BY year DESC
""")

print("\nReceipt-Banking Match Summary (by year):")
print("-"*100)
for row in cur.fetchall():
    year, total, matched, unmatched, pct, total_amt, matched_amt = row
    if year:
        print(f"  {int(year):4}: {total:5} total | {matched:5} matched ({pct:5.1f}%) | {unmatched:5} unmatched")
        print(f"        ${total_amt:>12,.2f} total | ${matched_amt:>12,.2f} matched")

# ============================================================================
# PART 3: MISSING RECURRING PAYMENTS AUDIT
# ============================================================================
print("\n" + "="*100)
print("PART 3: MISSING RECURRING PAYMENT CATEGORIES")
print("="*100)

# Define what we're looking for
recurring_patterns = {
    'RENT': ['RENT', 'LANDLORD', 'PROPERTY MANAGEMENT'],
    'LEASE': ['LEASE', 'LEASING', 'HEFFNER'],
    'PHONE/INTERNET/WEB': ['TELUS', 'ROGERS', 'BELL', 'SASKTEL', 'PHONE', 'INTERNET', 'CELLULAR', 'ISP', 'WIRELESS'],
    'WEB HOSTING': ['GODADDY', 'IONOS', 'WIX', 'HOSTING', 'DOMAIN', 'NAMESERVER'],
    'UTILITIES': ['POWER', 'ELECTRIC', 'GAS', 'WATER', 'SEWER', 'WASTE', 'GARBAGE'],
    'INSURANCE': ['INSURANCE', 'SGI', 'AVIVA', 'JEVCO', 'POLICY'],
    'BANKING': ['BANK', 'FEE', 'SERVICE CHARGE', 'NSF', 'OVERDRAFT'],
}

print("\nSearching for recurring monthly/quarterly/annual payments:\n")

for category, keywords in recurring_patterns.items():
    keywords_clause = ' OR '.join([f"description ILIKE '%{kw}%'" for kw in keywords])
    
    cur.execute(f"""
        SELECT 
            COUNT(*) as total_count,
            COUNT(DISTINCT EXTRACT(MONTH FROM receipt_date)) as unique_months,
            COUNT(DISTINCT EXTRACT(YEAR FROM receipt_date)) as unique_years,
            SUM(gross_amount) as total_amount,
            AVG(gross_amount) as avg_amount,
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest
        FROM receipts
        WHERE ({keywords_clause})
    """)
    
    result = cur.fetchone()
    if result:
        count, months, years, total, avg, earliest, latest = result
        if count and count > 0:
            print(f"✅ {category:25} | {count:4} receipts | ${total:>10,.2f} | Avg: ${avg:>8,.2f}")
            print(f"   Period: {earliest} to {latest}")
        else:
            print(f"❌ {category:25} | ZERO RECEIPTS FOUND")
    else:
        print(f"❌ {category:25} | ZERO RECEIPTS FOUND")

# ============================================================================
# PART 4: DETAILED SEARCH FOR SPECIFIC MISSING ITEMS
# ============================================================================
print("\n" + "="*100)
print("PART 4: DEEP DIVE - SPECIFIC PAYMENT SEARCHES")
print("="*100)

specific_searches = {
    'GODADDY': "GoDaddy domain/hosting",
    'IONOS': "IONOS hosting",
    'WIX': "Wix website builder",
    'GODADDY|IONOS|WIX': "Any web hosting (combined)",
}

for search_term, description in specific_searches.items():
    cur.execute("""
        SELECT 
            COUNT(*) as cnt,
            SUM(gross_amount) as total
        FROM receipts
        WHERE description ILIKE %s OR vendor_name ILIKE %s
    """, (f'%{search_term}%', f'%{search_term}%'))
    
    result = cur.fetchone()
    if result:
        cnt, total = result
        status = "✅ FOUND" if cnt and cnt > 0 else "❌ MISSING"
        print(f"{status}: {description:35} | {cnt:3} receipts | ${total if total else 0:>10,.2f}")

# ============================================================================
# PART 5: MONTHLY PAYMENT AUDIT (Find patterns)
# ============================================================================
print("\n" + "="*100)
print("PART 5: MONTHLY RECURRING PAYMENT PATTERNS")
print("="*100)

print("\nTop vendors with 'monthly' or regular payment patterns:")
print("-"*100)

cur.execute("""
    SELECT 
        COALESCE(canonical_vendor, vendor_name) as vendor,
        COUNT(*) as transactions,
        SUM(gross_amount) as total,
        ROUND(SUM(gross_amount) / COUNT(*), 2) as avg_amount,
        MIN(receipt_date) as first_date,
        MAX(receipt_date) as last_date
    FROM receipts
    WHERE gross_amount > 0
    GROUP BY COALESCE(canonical_vendor, vendor_name)
    HAVING COUNT(*) >= 5
    ORDER BY total DESC
    LIMIT 30
""")

for row in cur.fetchall():
    vendor, txns, total, avg, first, last = row
    if vendor:
        print(f"  {vendor:35} | {txns:3} txns | ${total:>10,.2f} | Avg: ${avg:>8,.2f}")
        print(f"     {first} → {last}")

# ============================================================================
# PART 6: MISSING PHONE/INTERNET/WEB HOSTING - EXHAUSTIVE SEARCH
# ============================================================================
print("\n" + "="*100)
print("PART 6: EXHAUSTIVE SEARCH - PHONE/INTERNET/WEB HOSTING")
print("="*100)

search_terms = [
    ('TELUS', 'Telus phone/internet'),
    ('ROGERS', 'Rogers telecom'),
    ('BELL', 'Bell Canada'),
    ('SASKTEL', 'SaskTel'),
    ('GODADDY', 'GoDaddy'),
    ('IONOS', 'IONOS'),
    ('WIX', 'Wix'),
    ('DOMAIN', 'Domain registration'),
    ('HOSTING', 'Web hosting'),
    ('PHONE', 'Phone-related'),
    ('INTERNET', 'Internet service'),
    ('CELLULAR', 'Cellular service'),
    ('ISP', 'Internet service provider'),
    ('NAMESERVER', 'DNS/Nameserver'),
]

print("\nExhaustive vendor search:")
print("-"*100)

for term, label in search_terms:
    cur.execute("""
        SELECT 
            COALESCE(canonical_vendor, vendor_name) as vendor,
            COUNT(*) as cnt,
            SUM(gross_amount) as total,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE description ILIKE %s 
        OR vendor_name ILIKE %s
        GROUP BY COALESCE(canonical_vendor, vendor_name)
        ORDER BY total DESC
    """, (f'%{term}%', f'%{term}%'))
    
    results = cur.fetchall()
    if results:
        print(f"\n🔍 {label} ({term}):")
        for row in results:
            vendor, cnt, total, first, last = row
            print(f"   {vendor:40} | {cnt:3} | ${total:>10,.2f} | {first} to {last}")
    else:
        print(f"\n❌ {label} ({term}): NO RECORDS FOUND")

# ============================================================================
# PART 7: SUMMARY & RECOMMENDATIONS
# ============================================================================
print("\n" + "="*100)
print("PART 7: AUDIT SUMMARY & RECOMMENDATIONS")
print("="*100)

cur.execute("""
    SELECT 
        COUNT(DISTINCT receipt_id) as total_receipts,
        SUM(gross_amount) as total_amount,
        COUNT(DISTINCT CASE WHEN created_from_banking = TRUE THEN receipt_id END) as auto_created,
        COUNT(DISTINCT CASE WHEN created_from_banking = FALSE THEN receipt_id END) as manually_entered
    FROM receipts
""")

total_receipts, total_amount, auto_created, manual_entered = cur.fetchone()

print(f"\nReceipt Database Status:")
print(f"  Total receipts: {total_receipts:,}")
print(f"  Total amount: ${total_amount:,.2f}")
print(f"  Auto-created from banking: {auto_created:,}")
print(f"  Manually entered: {manual_entered:,}")

print(f"\nNext Steps:")
print(f"  1. ✅ Run Part 4-6 results to identify MISSING recurring payments")
print(f"  2. ✅ Cross-reference against known vendor list")
print(f"  3. ✅ Check if these payments are in banking but not receipts")
print(f"  4. ✅ Add missing receipts for identified categories")

conn.close()
print("\n" + "="*100)
print("AUDIT COMPLETE")
print("="*100)
