#!/usr/bin/env python3
"""
Extract real vendor names from banking descriptions for generic receipt entries.

Priority fixes:
1. CHEQUE/CHECK PAYMENT → Extract payee from banking description
2. EMAIL TRANSFER/E-TRANSFER → Extract recipient from banking description  
3. POINT OF/PURCHASE/POS → Extract merchant from banking description
4. UNKNOWN PAYEE → Extract from banking description
"""

import psycopg2
import re
import os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("VENDOR NAME EXTRACTION FROM BANKING DESCRIPTIONS")
print("="*80)

# Pattern extractors
def extract_etransfer_recipient(desc):
    """Extract recipient from e-transfer description"""
    # "Internet Banking E-TRANSFER102853469535 Mike Woodrow 4506*********534"
    # "E-TRANSFER105547218481 Vanessa Thomas 4506*********534"
    match = re.search(r'E-TRANSFER\d+\s+([A-Za-z\s]+?)\s+4506', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # "Internet Banking E-TRANSFER 102224816722 Michael Richard"
    match = re.search(r'E-TRANSFER\s+\d+\s+([A-Za-z\s]+?)(?:\s*$|\s+\d)', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def extract_pos_merchant(desc):
    """Extract merchant from Point of Sale description"""
    # "Point of Sale - Interac PURCHASE066001001009 FGP40008 WESTPA 4506*********5"
    match = re.search(r'PURCHASE[A-Z0-9]+\s+(.+?)\s+4506', desc, re.IGNORECASE)
    if match:
        merchant = match.group(1).strip()
        # Clean up merchant codes
        merchant = re.sub(r'^\d+\s+', '', merchant)  # Remove leading numbers
        return merchant
    
    # "Point of Sale - Interac RETAIL PURCHASE 000001311003 ERLES AUTO REPA"
    match = re.search(r'PURCHASE\s+\d+\s+(.+?)(?:\s*$|\s+4506)', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def extract_eft_payee(desc):
    """Extract payee from Electronic Funds Transfer"""
    # "Electronic Funds Transfer INSURANCE 000000000000000 Aurora Premium Financing"
    match = re.search(r'Electronic Funds Transfer\s+\w+\s+\d+\s+(.+?)(?:\s*$)', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # "EFT Debit COMPANY NAME"
    match = re.search(r'EFT\s+(?:Debit|Credit)\s+(.+?)(?:\s*$)', desc, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def extract_cheque_payee(desc):
    """Extract payee from cheque description"""
    # Unfortunately most cheque descriptions are just "CHEQUE 12345678 1"
    # We'd need to cross-reference with cheque_vendor_reference.xlsx
    return None

# Process EMAIL TRANSFER / E-TRANSFER
print("\n1. EMAIL TRANSFER / E-TRANSFER")
print("-"*80)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('EMAIL TRANSFER', 'E-TRANSFER')
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
    LIMIT 10
""")

updates = []
for receipt_id, vendor, desc in cur.fetchall():
    recipient = extract_etransfer_recipient(desc)
    if recipient:
        updates.append((recipient, receipt_id))
        print(f"  Receipt #{receipt_id}: '{vendor}' → '{recipient}'")
        print(f"    From: {desc}")

print(f"\n  Found {len(updates)} e-transfer recipients to update")

# Process POINT OF / PURCHASE / POS
print("\n2. POINT OF SALE / PURCHASE")
print("-"*80)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('POINT OF', 'PURCHASE', 'POS')
      AND r.exclude_from_reports = FALSE
      AND bt.description LIKE '%Point of Sale%'
    LIMIT 10
""")

pos_updates = []
for receipt_id, vendor, desc in cur.fetchall():
    merchant = extract_pos_merchant(desc)
    if merchant:
        pos_updates.append((merchant, receipt_id))
        print(f"  Receipt #{receipt_id}: '{vendor}' → '{merchant}'")
        print(f"    From: {desc}")

print(f"\n  Found {len(pos_updates)} POS merchants to update")

# Process UNKNOWN PAYEE
print("\n3. UNKNOWN PAYEE (CHEQUE)")
print("-"*80)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE '%UNKNOWN%'
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
    LIMIT 10
""")

unknown_updates = []
for receipt_id, vendor, desc in cur.fetchall():
    # Try all extractors
    payee = extract_etransfer_recipient(desc) or extract_pos_merchant(desc) or extract_eft_payee(desc)
    if payee:
        unknown_updates.append((payee, receipt_id))
        print(f"  Receipt #{receipt_id}: '{vendor}' → '{payee}'")
        print(f"    From: {desc}")

print(f"\n  Found {len(unknown_updates)} unknown payees to update")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

all_updates = updates + pos_updates + unknown_updates

print(f"\nTotal vendor name extractions: {len(all_updates)}")
print(f"  E-transfers: {len(updates)}")
print(f"  POS purchases: {len(pos_updates)}")
print(f"  Unknown payees: {len(unknown_updates)}")

if all_updates:
    print(f"\nWould update {len(all_updates)} receipts")
    print("\nRun full extraction? This will:")
    print("  1. Extract all vendor names from banking descriptions")
    print("  2. Update receipts.vendor_name")
    print("  3. Standardize vendor names using vendor_standardization table")
    print("  4. Update receipts.canonical_vendor")
else:
    print("\n❌ No extractions found - patterns may need adjustment")

cur.close()
conn.close()
