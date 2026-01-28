#!/usr/bin/env python3
"""Improved e-transfer reconciliation with better name extraction and fuzzy matching."""
import psycopg2
import os
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Employee names to exclude
EMPLOYEE_PATTERNS = ['BARB', 'BARBARA', 'PEACOCK', 'DAVID RICHARD', 'PAUL RICHARD', 'MATTHEW RICHARD', 
                     'JERRY', 'SCHANDRIP', 'JEANNIE', 'SHILLINGTON', 'MICHAEL RICHARD']

def is_employee_etransfer(description):
    """Check if e-transfer is from an employee."""
    desc_upper = description.upper()
    return any(pattern in desc_upper for pattern in EMPLOYEE_PATTERNS)

def extract_name_from_etransfer(description):
    """Extract client name from various e-transfer description formats."""
    desc_upper = description.upper().strip()
    
    # Pattern 1: "Internet Banking E-TRANSFER 105763407934 DAVID WIL"
    # Pattern 2: "Internet Banking E-TRANSFER105763407934 DAVID RICHARD"
    # Pattern 3: "E-TRANSFER FROM JOHN SMITH"
    # Pattern 4: "ETRANSFER JOHN SMITH"
    
    # Extract everything after the reference number (if present)
    ref_match = re.search(r'(\d{12,15})\s+(.+)$', desc_upper)
    if ref_match:
        return ref_match.group(2).strip()
    
    # Try standard patterns
    for pattern in [
        r'E-?TRANSFER\s+FROM\s+(.+)',
        r'E-?TRANSFER\s+(.+)',
        r'INTERNET\s+BANKING\s+E-?TRANSFER\s+(.+)'
    ]:
        match = re.search(pattern, desc_upper)
        if match:
            name = match.group(1).strip()
            # Remove trailing numbers/dates
            name = re.sub(r'\s+\d{6,}$', '', name)
            name = re.sub(r'\s+\d{4}-\d{2}-\d{2}$', '', name)
            if len(name) >= 3:
                return name
    
    return None

def similarity_score(str1, str2):
    """Calculate similarity between two strings (0-1)."""
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()

# Get unmatched customer e-transfers
cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description,
        bt.reconciled_payment_id
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
    ORDER BY bt.transaction_date DESC;
''')

all_etransfers = cur.fetchall()

# Filter out employee e-transfers
customer_etransfers = [e for e in all_etransfers if not is_employee_etransfer(e[3])]

print("\n" + "=" * 140)
print("IMPROVED E-TRANSFER RECONCILIATION - CLIENT NAME MATCHING".center(140))
print("=" * 140)
print(f"\n📊 Total e-transfers: {len(all_etransfers)}")
print(f"   Employee e-transfers (excluded): {len(all_etransfers) - len(customer_etransfers)}")
print(f"   Customer e-transfers: {len(customer_etransfers)} | ${sum(e[2] for e in customer_etransfers):,.2f}\n")

# Get all clients with their variations
cur.execute('''
    SELECT 
        cl.client_id,
        cl.client_name,
        cl.company_name
    FROM clients cl
    WHERE cl.client_name IS NOT NULL OR cl.company_name IS NOT NULL;
