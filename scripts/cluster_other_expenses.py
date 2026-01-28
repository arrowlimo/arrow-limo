#!/usr/bin/env python3
"""Cluster unlinked 'Other' expenses to suggest next actions (receipt vs transfer)."""
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter, defaultdict

NORMALIZE_PATTERNS = [
    (re.compile(r"\s+"), " "),
    (re.compile(r"\d{6,}"), "{NUM}"),
    (re.compile(r"\d{2,}/\d{2,}"), "{NUM}"),
    (re.compile(r"\*+"), "*"),
]

KEYWORDS_TRANSFER = ["transfer", "move", "to chequing", "to checking", "between", "sweep"]
KEYWORDS_SALES = ["sales", "monthly sales", "deposit sales", "batch"]
KEYWORDS_BALANCE = ["balance adj", "balance adjustment", "adjustment"]


def normalize(desc: str) -> str:
    if not desc:
        return ""
    s = desc.lower().strip()
    for pat, rep in NORMALIZE_PATTERNS:
        s = pat.sub(rep, s)
    return s[:120]


def classify(desc: str) -> str:
    s = desc.lower()
    if any(k in s for k in KEYWORDS_TRANSFER):
        return 'transfer'
    if any(k in s for k in KEYWORDS_SALES):
        return 'sales_batch'
    if any(k in s for k in KEYWORDS_BALANCE):
        return 'balance_adjustment'
    return 'other'


def main():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        database=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD')
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        WITH categorized AS (
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE debit_amount > 0
              AND receipt_id IS NULL
              AND NOT (LOWER(description) LIKE '%pos purchase%' OR LOWER(description) LIKE '%point of sale%')
              AND NOT (LOWER(description) LIKE '%nsf%' OR LOWER(description) LIKE '%non-sufficient%')
              AND NOT (LOWER(description) LIKE '%service charge%' OR LOWER(description) LIKE '%fee%')
              AND NOT (LOWER(description) LIKE '%withdrawal%' OR LOWER(description) LIKE '%atm%')
              AND NOT (LOWER(description) LIKE '%transfer%')
        )
        SELECT * FROM categorized
    """)
    rows = cur.fetchall()

    buckets = defaultdict(list)
    for r in rows:
        norm = normalize(r['description'] or '')
        buckets[norm].append(r)

    # Rank by total amount
    ranked = sorted(buckets.items(), key=lambda kv: sum(x['debit_amount'] or 0 for x in kv[1]), reverse=True)
    
    print("Top clusters (Other expenses without receipts):")
    for norm_desc, items in ranked[:30]:
        total = sum(x['debit_amount'] or 0 for x in items)
        cls = classify(norm_desc)
        example = items[0]
        print(f"- ${total:,.2f} across {len(items)} tx | class={cls} | '{norm_desc[:80]}'")
        # Show 1-2 largest examples for sanity
        for ex in sorted(items, key=lambda x: x['debit_amount'] or 0, reverse=True)[:2]:
            print(f"    {ex['transaction_date']}  ${ex['debit_amount']:,.2f}  {ex['description'][:80]}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
