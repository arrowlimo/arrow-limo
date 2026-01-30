import psycopg2
import re
from datetime import datetime

# DRY RUN by default - set to True to apply changes
DRY_RUN = False

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

if not DRY_RUN:
    # Create backup using SQL export
    backup_file = f"l:/limo/receipts_vendor_backup_{timestamp}.csv"
    print(f"Creating backup: {backup_file}")
    
    with open(backup_file, 'w', encoding='utf-8', newline='') as f:
        cur.copy_expert("""
            COPY (SELECT * FROM receipts WHERE exclude_from_reports = FALSE) 
            TO STDOUT WITH CSV HEADER
        """, f)
    
    print(f"✅ Backup created ({backup_file})\n")

print("VENDOR NAME EXTRACTION AND CLEANUP")
print("="*100)
print(f"MODE: {'DRY RUN (no changes)' if DRY_RUN else '🔥 LIVE - MAKING CHANGES 🔥'}")
print("="*100)

# FGP Merchant code table
FGP_MERCHANTS = {
    'RUN': "RUN'N ON EMPTY",
    'WESTPA': 'WESTPARK LIQUOR',
    'SOUTHS': 'SOUTHSIDE LIQUOR', 
    'PENHOL': 'PENHOLD',
    'ROSS': "ROSS'S",
    'RED': 'RED DEER',
    'NORTH': 'NORTH',
    '608-WB': 'WINE AND BEYOND',
    'LB': 'LIQUOR BARN',
    'LD': 'LIQUOR DEPOT',
    'WB': 'WINE AND BEYOND'
}

updates = []

# 1. Standardize "Cash Withdrawal" to "CASH WITHDRAWAL"
print("\n1. STANDARDIZING 'Cash Withdrawal' → 'CASH WITHDRAWAL'")
print("-"*100)

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE vendor_name = 'Cash Withdrawal'
      AND exclude_from_reports = FALSE
""")

cash_fix = cur.fetchall()
print(f"Found {len(cash_fix)} receipts with 'Cash Withdrawal' (title case)")

for receipt_id, vendor, amount in cash_fix:
    updates.append({
        'receipt_id': receipt_id,
        'old_vendor': vendor,
        'new_vendor': 'CASH WITHDRAWAL',
        'reason': 'Standardize case'
    })
    print(f"  Receipt {receipt_id}: '{vendor}' → 'CASH WITHDRAWAL' (${float(amount):,.2f})")

# Also fix "CASH WITHDRAWAL 2" etc
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount
    FROM receipts
    WHERE vendor_name LIKE 'CASH WITHDRAWAL %'
      AND exclude_from_reports = FALSE
""")

cash_numbered = cur.fetchall()
for receipt_id, vendor, amount in cash_numbered:
    updates.append({
        'receipt_id': receipt_id,
        'old_vendor': vendor,
        'new_vendor': 'CASH WITHDRAWAL',
        'reason': 'Remove numbering'
    })
    print(f"  Receipt {receipt_id}: '{vendor}' → 'CASH WITHDRAWAL' (${float(amount):,.2f})")

# 2. Extract vendor from "Cheque Expense - [vendor]"
print("\n2. EXTRACTING VENDORS FROM 'Cheque Expense - [vendor]'")
print("-"*100)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE 'Cheque Expense -%'
      AND r.exclude_from_reports = FALSE
    ORDER BY r.gross_amount DESC
""")

cheque_expense = cur.fetchall()
print(f"Found {len(cheque_expense)} 'Cheque Expense' entries")

for receipt_id, vendor, amount, banking_desc in cheque_expense:
    # Check if banking says cash withdrawal
    if banking_desc and ('CASH WITHDRAWAL' in banking_desc.upper() or 'ATM' in banking_desc.upper()):
        new_vendor = 'CASH WITHDRAWAL'
        reason = 'Banking shows cash withdrawal'
    else:
        # Extract vendor after ' - '
        if ' - ' in vendor:
            new_vendor = vendor.split(' - ', 1)[1].strip()
            reason = 'Extract from QB format'
        else:
            continue
    
    updates.append({
        'receipt_id': receipt_id,
        'old_vendor': vendor,
        'new_vendor': new_vendor,
        'reason': reason
    })

print(f"  Will extract {len([u for u in updates if u['reason'] == 'Extract from QB format'])} vendor names")
print(f"  Will fix {len([u for u in updates if u['reason'] == 'Banking shows cash withdrawal'])} QB→cash")

# Show top extractions
qb_extractions = [u for u in updates if u['reason'] == 'Extract from QB format'][:10]
for update in qb_extractions:
    print(f"    '{update['old_vendor'][:50]}' → '{update['new_vendor']}'")

# 3. Extract EMAIL TRANSFER recipients
print("\n3. EXTRACTING EMAIL TRANSFER RECIPIENTS")
print("-"*100)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name IN ('EMAIL TRANSFER', 'E-TRANSFER')
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
""")

