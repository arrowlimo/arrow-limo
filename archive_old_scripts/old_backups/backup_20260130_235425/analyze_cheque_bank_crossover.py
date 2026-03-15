"""
Analyze cheque number crossover between Scotia Bank and CIBC accounts.

Cheque numbers can overlap between banks but amounts differ.
"""
import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("CHEQUE BANK ACCOUNT CROSSOVER ANALYSIS")
print("=" * 80)

# 1. Identify all cheques in receipts by bank account
print("\n1. RECEIPTS: Cheques by Bank Account")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN r.mapped_bank_account_id = 1 THEN 'CIBC 0228362'
            WHEN r.mapped_bank_account_id = 2 THEN 'SCOTIA 903990106011'
            ELSE 'Unknown/NULL'
        END as bank,
        r.mapped_bank_account_id,
        COUNT(*) as count,
        MIN(r.gross_amount) as min_amount,
        MAX(r.gross_amount) as max_amount,
        SUM(r.gross_amount) as total_amount
    FROM receipts r
    WHERE r.description LIKE '%CHQ%' 
       OR r.description LIKE '%CHEQUE%'
       OR r.payment_method LIKE '%CHQ%'
    GROUP BY r.mapped_bank_account_id
    ORDER BY r.mapped_bank_account_id NULLS LAST
""")

for bank, acct_id, count, min_amt, max_amt, total in cur.fetchall():
    acct_display = f"(ID: {acct_id})" if acct_id else "(NULL)"
    print(f"  {bank:25} {acct_display:15} | {count:3} cheques | ${min_amt:>10,.2f} - ${max_amt:>10,.2f} | Total: ${total:>12,.2f}")

# 2. Extract cheque numbers from receipts
print("\n\n2. RECEIPTS: Cheque Numbers by Bank")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        CASE 
            WHEN r.mapped_bank_account_id = 1 THEN 'CIBC'
            WHEN r.mapped_bank_account_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        r.vendor_name,
        r.gross_amount,
        r.description,
        r.payment_method
    FROM receipts r
    WHERE r.description LIKE '%CHQ%' 
       OR r.description LIKE '%CHEQUE%'
       OR r.payment_method LIKE '%CHQ%'
    ORDER BY r.mapped_bank_account_id, r.receipt_date
""")

import re
cheque_pattern = re.compile(r'CHQ\s*(\d+)', re.IGNORECASE)

cheques_by_bank = defaultdict(list)
for receipt_id, date, bank, vendor, amount, desc, payment in cur.fetchall():
    # Extract cheque number
    cheque_num = None
    combined = f"{desc or ''} {payment or ''}"
    match = cheque_pattern.search(combined)
    if match:
        cheque_num = int(match.group(1))
    
    cheques_by_bank[bank].append({
        'receipt_id': receipt_id,
        'date': date,
        'cheque_num': cheque_num,
        'vendor': vendor,
        'amount': amount,
        'desc': combined[:60]
    })

for bank in ['CIBC', 'SCOTIA', 'Unknown']:
    if bank in cheques_by_bank:
        cheques = cheques_by_bank[bank]
        print(f"\n{bank} - {len(cheques)} cheques:")
        for chq in cheques[:10]:  # First 10
            num_display = f"#{chq['cheque_num']:03d}" if chq['cheque_num'] else "???"
            vendor_display = chq['vendor'][:25] if chq['vendor'] else "None"
            amount_display = chq['amount'] if chq['amount'] is not None else 0.0
            print(f"  {chq['receipt_id']} | {chq['date']} | {num_display} | ${amount_display:>10,.2f} | {vendor_display:25} | {chq['desc'][:40]}")
        if len(cheques) > 10:
            print(f"  ... and {len(cheques) - 10} more")

# 3. Check for duplicate cheque numbers across banks
print("\n\n3. CHEQUE NUMBER OVERLAP CHECK")
print("-" * 80)

cibc_nums = {c['cheque_num'] for c in cheques_by_bank.get('CIBC', []) if c['cheque_num']}
scotia_nums = {c['cheque_num'] for c in cheques_by_bank.get('SCOTIA', []) if c['cheque_num']}
overlap = cibc_nums & scotia_nums

