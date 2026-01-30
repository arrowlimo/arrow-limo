#!/usr/bin/env python3
"""Check CIBC staging vs banking_transactions duplicates."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("CIBC STAGING DUPLICATE CHECK")
print("=" * 80)

# 1. cibc_checking_staging - use amount_in/amount_out
print("\n1. cibc_checking_staging vs banking_transactions")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) as match_count
    FROM cibc_checking_staging ccs
    JOIN banking_transactions bt ON (
        ccs.txn_date = bt.transaction_date
        AND (
            (COALESCE(ccs.amount_out, 0) > 0 AND COALESCE(ccs.amount_out, 0) = COALESCE(bt.debit_amount, 0))
            OR
            (COALESCE(ccs.amount_in, 0) > 0 AND COALESCE(ccs.amount_in, 0) = COALESCE(bt.credit_amount, 0))
        )
    )
""")

checking_matches = cur.fetchone()[0]
checking_total = 6506

print(f"Matched rows: {checking_matches:,} / {checking_total:,} ({checking_matches/checking_total*100:.1f}%)")
print(f"Unmatched: {checking_total - checking_matches:,}")

# 2. cibc_ledger_staging
print("\n2. cibc_ledger_staging vs banking_transactions")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) as match_count
    FROM cibc_ledger_staging cls
    JOIN banking_transactions bt ON (
        cls.txn_date = bt.transaction_date
        AND COALESCE(cls.amount, 0) = COALESCE(bt.debit_amount, bt.credit_amount, 0)
    )
""")

ledger_matches = cur.fetchone()[0]
ledger_total = 53

print(f"Matched rows: {ledger_matches:,} / {ledger_total:,} ({ledger_matches/ledger_total*100:.1f}%)")
print(f"Unmatched: {ledger_total - ledger_matches:,}")

# 3. cibc_qbo_staging
print("\n3. cibc_qbo_staging vs banking_transactions")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) as match_count
    FROM cibc_qbo_staging cqs
    JOIN banking_transactions bt ON (
        cqs.dtposted = bt.transaction_date
        AND COALESCE(cqs.trnamt, 0) = COALESCE(bt.debit_amount, bt.credit_amount, 0)
    )
""")

qbo_matches = cur.fetchone()[0]
qbo_total = 1200

print(f"Matched rows: {qbo_matches:,} / {qbo_total:,} ({qbo_matches/qbo_total*100:.1f}%)")
print(f"Unmatched: {qbo_total - qbo_matches:,}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_staging = checking_total + ledger_total + qbo_total
total_matches = checking_matches + ledger_matches + qbo_matches

print(f"\nTotal staging rows: {total_staging:,}")
print(f"Total matched: {total_matches:,} ({total_matches/total_staging*100:.1f}%)")
print(f"Total unmatched: {total_staging - total_matches:,}")

if total_matches / total_staging > 0.95:
    print("\n[ARCHIVE] High duplicate rate (>95%) - staging data already in banking_transactions")
elif total_matches / total_staging > 0.70:
    print("\n[SELECTIVE] Moderate duplicates (70-95%) - some new data to promote")
else:
    print("\n[PROMOTE] Low duplicates (<70%) - significant new data to add")

cur.close()
conn.close()