email_transfers = cur.fetchall()
print(f"Found {len(email_transfers)} EMAIL TRANSFER entries with banking descriptions")

email_extracted = 0
for receipt_id, vendor, amount, banking_desc in email_transfers:
    # Try to extract recipient
    match1 = re.search(r'E-TRANSFER[^A-Z]*([A-Z][A-Za-z\s&\.]+?)\s*4506', banking_desc)
    match2 = re.search(r'EMAIL TRANSFER TO\s+([A-Z][A-Za-z\s&\.]+)', banking_desc)
    match3 = re.search(r'TRANSFER[^A-Z]*([A-Z][A-Za-z\s&\.]{3,}?)\s*(?:4506|\d{4}\*)', banking_desc)
    
    recipient = None
    if match1:
        recipient = match1.group(1).strip()
    elif match2:
        recipient = match2.group(1).strip()
    elif match3:
        recipient = match3.group(1).strip()
    
    if recipient:
        # Clean up
        recipient = recipient.replace('PURCHASE', '').replace('SEND', '').strip()
        if len(recipient) > 3:
            updates.append({
                'receipt_id': receipt_id,
                'old_vendor': vendor,
                'new_vendor': recipient,
                'reason': 'Extract from banking'
            })
            email_extracted += 1

print(f"  Successfully extracted {email_extracted} recipient names ({email_extracted/len(email_transfers)*100:.1f}%)")

# Show samples
email_samples = [u for u in updates if 'Extract from banking' in u['reason'] and u['old_vendor'] in ('EMAIL TRANSFER', 'E-TRANSFER')][:10]
for update in email_samples:
    print(f"    'EMAIL TRANSFER' → '{update['new_vendor']}'")

# 4. Extract FGP merchant names
print("\n4. EXTRACTING FGP MERCHANT NAMES")
print("-"*100)

cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, bt.description
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name LIKE 'FGP%'
      AND r.exclude_from_reports = FALSE
      AND bt.description IS NOT NULL
""")

fgp_entries = cur.fetchall()
print(f"Found {len(fgp_entries)} FGP code entries")

fgp_decoded = 0
for receipt_id, vendor, amount, banking_desc in fgp_entries:
    # Extract FGP code
    match = re.search(r'FGP\d+\s+([A-Z0-9-]+)', banking_desc)
    if match:
        merchant_code = match.group(1).split()[0]  # Get first part before space/card
        
        # Look up in merchant table
        if merchant_code in FGP_MERCHANTS:
            new_vendor = FGP_MERCHANTS[merchant_code]
            updates.append({
                'receipt_id': receipt_id,
                'old_vendor': vendor,
                'new_vendor': new_vendor,
                'reason': f'Decode FGP {merchant_code}'
            })
            fgp_decoded += 1

print(f"  Successfully decoded {fgp_decoded} FGP merchant codes")

# SUMMARY
print("\n" + "="*100)
print("SUMMARY OF CHANGES")
print("="*100)

by_reason = {}
for update in updates:
    reason = update['reason']
    by_reason[reason] = by_reason.get(reason, 0) + 1

for reason, count in sorted(by_reason.items(), key=lambda x: x[1], reverse=True):
    print(f"  {reason}: {count} receipts")

print(f"\nTOTAL UPDATES: {len(updates)} receipts")

# Apply changes
if not DRY_RUN and updates:
    print("\n" + "="*100)
    print("APPLYING CHANGES...")
    print("="*100)
    
    for update in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (update['new_vendor'], update['receipt_id']))
    
    conn.commit()
    print(f"✅ Updated {len(updates)} receipts")
elif DRY_RUN:
    print(f"\n⚠️  DRY RUN - No changes made. Set DRY_RUN=False to apply.")
else:
    print(f"\n✅ No updates needed")

cur.close()
conn.close()

print("\n" + "="*100)
print(f"COMPLETED: {timestamp}")
print("="*100)
