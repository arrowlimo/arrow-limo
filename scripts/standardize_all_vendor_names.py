#!/usr/bin/env python3
"""
Comprehensive vendor name standardization:
1. ATM/ABM withdrawals → CASH WITHDRAWAL
2. Email transfers → EMAIL TRANSFER or EMAIL TRANSFER FEE
3. Point of Sale → Extract actual vendor (ITUNES, NATIONAL MONEY MART, etc.)
4. Check payments → CHECK PAYMENT
5. Branch transactions → Standardize by type
"""

import psycopg2
import re
from collections import defaultdict

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

print("=" * 80)
print("COMPREHENSIVE VENDOR NAME STANDARDIZATION")
print("=" * 80)

def standardize_vendor_name(vendor):
    """Apply standardization rules to vendor name."""
    if not vendor:
        return vendor
    
    original = vendor
    
    # 1. ATM/ABM WITHDRAWALS → CASH WITHDRAWAL
    if 'ABM WITHDRAWAL' in vendor or 'ATM WITHDRAWAL' in vendor:
        return 'CASH WITHDRAWAL'
    
    # 2. EMAIL TRANSFER FEE (keep as is)
    if vendor == 'EMAIL TRANSFER FEE':
        return 'EMAIL TRANSFER FEE'
    
    # 3. EMAIL TRANSFER (already standardized)
    if vendor == 'EMAIL TRANSFER':
        return 'EMAIL TRANSFER'
    
    # 4. CHECK PAYMENTS
    if vendor.startswith('CHQ ') or vendor.startswith('CHECK ') or vendor.startswith('CHEQUE '):
        return 'CHECK PAYMENT'
    
    # 5. POINT OF SALE - Extract vendor name
    if vendor.startswith('POINT OF SALE'):
        # Extract actual vendor name from transaction
        
        # iTunes
        if 'ITUNES' in vendor or 'APL*ITUNES' in vendor or 'APL* ITUNES' in vendor:
            return 'ITUNES'
        
        # National Money Mart
        if 'NATIONAL MONEYM' in vendor or 'NATIONAL MONEY' in vendor:
            return 'NATIONAL MONEY MART'
        
        # Shaw Cable
        if 'SHAW' in vendor:
            return 'SHAW CABLE'
        
        # Google G Suite
        if 'GOOGLE' in vendor and ('GSUITE' in vendor or 'G SUITE' in vendor):
            return 'GOOGLE WORKSPACE'
        
        # Rogers
        if 'ROGERS' in vendor:
            return 'ROGERS'
        
        # Telus
        if 'TELUS' in vendor:
            return 'TELUS'
        
        # Amazon
        if 'AMAZON' in vendor:
            return 'AMAZON'
        
        # Microsoft
        if 'MICROSOFT' in vendor:
            return 'MICROSOFT'
        
        # Fibrenew
        if 'FIBRENEW' in vendor or 'FIBRE NEW' in vendor:
            return 'FIBRENEW'
        
        # Red Deer Films
        if 'RED DEER FILMS' in vendor:
            return 'RED DEER FILMS'
        
        # Sobeys
        if 'SOBEYS' in vendor:
            return 'SOBEYS'
        
        # Superstore
        if 'SUPERSTORE' in vendor or 'SUPER STORE' in vendor:
            return 'SUPERSTORE'
        
        # Walmart
        if 'WAL-MART' in vendor or 'WALMART' in vendor:
            return 'WALMART'
        
        # 7-Eleven
        if '7-ELEVEN' in vendor or '7 ELEVEN' in vendor or '7ELEVEN' in vendor:
            return '7-ELEVEN'
        
        # Plenty of Liquor
        if 'PLENTY OF LIQUO' in vendor or 'PLENTY OF LIQUOR' in vendor:
            return 'PLENTY OF LIQUOR'
        
        # Clearview
        if 'CLEARVIEW' in vendor or 'CLEARVIE' in vendor:
            return 'CLEARVIEW'
        
        # Bird Rides
        if 'BIRD RIDES' in vendor:
            return 'BIRD RIDES'
        
        # CFIB
        if 'CFIB' in vendor or 'FCEI' in vendor:
            return 'CFIB'
        
        # Edmonton KOA
        if 'EDMONTONKOA' in vendor or 'EDMONTON KOA' in vendor:
            return 'EDMONTON KOA'
        
        # Prime Video
        if 'PRIMEVIDEO' in vendor or 'PRIME VIDEO' in vendor:
            return 'PRIME VIDEO'
        
        # Cineplex
        if 'CINEPLEX' in vendor or 'CINEPLE' in vendor:
            return 'CINEPLEX'
        
        # Generic fallback - try to extract vendor from pattern
        # Pattern: POINT OF SALE - INTERAC PURCHASE[numbers] VENDOR [card]
        match = re.search(r'PURCHASE\d+\s+([A-Z\*\s]+?)\s+\d{4}\*', vendor)
        if match:
            vendor_name = match.group(1).strip()
            # Clean up
            vendor_name = vendor_name.replace('SQ *', '').strip()
            if len(vendor_name) > 3:  # Valid vendor name
                return vendor_name
        
        # Pattern: RETAIL PURCHASE VENDOR [numbers]
        match = re.search(r'RETAIL PURCHASE\s+([A-Z\*\s\-\.]+?)\s+\d{6,}', vendor)
        if match:
            vendor_name = match.group(1).strip()
            if len(vendor_name) > 3:
                return vendor_name
    
    # 6. INTERNET BANKING - Extract payee
    if vendor.startswith('INTERNET BANKING'):
        # Extract payee name
        # Pattern: INTERNET BILL PAY/PMT [numbers] PAYEE
        match = re.search(r'(?:PAY|PMT)\s*\d+\s+([A-Z\s\-]+?)(?:\s+\d{4}\*|\s*$)', vendor)
        if match:
            payee = match.group(1).strip()
            if len(payee) > 3:
                return payee
    
    # 7. BRANCH TRANSACTION - Standardize by type
    if vendor.startswith('BRANCH TRANSACTION'):
        if 'WITHDRAWAL' in vendor:
            return 'CASH WITHDRAWAL'
        if 'ACC FEE' in vendor:
            return 'BANK SERVICE FEE'
        if 'OVERDRAFT INTEREST' in vendor:
            return 'OVERDRAFT INTEREST'
        if 'OVERDRAFT S/C' in vendor:
            return 'OVERDRAFT FEE'
        if 'DEPOSIT NOTE FEE' in vendor:
            return 'DEPOSIT FEE'
    
    return original

