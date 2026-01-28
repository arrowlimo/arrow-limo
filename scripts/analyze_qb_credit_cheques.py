"""
Analyze QuickBooks CREDIT cheque transactions to determine if they're needed.
Check for:
1. Duplicates with matching DEBITs
2. Standalone credits (actual banking transactions)
3. Confusing patterns
"""
import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("QUICKBOOKS CREDIT CHEQUE TRANSACTION ANALYSIS")
print("=" * 120)

# Get all CREDIT cheque transactions
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        bt.account_number,
        bt.credit_amount,
        bt.description,
        bt.source_file,
        r.receipt_id
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE (bt.description ILIKE '%CHQ%' OR bt.description ILIKE '%CHEQUE%')
      AND bt.credit_amount IS NOT NULL
    ORDER BY bt.transaction_date, bt.transaction_id
""")

credit_txs = cur.fetchall()

print(f"\nTotal CREDIT cheque transactions: {len(credit_txs)}")

# Categorize by source
by_source = defaultdict(list)
for tx in credit_txs:
    source = tx[6] if tx[6] else "Unknown"
    by_source[source].append(tx)

print(f"\nBy source file:")
for source, txs in sorted(by_source.items(), key=lambda x: -len(x[1])):
    print(f"  {source}: {len(txs)}")

# Check which ones have "Cheque Expense" pattern (QB journal entries)
qb_journal = [tx for tx in credit_txs if 'Cheque Expense' in tx[5]]
other_credits = [tx for tx in credit_txs if 'Cheque Expense' not in tx[5]]

print(f"\nBy description pattern:")
print(f"  'Cheque Expense' (QB journal entries): {len(qb_journal)}")
print(f"  Other CREDIT patterns: {len(other_credits)}")

# Show sample of non-QB credit patterns
if other_credits:
    print(f"\n\nNON-QB CREDIT PATTERNS ({len(other_credits)} transactions):")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Amount':>10} | Description")
    print("-" * 100)
    for tx_id, date, bank, acct, amount, desc, source, receipt in other_credits[:20]:
        print(f"{tx_id:6d} | {date} | {bank:7} | ${amount:>9,.2f} | {desc[:60]}")
    if len(other_credits) > 20:
        print(f"  ... and {len(other_credits) - 20} more")

# Now get all DEBIT cheque transactions for matching
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        debit_amount,
        description,
        source_file
    FROM banking_transactions
    WHERE (description ILIKE '%CHQ%' OR description ILIKE '%CHEQUE%')
      AND debit_amount IS NOT NULL
""")

debit_txs = cur.fetchall()

# Build index by date+amount
debit_index = defaultdict(list)
for tx_id, date, amount, desc, source in debit_txs:
    key = (date, amount)
    debit_index[key].append((tx_id, desc, source))

# Check how many CREDIT transactions have matching DEBITs
print(f"\n\n" + "=" * 120)
print("MATCHING ANALYSIS: CREDITS vs DEBITS")
print("=" * 120)

credits_with_match = []
credits_without_match = []

for tx_id, date, bank, acct, credit_amount, desc, source, receipt in credit_txs:
    key = (date, credit_amount)
    if key in debit_index:
        matches = debit_index[key]
        credits_with_match.append((tx_id, date, bank, credit_amount, desc, matches))
    else:
        credits_without_match.append((tx_id, date, bank, credit_amount, desc, source))

print(f"\nCREDIT transactions with matching DEBIT (same date+amount): {len(credits_with_match)}")
print(f"CREDIT transactions WITHOUT matching DEBIT: {len(credits_without_match)}")

# Show sample of matched credits (these are QB duplicates)
if credits_with_match:
    print(f"\n\nSAMPLE: CREDITS WITH MATCHING DEBITS (QB duplicates):")
    print(f"{'Credit TX':>9} | {'Date':10} | {'Amount':>10} | Credit Description → Debit TX & Description")
    print("-" * 120)
    for tx_id, date, bank, amount, desc, matches in credits_with_match[:10]:
        credit_desc = desc[:40]
        for debit_id, debit_desc, debit_source in matches[:1]:  # Show first match
            print(f"{tx_id:9d} | {date} | ${amount:>9,.2f} | {credit_desc:40} → TX {debit_id:6d} {debit_desc[:40]}")
    if len(credits_with_match) > 10:
        print(f"  ... and {len(credits_with_match) - 10} more")

# Show credits WITHOUT matching debits (these might be real)
if credits_without_match:
    print(f"\n\nCREDITS WITHOUT MATCHING DEBITS ({len(credits_without_match)} - possibly real transactions):")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Amount':>10} | {'Source':40} | Description")
    print("-" * 120)
    for tx_id, date, bank, amount, desc, source in credits_without_match[:20]:
        source_display = (source[:37] + '...') if source and len(source) > 40 else (source or 'None')
        print(f"{tx_id:6d} | {date} | {bank:7} | ${amount:>9,.2f} | {source_display:40} | {desc[:40]}")
    if len(credits_without_match) > 20:
        print(f"  ... and {len(credits_without_match) - 20} more")

# Check for confusing patterns - multiple credits for same debit
print(f"\n\n" + "=" * 120)
print("CONFUSING PATTERNS: Multiple CREDITS for same DEBIT")
print("=" * 120)

multi_credit_debits = {k: v for k, v in credits_with_match if len(v[5]) > 1}
if any(len(matches) > 1 for _, _, _, _, _, matches in credits_with_match):
    confusing = [(tx_id, date, bank, amount, desc, matches) 
                 for tx_id, date, bank, amount, desc, matches in credits_with_match 
                 if len(matches) > 1]
    print(f"Found {len(confusing)} credits with multiple debit matches:")
    for tx_id, date, bank, amount, desc, matches in confusing[:10]:
        print(f"\n  Credit TX {tx_id} | {date} | ${amount:,.2f} | {desc[:50]}")
        print(f"    Matches {len(matches)} debits:")
        for debit_id, debit_desc, debit_source in matches:
            print(f"      TX {debit_id:6d} | {debit_desc[:60]}")
else:
    print("✅ No confusing patterns found - each credit matches at most one debit")

# Summary and recommendation
print(f"\n\n" + "=" * 120)
print("SUMMARY & RECOMMENDATION")
print("=" * 120)
print(f"Total CREDIT cheque transactions: {len(credit_txs)}")
print(f"  QB 'Cheque Expense' journal entries: {len(qb_journal)}")
print(f"  Credits with matching debits (same date+amount): {len(credits_with_match)}")
print(f"  Credits WITHOUT matching debits: {len(credits_without_match)}")

if len(credits_with_match) > 900:
    print(f"\n⚠️  RECOMMENDATION:")
    print(f"  - {len(credits_with_match)} credits are QB journal entry DUPLICATES of actual bank debits")
    print(f"  - These create confusion and inflate transaction counts")
    print(f"  - SAFE TO DELETE: Mark these {len(credits_with_match)} as duplicates or delete them")
    print(f"  - KEEP: {len(credits_without_match)} credits without matching debits (possible real transactions)")

cur.close()
conn.close()