''')

clients_raw = cur.fetchall()

# Build client lookup with variations
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

print(f"📊 Loaded {len(clients_raw)} clients with {len(client_variants)} name variations\n")

# Match e-transfers to clients
print("=" * 140)
print("MATCHING E-TRANSFERS TO CLIENTS:")
print("=" * 140)

matches = {
    'exact': [],
    'fuzzy_high': [],  # 90%+ similarity
    'fuzzy_med': [],   # 75-89% similarity
    'partial': [],     # Contains match
    'unmatched': []
}

for etransfer in customer_etransfers:
    trans_id, trans_date, amount, description, _ = etransfer
    
    extracted_name = extract_name_from_etransfer(description)
    
    if not extracted_name or len(extracted_name) < 3:
        matches['unmatched'].append((etransfer, None, 'NO_NAME'))
        continue
    
    best_match = None
    best_score = 0
    match_type = None
    
    # Try exact match
    if extracted_name in client_variants:
        best_match = client_variants[extracted_name][0]
        best_score = 1.0
        match_type = 'exact'
    else:
        # Try fuzzy matching
        for client_name_upper, client_list in client_variants.items():
            # Similarity score
            score = similarity_score(extracted_name, client_name_upper)
            
            if score > best_score:
                best_score = score
                best_match = client_list[0]
            
            # Also check if one contains the other (for truncated names)
            if (extracted_name in client_name_upper or client_name_upper in extracted_name):
                if len(extracted_name) >= 5:  # Minimum length for contains match
                    contains_score = 0.85
                    if contains_score > best_score:
                        best_score = contains_score
                        best_match = client_list[0]
        
        # Categorize by score
        if best_score >= 0.90:
            match_type = 'fuzzy_high'
        elif best_score >= 0.75:
            match_type = 'fuzzy_med'
        elif best_score >= 0.60:
            match_type = 'partial'
        else:
            match_type = None
    
    if match_type:
        matches[match_type].append((etransfer, best_match, extracted_name, best_score))
    else:
        matches['unmatched'].append((etransfer, extracted_name, 'NO_MATCH'))

# Show results
print(f"\n📊 MATCHING RESULTS:")
print(f"   Exact Matches:       {len(matches['exact']):>5} e-transfers | ${sum(e[0][2] for e in matches['exact']):>14,.2f}")
print(f"   Fuzzy High (90%+):   {len(matches['fuzzy_high']):>5} e-transfers | ${sum(e[0][2] for e in matches['fuzzy_high']):>14,.2f}")
print(f"   Fuzzy Med (75-89%):  {len(matches['fuzzy_med']):>5} e-transfers | ${sum(e[0][2] for e in matches['fuzzy_med']):>14,.2f}")
print(f"   Partial Contains:    {len(matches['partial']):>5} e-transfers | ${sum(e[0][2] for e in matches['partial']):>14,.2f}")
print(f"   Unmatched:           {len(matches['unmatched']):>5} e-transfers | ${sum(e[0][2] for e in matches['unmatched']):>14,.2f}")

total_matched = len(matches['exact']) + len(matches['fuzzy_high']) + len(matches['fuzzy_med']) + len(matches['partial'])
print(f"\n   TOTAL MATCHED:       {total_matched:>5} e-transfers ({100*total_matched/len(customer_etransfers):.1f}%)")

# Show sample matches
for match_type_label, match_key in [('EXACT MATCHES', 'exact'), ('FUZZY HIGH (90%+)', 'fuzzy_high')]:
    if matches[match_key]:
        print(f"\n" + "=" * 140)
        print(f"SAMPLE {match_type_label} (showing first 15):")
        print("=" * 140)
        print(f"{'Date':<12} | {'Amount':>10} | {'Extracted Name':<35} | {'Score':>5} | {'Matched Client':<40}")
        print("-" * 140)
        
        for i, item in enumerate(matches[match_key][:15]):
            etransfer, client, extracted, score = item
            trans_date = etransfer[1].strftime('%Y-%m-%d')
            amount = etransfer[2]
            client_name = client[1][:39]
            print(f"{trans_date} | ${amount:>9.2f} | {extracted[:34]:<35} | {score:>5.0%} | {client_name}")
        
        if len(matches[match_key]) > 15:
            print(f"... and {len(matches[match_key]) - 15} more")

print("\n" + "=" * 140)
print("💡 NEXT STEP: CREATE PAYMENT RECORDS")
print("=" * 140)
print(f"\n✅ Ready to create payments for {total_matched} matched e-transfers")
print(f"   - Will match to charters within ±365 days by client_id")
print(f"   - Will handle multi-charter bookings (prioritize by balance match)")
print(f"   - Will update banking_transactions.reconciled_payment_id")
print("\n" + "=" * 140 + "\n")

cur.close()
conn.close()
