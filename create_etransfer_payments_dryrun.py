#!/usr/bin/env python3
"""Create payment records for matched e-transfers (DRY RUN)."""
import psycopg2
import os
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

DRY_RUN = True  # Set to False to execute

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# [Copy matching logic from previous script]
EMPLOYEE_PATTERNS = ['BARB', 'BARBARA', 'PEACOCK', 'DAVID RICHARD', 'PAUL RICHARD', 'MATTHEW RICHARD', 
                     'JERRY', 'SCHANDRIP', 'JEANNIE', 'SHILLINGTON', 'MICHAEL RICHARD']

def is_employee_etransfer(description):
    desc_upper = description.upper()
    return any(pattern in desc_upper for pattern in EMPLOYEE_PATTERNS)

def extract_name_from_etransfer(description):
    desc_upper = description.upper().strip()
    ref_match = re.search(r'(\d{12,15})\s+(.+)$', desc_upper)
    if ref_match:
        return ref_match.group(2).strip()
    for pattern in [r'E-?TRANSFER\s+FROM\s+(.+)', r'E-?TRANSFER\s+(.+)', r'INTERNET\s+BANKING\s+E-?TRANSFER\s+(.+)']:
        match = re.search(pattern, desc_upper)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+\d{6,}$', '', name)
            name = re.sub(r'\s+\d{4}-\d{2}-\d{2}$', '', name)
            if len(name) >= 3:
                return name
    return None

def similarity_score(str1, str2):
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()

print("\n" + "=" * 140)
print("CREATE PAYMENT RECORDS FOR MATCHED E-TRANSFERS".center(140))
if DRY_RUN:
    print("*** DRY RUN MODE - NO DATABASE CHANGES ***".center(140))
print("=" * 140)

# Get unmatched customer e-transfers
cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
    ORDER BY bt.transaction_date DESC;
''')

all_etransfers = cur.fetchall()
customer_etransfers = [e for e in all_etransfers if not is_employee_etransfer(e[3])]

# Get clients
cur.execute('''SELECT client_id, client_name, company_name FROM clients 
            WHERE client_name IS NOT NULL OR company_name IS NOT NULL''')
clients_raw = cur.fetchall()

client_variants = {}
for client_id, client_name, company_name in clients_raw:
    names = []
    if client_name:
        names.append(client_name.upper().strip())
    if company_name and company_name != client_name:
        names.append(company_name.upper().strip())
    for name in names:
        if name:
            if name not in client_variants:
                client_variants[name] = []
            client_variants[name].append((client_id, client_name or company_name))

# Match e-transfers (only exact + fuzzy high for safety)
high_confidence_matches = []

for etransfer in customer_etransfers:
    trans_id, trans_date, amount, description = etransfer
    extracted_name = extract_name_from_etransfer(description)
    
    if not extracted_name or len(extracted_name) < 3:
        continue
    
    best_match = None
    best_score = 0
    
    # Exact match
    if extracted_name in client_variants:
        best_match = client_variants[extracted_name][0]
        best_score = 1.0
    else:
        # Fuzzy match
        for client_name_upper, client_list in client_variants.items():
            score = similarity_score(extracted_name, client_name_upper)
            if score > best_score:
                best_score = score
                best_match = client_list[0]
            if (extracted_name in client_name_upper or client_name_upper in extracted_name):
                if len(extracted_name) >= 5:
                    contains_score = 0.85
                    if contains_score > best_score:
                        best_score = contains_score
                        best_match = client_list[0]
    
    # Only include exact (100%) or fuzzy high (90%+)
    if best_score >= 0.90 and best_match:
        high_confidence_matches.append((etransfer, best_match, best_score))

print(f"\n📊 High-confidence matches: {len(high_confidence_matches)} e-transfers")
print(f"   Total amount: ${sum(e[0][2] for e in high_confidence_matches):,.2f}\n")

# Find charters for each matched e-transfer
payment_creates = []
no_charter_found = []

for etransfer, client, score in high_confidence_matches:
    trans_id, trans_date, amount, description = etransfer
    client_id, client_name = client
    
    # Find charters within ±365 days
    date_from = trans_date - timedelta(days=365)
    date_to = trans_date + timedelta(days=365)
    
    cur.execute('''
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            (c.total_amount_due - c.paid_amount) as balance,
            ABS(c.total_amount_due - c.paid_amount - %s) as amount_diff
        FROM charters c
        WHERE c.client_id = %s
          AND c.charter_date BETWEEN %s AND %s
          AND c.total_amount_due > 0
          AND (c.total_amount_due - c.paid_amount) > 0.10
        ORDER BY amount_diff ASC, charter_date DESC
        LIMIT 1;
    ''', (amount, client_id, date_from, date_to))
    
    charter = cur.fetchone()
    
    if charter:
        payment_creates.append({
            'etransfer': etransfer,
            'client': client,
            'charter': charter,
            'score': score
        })
    else:
        no_charter_found.append((etransfer, client, score))

print("=" * 140)
print(f"PAYMENT CREATION PLAN:")
print("=" * 140)
print(f"\n✅ Can create payments: {len(payment_creates)} e-transfers → charters")
print(f"   Total amount: ${sum(p['etransfer'][2] for p in payment_creates):,.2f}")
print(f"\n⚠️  No charter found: {len(no_charter_found)} e-transfers")
print(f"   (Client matched but no open charter within 365 days)")
print(f"   Total amount: ${sum(e[0][2] for e in no_charter_found):,.2f}")

# Show sample creates
if payment_creates:
    print(f"\n" + "=" * 140)
    print(f"SAMPLE PAYMENT RECORDS TO CREATE (showing first 20):")
    print("=" * 140)
    print(f"{'Date':<12} | {'Amount':>10} | {'Client':<30} | {'Charter':<9} | {'Balance':>10} | {'Match'}")
    print("-" * 140)
    
    for i, p in enumerate(payment_creates[:20]):
        etransfer = p['etransfer']
        client = p['client']
        charter = p['charter']
        score = p['score']
        
        trans_date = etransfer[1].strftime('%Y-%m-%d')
        amount = etransfer[2]
        client_name = client[1][:29]
        reserve = charter[1] or 'N/A'
        balance = charter[5]
        
        print(f"{trans_date} | ${amount:>9.2f} | {client_name:<30} | {reserve:<9} | ${balance:>9.2f} | {score:>5.0%}")
    
    if len(payment_creates) > 20:
        print(f"... and {len(payment_creates) - 20} more")

print("\n" + "=" * 140)
if DRY_RUN:
    print("💡 DRY RUN COMPLETE - No changes made")
    print("\n   To execute, set DRY_RUN = False in the script")
else:
    print("⚠️  READY TO EXECUTE - This will:")
    print(f"   - Create {len(payment_creates)} payment records")
    print(f"   - Link them to charters via reserve_number")
    print(f"   - Update banking_transactions.reconciled_payment_id")
    print(f"   - Recalculate charter paid_amount")

print("=" * 140 + "\n")

cur.close()
conn.close()