# Preview changes
cur = conn.cursor()

print("\nAnalyzing receipts for standardization...\n")

cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    HAVING COUNT(*) > 0
    ORDER BY COUNT(*) DESC
""")

changes = defaultdict(list)
total_receipts = 0

for vendor, count in cur.fetchall():
    standardized = standardize_vendor_name(vendor)
    if standardized != vendor:
        changes[standardized].append((vendor, count))
        total_receipts += count

print(f"Found {len(changes)} standardized vendor names affecting {total_receipts:,} receipts\n")
print("=" * 80)
print("PREVIEW OF CHANGES (Top 20 by impact)")
print("=" * 80)

# Sort by total impact
change_summary = []
for new_name, variations in changes.items():
    total = sum(count for _, count in variations)
    change_summary.append((new_name, variations, total))

change_summary.sort(key=lambda x: x[2], reverse=True)

for i, (new_name, variations, total) in enumerate(change_summary[:20], 1):
    print(f"\n{i}. → '{new_name}' ({total:,} receipts from {len(variations)} variations)")
    for old_name, count in sorted(variations, key=lambda x: x[1], reverse=True)[:3]:
        print(f"      '{old_name[:70]}...' ({count})" if len(old_name) > 70 else f"      '{old_name}' ({count})")
    if len(variations) > 3:
        print(f"      ... and {len(variations) - 3} more variations")

print("\n" + "=" * 80)
print(f"Total receipts to update: {total_receipts:,}")
print("=" * 80)

confirm = input("\nProceed with standardization? (yes/no): ").strip().lower()

if confirm == 'yes':
    print("\n📝 Applying vendor name standardization...")
    
    # Re-fetch all vendors to standardize
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IS NOT NULL
        GROUP BY vendor_name
    """)
    
    all_vendors = cur.fetchall()
    updated_count = 0
    
    for vendor, count in all_vendors:
        standardized = standardize_vendor_name(vendor)
        if standardized != vendor:
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s
                WHERE vendor_name = %s
            """, (standardized, vendor))
            updated_count += cur.rowcount
    
    print(f"   Updated {updated_count:,} receipts")
    
    print("\n💾 Committing changes...")
    conn.commit()
    
    print("\n✅ STANDARDIZATION COMPLETE")
    
    # Show summary
    print("\nTop standardized vendors:")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    for vendor, count in cur.fetchall():
        print(f"  {vendor}: {count:,}")
    
else:
    print("\n❌ Standardization cancelled")

cur.close()
conn.close()
