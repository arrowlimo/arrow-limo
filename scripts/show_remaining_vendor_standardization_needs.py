#!/usr/bin/env python3
"""
Show remaining vendor groups that need standardization.
Focus on patterns where names are truncated or have embedded codes/IDs.
"""

import psycopg2
from collections import defaultdict
import re

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("VENDOR GROUPS NEEDING STANDARDIZATION")
print("=" * 80)

cur = conn.cursor()

# Define vendor patterns to standardize
standardization_groups = []

# 1. ATM/ABM WITHDRAWALS
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE '%ABM WITHDRAWAL%'
       OR vendor_name LIKE '%ATM WITHDRAWAL%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
atm_vendors = cur.fetchall()
if atm_vendors:
    total = sum(count for _, count in atm_vendors)
    standardization_groups.append({
        'name': 'ATM/ABM WITHDRAWALS',
        'count': total,
        'variations': len(atm_vendors),
        'target': 'ATM WITHDRAWAL',
        'samples': atm_vendors[:5]
    })

# 2. POINT OF SALE - INTERAC
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE 'POINT OF SALE - INTERAC%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
interac_vendors = cur.fetchall()
if interac_vendors:
    total = sum(count for _, count in interac_vendors)
    standardization_groups.append({
        'name': 'POINT OF SALE - INTERAC',
        'count': total,
        'variations': len(interac_vendors),
        'target': 'Extract actual vendor from embedded transaction ID',
        'samples': interac_vendors[:5]
    })

# 3. POINT OF SALE - VISA DEBIT
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE 'POINT OF SALE - VISA DEBIT%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
visa_vendors = cur.fetchall()
if visa_vendors:
    total = sum(count for _, count in visa_vendors)
    standardization_groups.append({
        'name': 'POINT OF SALE - VISA DEBIT',
        'count': total,
        'variations': len(visa_vendors),
        'target': 'Extract actual vendor from embedded transaction ID',
        'samples': visa_vendors[:5]
    })

# 4. EMAIL TRANSFER variations
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE '%EMAIL TRANSFER%'
       OR vendor_name LIKE '%E-TRANSFER%'
       OR vendor_name LIKE '%ETRANSFER%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
email_vendors = cur.fetchall()
if len(email_vendors) > 1:
    total = sum(count for _, count in email_vendors)
    standardization_groups.append({
        'name': 'EMAIL TRANSFERS',
        'count': total,
        'variations': len(email_vendors),
        'target': 'EMAIL TRANSFER',
        'samples': email_vendors
    })

# 5. INTERNET BANKING variations
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE 'INTERNET BANKING%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
internet_banking = cur.fetchall()
if internet_banking:
    total = sum(count for _, count in internet_banking)
    standardization_groups.append({
        'name': 'INTERNET BANKING',
        'count': total,
        'variations': len(internet_banking),
        'target': 'Extract actual payee/vendor',
        'samples': internet_banking[:5]
    })

# 6. CHECK PAYMENTS
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE 'CHQ %'
       OR vendor_name LIKE 'CHECK %'
       OR vendor_name LIKE 'CHEQUE %'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
check_vendors = cur.fetchall()
if len(check_vendors) > 1:
    total = sum(count for _, count in check_vendors)
    standardization_groups.append({
        'name': 'CHECK PAYMENTS',
        'count': total,
        'variations': len(check_vendors),
        'target': 'CHECK PAYMENT (remove check numbers)',
        'samples': check_vendors
    })

# 7. BRANCH TRANSACTION variations
cur.execute("""
    SELECT vendor_name, COUNT(*) 
    FROM receipts
    WHERE vendor_name LIKE 'BRANCH TRANSACTION%'
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")
branch_vendors = cur.fetchall()
if branch_vendors:
    total = sum(count for _, count in branch_vendors)
    standardization_groups.append({
        'name': 'BRANCH TRANSACTIONS',
        'count': total,
        'variations': len(branch_vendors),
        'target': 'Standardize by transaction type',
        'samples': branch_vendors[:5]
    })

# 8. Service providers with transaction IDs (recurring)
service_patterns = [
    ('APPLE', 'APL%ITUNES%'),
    ('SHAW CABLE', 'SHAW CABLESYSTE%'),
    ('GOOGLE G SUITE', 'GOOGLE%GSUITE%'),
    ('ROGERS', 'ROGERS%'),
    ('TELUS', 'TELUS%'),
    ('AMAZON', 'AMAZON%'),
]

for service_name, pattern in service_patterns:
    cur.execute("""
        SELECT vendor_name, COUNT(*) 
        FROM receipts
        WHERE vendor_name LIKE %s
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
    """, (pattern,))
    vendors = cur.fetchall()
    if len(vendors) > 1:
        total = sum(count for _, count in vendors)
        standardization_groups.append({
            'name': service_name,
            'count': total,
            'variations': len(vendors),
            'target': service_name,
            'samples': vendors[:3]
        })

# Display results
print("\nGROUPS REQUIRING STANDARDIZATION:\n")
print("=" * 80)

for i, group in enumerate(sorted(standardization_groups, key=lambda x: x['count'], reverse=True), 1):
    print(f"\n{i}. {group['name']}")
    print(f"   Total receipts: {group['count']:,}")
    print(f"   Variations: {group['variations']:,}")
    print(f"   Target: {group['target']}")
    print(f"\n   Sample variations:")
    for vendor, count in group['samples']:
        print(f"      '{vendor}' ({count})")

# Summary
print("\n" + "=" * 80)
print("PRIORITY RECOMMENDATIONS")
print("=" * 80)

print("\n1. HIGH PRIORITY (4,000+ receipts):")
print("   - Point of Sale transactions: Extract actual vendor names")
print("     Remove transaction IDs, keep meaningful vendor")

print("\n2. MEDIUM PRIORITY (1,000+ receipts):")
print("   - ATM/ABM withdrawals: Standardize to 'ATM WITHDRAWAL'")
print("     Remove location codes and card numbers")

print("\n3. LOW PRIORITY (<100 receipts):")
print("   - Email transfers: Standardize to 'EMAIL TRANSFER'")
print("   - Check payments: Standardize to 'CHECK PAYMENT'")
print("   - Service providers: Remove transaction IDs")

print("\n4. SPECIAL HANDLING:")
print("   - Internet Banking: Extract actual payee from bill payment details")
print("   - Branch Transactions: Keep type, remove transaction numbers")

total_affected = sum(g['count'] for g in standardization_groups)
print(f"\n📊 TOTAL RECEIPTS AFFECTED: {total_affected:,}")

cur.close()
conn.close()