if overlap:
    print(f"⚠️  Found {len(overlap)} cheque numbers used in BOTH banks:")
    for num in sorted(overlap)[:20]:
        print(f"  CHQ #{num:03d}")
        cibc_chqs = [c for c in cheques_by_bank['CIBC'] if c['cheque_num'] == num]
        scotia_chqs = [c for c in cheques_by_bank['SCOTIA'] if c['cheque_num'] == num]
        for chq in cibc_chqs:
            print(f"    CIBC:   {chq['date']} | ${chq['amount']:>10,.2f} | {chq['vendor'][:30] if chq['vendor'] else 'None'}")
        for chq in scotia_chqs:
            print(f"    SCOTIA: {chq['date']} | ${chq['amount']:>10,.2f} | {chq['vendor'][:30] if chq['vendor'] else 'None'}")
else:
    print("✅ No overlap - all cheque numbers are unique to their bank")

# 4. Now check banking transactions for CHQ 202/203
print("\n\n4. BANKING TRANSACTIONS: CHQ 202-203 by Bank Account")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC 0228362'
            WHEN bt.bank_id = 2 THEN 'SCOTIA 903990106011'
            ELSE 'Unknown'
        END as bank,
        COALESCE(bt.debit_amount, 0) - COALESCE(bt.credit_amount, 0) as amount,
        CASE WHEN bt.debit_amount > 0 THEN 'DEBIT' ELSE 'CREDIT' END as type,
        bt.description
    FROM banking_transactions bt
    WHERE (bt.description LIKE '%CHQ 202%' 
        OR bt.description LIKE '%CHQ 203%'
        OR bt.description LIKE '%CHEQUE 202%'
        OR bt.description LIKE '%CHEQUE 203%')
    ORDER BY bt.bank_id, bt.transaction_date
""")

banking_cheques = cur.fetchall()
if banking_cheques:
    print(f"Found {len(banking_cheques)} banking transactions for CHQ 202-203:\n")
    for tx_id, date, bank, amount, tx_type, desc in banking_cheques:
        print(f"  TX {tx_id} | {date} | {bank:25} | ${abs(amount):>10,.2f} {tx_type:6} | {desc}")
else:
    print("❌ No banking transactions found for CHQ 202-203")

# 5. Search for Metuier/Metirier across both banks
print("\n\n5. BANKING TRANSACTIONS: Metuier/Metirier Across Banks")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC 0228362'
            WHEN bt.bank_id = 2 THEN 'SCOTIA 903990106011'
            ELSE 'Unknown'
        END as bank,
        COALESCE(bt.debit_amount, 0) - COALESCE(bt.credit_amount, 0) as amount,
        CASE WHEN bt.debit_amount > 0 THEN 'DEBIT' ELSE 'CREDIT' END as type,
        bt.description
    FROM banking_transactions bt
    WHERE bt.description ILIKE '%METUI%' 
       OR bt.description ILIKE '%METIRI%'
    ORDER BY bt.bank_id, bt.transaction_date
""")

metuier_txs = cur.fetchall()
if metuier_txs:
    print(f"Found {len(metuier_txs)} banking transactions for Metuier/Metirier:\n")
    for tx_id, date, bank, amount, tx_type, desc in metuier_txs:
        print(f"  TX {tx_id} | {date} | {bank:25} | ${abs(amount):>10,.2f} {tx_type:6} | {desc}")
else:
    print("❌ No transactions found")

# 6. Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Receipt cheques: {len(cheques_by_bank.get('CIBC', []))} CIBC, {len(cheques_by_bank.get('SCOTIA', []))} Scotia, {len(cheques_by_bank.get('Unknown', []))} Unknown")
print(f"Cheque number overlap: {len(overlap)} numbers used in both banks")
print(f"CHQ 202-203 banking transactions: {len(banking_cheques)}")
print(f"Metuier/Metirier banking transactions: {len(metuier_txs)}")

cur.close()
conn.close()
