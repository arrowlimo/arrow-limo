#!/usr/bin/env python3
"""
Reconcile lender_statement_transactions to banking_transactions.

Why: Our banking data now lives in banking_transactions (not just receipts).
This script matches lender statement rows to net banking transactions by amount
within a ±3 day window, preferring the 8314462 (vehicle loans) account when ties occur.

Outputs:
- reports/lender_bt_matches.csv
- reports/lender_bt_unmatched.csv

Usage:
  python scripts/reconcile_lender_to_banking_transactions.py
"""

import csv
import os
from typing import List, Dict, Any

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

PREFERRED_LOAN_ACCOUNT = '8314462'  # CIBC vehicle loans (not strictly used for ordering)

# Prefer the vehicle loans account when multiple banking candidates tie on amount/date
QUERY = f"""
WITH lender AS (
  SELECT id, txn_date, description, amount, balance
  FROM lender_statement_transactions
  WHERE COALESCE(ABS(amount),0) > 0.001
),
bt AS (
  SELECT transaction_id,
         transaction_date,
         account_number,
         description,
         vendor_extracted,
         debit_amount,
         credit_amount,
         (COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS net_amount
  FROM banking_transactions
),
matches AS (
  SELECT l.id AS lender_id,
         l.txn_date AS lender_date,
         l.description AS lender_desc,
         l.amount AS lender_amount,
         l.balance AS lender_balance,
         b.transaction_id,
         b.transaction_date,
         b.account_number,
         b.description AS bank_desc,
         b.vendor_extracted,
         b.debit_amount,
         b.credit_amount,
         b.net_amount,
         ABS(EXTRACT(EPOCH FROM (b.transaction_date::timestamp - l.txn_date::timestamp))) AS date_diff_seconds,
                 CASE WHEN b.debit_amount IS NOT NULL AND b.debit_amount > 0 THEN 0 ELSE 1 END AS account_pref,
                 CASE WHEN b.account_number = '{PREFERRED_LOAN_ACCOUNT}' THEN 0 ELSE 1 END AS loan_pref
  FROM lender l
  JOIN bt b
    ON b.transaction_date BETWEEN l.txn_date - INTERVAL '5 day' AND l.txn_date + INTERVAL '5 day'
   AND ABS(ABS(b.net_amount) - ABS(l.amount)) < 0.01
)
SELECT DISTINCT ON (lender_id)
       lender_id,
       lender_date,
       lender_desc,
       lender_amount,
       lender_balance,
       transaction_id,
       transaction_date,
       account_number,
       bank_desc,
       vendor_extracted,
       debit_amount,
       credit_amount,
       net_amount
FROM matches
ORDER BY lender_id, loan_pref ASC, account_pref ASC, date_diff_seconds ASC, transaction_id ASC;
"""


def export_csv(path: str, rows: List[Dict[str, Any]], headers: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow([r.get(h, '') for h in headers])


def main() -> None:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Basic counts to orient the user
    cur.execute("SELECT COUNT(*) FROM lender_statement_transactions")
    total_lender = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lender_statement_transactions WHERE COALESCE(ABS(amount),0) > 0.001")
    lender_nonzero = cur.fetchone()[0]

    # Fetch matches using banking_transactions
    cur.execute(QUERY)
    matched_rows = cur.fetchall()

    # Map by lender_id for quick lookup (pass A: individual rows)
    matched_by_id = {row[0]: row for row in matched_rows}

    # Load all candidate lender rows to split matched/unmatched
    cur.execute(
        """
        SELECT id, txn_date, description, amount, balance
        FROM lender_statement_transactions
        WHERE COALESCE(ABS(amount),0) > 0.001
        ORDER BY txn_date, id
        """
    )
    lender_rows = cur.fetchall()

    matched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    for id_, d, desc, amt, bal in lender_rows:
        m = matched_by_id.get(id_)
        if m:
            matched.append({
                'lender_id': id_,
                'lender_date': d,
                'lender_desc': desc,
                'lender_amount': float(amt) if amt is not None else None,
                'lender_balance': float(bal) if bal is not None else None,
                'bank_txn_id': m[5],
                'bank_date': m[6],
                'bank_account': m[7],
                'bank_desc': m[8],
                'bank_vendor': m[9],
                'bank_debit': float(m[10]) if m[10] is not None else None,
                'bank_credit': float(m[11]) if m[11] is not None else None,
                'bank_net': float(m[12]) if m[12] is not None else None,
            })
        else:
            unmatched.append({
                'lender_id': id_,
                'lender_date': d,
                'lender_desc': desc,
                'lender_amount': float(amt) if amt is not None else None,
                'lender_balance': float(bal) if bal is not None else None,
            })

    # Second pass: group unmatched lender rows by date and match the daily total to a bank txn
    if unmatched:
        unmatched_ids = [r['lender_id'] for r in unmatched]
        # Build grouped matching query
        grouped_query = f"""
        WITH lender_unmatched AS (
            SELECT id, txn_date, description, amount
            FROM lender_statement_transactions
            WHERE id = ANY(%s)
        ),
        lender_groups AS (
            SELECT txn_date,
                   ROUND(SUM(amount)::numeric, 2) AS total_amount,
                   ARRAY_AGG(id) AS lender_ids
            FROM lender_unmatched
            GROUP BY txn_date
        ),
        bt AS (
            SELECT transaction_id,
                   transaction_date,
                   account_number,
                   description,
                   vendor_extracted,
                   debit_amount,
                   credit_amount,
                   (COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS net_amount
            FROM banking_transactions
        ),
        matches AS (
            SELECT lg.txn_date,
                   lg.total_amount,
                   lg.lender_ids,
                   b.transaction_id,
                   b.transaction_date,
                   b.account_number,
                   b.description AS bank_desc,
                   b.vendor_extracted,
                   b.debit_amount,
                   b.credit_amount,
                   b.net_amount,
                   ABS(EXTRACT(EPOCH FROM (b.transaction_date::timestamp - lg.txn_date::timestamp))) AS date_diff_seconds,
          CASE WHEN b.debit_amount IS NOT NULL AND b.debit_amount > 0 THEN 0 ELSE 1 END AS account_pref,
          CASE WHEN b.account_number = '{PREFERRED_LOAN_ACCOUNT}' THEN 0 ELSE 1 END AS loan_pref
            FROM lender_groups lg
            JOIN bt b
          ON b.transaction_date BETWEEN lg.txn_date - INTERVAL '5 day' AND lg.txn_date + INTERVAL '5 day'
             AND ABS(ABS(b.net_amount) - ABS(lg.total_amount)) < 0.01
        )
        SELECT DISTINCT ON (txn_date)
               txn_date,
               total_amount,
               lender_ids,
               transaction_id,
               transaction_date,
               account_number,
               bank_desc,
               vendor_extracted,
               debit_amount,
               credit_amount,
               net_amount
        FROM matches
     ORDER BY txn_date, loan_pref ASC, account_pref ASC, date_diff_seconds ASC, transaction_id ASC;
     """
        cur.execute(grouped_query, (unmatched_ids,))
        grouped_matches = cur.fetchall()

        # Apply grouped matches: for each group, assign the bank txn to each lender_id still unmatched
    unmatched_index = {r['lender_id']: r for r in unmatched}
    for gm in grouped_matches:
            txn_date, total_amount, lender_ids, bank_txn_id, bank_date, bank_acct, bank_desc, bank_vendor, bank_debit, bank_credit, bank_net = gm
            for lid in lender_ids:
                if lid in unmatched_index:
                    r = unmatched_index.pop(lid)
                    matched.append({
                        'lender_id': lid,
                        'lender_date': r['lender_date'],
                        'lender_desc': r['lender_desc'],
                        'lender_amount': r['lender_amount'],
                        'lender_balance': r.get('lender_balance'),
                        'bank_txn_id': bank_txn_id,
                        'bank_date': bank_date,
                        'bank_account': bank_acct,
                        'bank_desc': bank_desc,
                        'bank_vendor': bank_vendor,
                        'bank_debit': float(bank_debit) if bank_debit is not None else None,
                        'bank_credit': float(bank_credit) if bank_credit is not None else None,
                        'bank_net': float(bank_net) if bank_net is not None else None,
                    })
    # Rebuild unmatched list from remaining index
    unmatched = list(unmatched_index.values())

    # Third pass: try pairing two bank debits whose net sum matches the lender daily total
    if unmatched:
        # Build date-group sums for remaining unmatched
        from collections import defaultdict
        grouped_by_date = defaultdict(list)
        for r in unmatched:
            grouped_by_date[r['lender_date']].append(r)

        # For each date, fetch nearby bank debits and try pair sums
        pair_matched_ids = set()
        for d, items in grouped_by_date.items():
            target_total = round(sum(abs(float(r['lender_amount'] or 0)) for r in items), 2)
            cur.execute(
                """
                SELECT transaction_id, transaction_date, account_number, description, vendor_extracted,
                       debit_amount, credit_amount,
                       (COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS net_amount
                  FROM banking_transactions
                 WHERE transaction_date BETWEEN %s - INTERVAL '5 day' AND %s + INTERVAL '5 day'
                   AND debit_amount IS NOT NULL AND debit_amount > 0
                ORDER BY transaction_date
                """,
                (d, d)
            )
            banks = cur.fetchall()
            # Try simple O(n^2) two-sum with tolerance
            tol = 0.01
            chosen = None
            n = len(banks)
            for i in range(min(n, 400)):
                for j in range(i+1, min(n, 400)):
                    ni = abs(float(banks[i][7] or 0))
                    nj = abs(float(banks[j][7] or 0))
                    if abs((ni + nj) - target_total) < tol:
                        chosen = (banks[i], banks[j])
                        break
                if chosen:
                    break
            if chosen:
                b1, b2 = chosen
                # Assign both bank txns to each lender row for that day (note: bank_txn_id becomes 'id1|id2')
                for r in items:
                    matched.append({
                        'lender_id': r['lender_id'],
                        'lender_date': r['lender_date'],
                        'lender_desc': r['lender_desc'],
                        'lender_amount': r['lender_amount'],
                        'lender_balance': r.get('lender_balance'),
                        'bank_txn_id': f"{b1[0]}|{b2[0]}",
                        'bank_date': b1[1],
                        'bank_account': f"{b1[2]}+{b2[2]}",
                        'bank_desc': f"{b1[3]} + {b2[3]}",
                        'bank_vendor': f"{b1[4]} + {b2[4]}",
                        'bank_debit': float((b1[5] or 0) + (b2[5] or 0)),
                        'bank_credit': float((b1[6] or 0) + (b2[6] or 0)),
                        'bank_net': float((b1[7] or 0) + (b2[7] or 0)),
                    })
                    pair_matched_ids.add(r['lender_id'])

        if pair_matched_ids:
            unmatched = [r for r in unmatched if r['lender_id'] not in pair_matched_ids]

    # Fourth pass: relaxed single match with slightly wider amount tolerance (0.02)
    if unmatched:
        relaxed_matched_ids = set()
        new_unmatched: List[Dict[str, Any]] = []
        for r in unmatched:
            d = r['lender_date']
            amt = r.get('lender_amount')
            if amt is None:
                new_unmatched.append(r)
                continue
            cur.execute(
                """
                SELECT transaction_id, transaction_date, account_number, description, vendor_extracted,
                       debit_amount, credit_amount,
                       (COALESCE(credit_amount,0) - COALESCE(debit_amount,0)) AS net_amount,
                       ABS(EXTRACT(EPOCH FROM (transaction_date::timestamp - %s::timestamp))) AS date_diff_seconds,
                       CASE WHEN account_number = %s THEN 0 ELSE 1 END AS loan_pref,
                       CASE WHEN debit_amount IS NOT NULL AND debit_amount > 0 THEN 0 ELSE 1 END AS account_pref
                  FROM banking_transactions
                 WHERE transaction_date BETWEEN %s - INTERVAL '5 day' AND %s + INTERVAL '5 day'
                   AND ABS(ABS((COALESCE(credit_amount,0) - COALESCE(debit_amount,0))) - ABS(%s)) < 0.02
                 ORDER BY loan_pref ASC, account_pref ASC, date_diff_seconds ASC, transaction_id ASC
                 LIMIT 1
                """,
                (d, PREFERRED_LOAN_ACCOUNT, d, d, amt)
            )
            row = cur.fetchone()
            if row:
                (bank_txn_id, bank_date, bank_acct, bank_desc, bank_vendor,
                 bank_debit, bank_credit, bank_net, *_rest) = row
                matched.append({
                    'lender_id': r['lender_id'],
                    'lender_date': r['lender_date'],
                    'lender_desc': r['lender_desc'],
                    'lender_amount': r['lender_amount'],
                    'lender_balance': r.get('lender_balance'),
                    'bank_txn_id': bank_txn_id,
                    'bank_date': bank_date,
                    'bank_account': bank_acct,
                    'bank_desc': bank_desc,
                    'bank_vendor': bank_vendor,
                    'bank_debit': float(bank_debit) if bank_debit is not None else None,
                    'bank_credit': float(bank_credit) if bank_credit is not None else None,
                    'bank_net': float(bank_net) if bank_net is not None else None,
                })
                relaxed_matched_ids.add(r['lender_id'])
            else:
                new_unmatched.append(r)

        if relaxed_matched_ids:
            unmatched = new_unmatched

    print("=== LENDER \u2194 BANKING TRANSACTIONS RECON ===")
    print(f"Total lender rows: {total_lender}")
    print(f"Non-zero amount rows: {lender_nonzero}")
    print(f"Matched: {len(matched)}")
    print(f"Unmatched: {len(unmatched)}")

    # Export CSVs for review
    export_csv(
        os.path.join('reports', 'lender_bt_matches.csv'),
        matched,
        [
            'lender_id', 'lender_date', 'lender_desc', 'lender_amount', 'lender_balance',
            'bank_txn_id', 'bank_date', 'bank_account', 'bank_desc', 'bank_vendor',
            'bank_debit', 'bank_credit', 'bank_net'
        ],
    )
    export_csv(
        os.path.join('reports', 'lender_bt_unmatched.csv'),
        unmatched,
        ['lender_id', 'lender_date', 'lender_desc', 'lender_amount', 'lender_balance'],
    )
    print("Wrote reports/lender_bt_matches.csv and reports/lender_bt_unmatched.csv")

    # Quick by-account summary of matches (optional)
    if matched:
        by_acct: Dict[str, int] = {}
        for r in matched:
            by_acct[r['bank_account']] = by_acct.get(r['bank_account'], 0) + 1
        print("\nMatched by account_number:")
        for acct, cnt in sorted(by_acct.items()):
            print(f"  {acct}: {cnt}")

    # Unmatched analysis to guide next steps
    if unmatched:
        from collections import Counter
        amt_freq = Counter()
        kinds = Counter()
        for r in unmatched:
            amt = r.get('lender_amount')
            if amt is not None:
                amt_freq[round(abs(float(amt)), 2)] += 1
            desc = (r.get('lender_desc') or '').upper()
            if 'PMT' in desc or 'PAYMENT' in desc:
                kinds['payment_like'] += 1
            elif 'INT' in desc or 'INTEREST' in desc:
                kinds['interest_like'] += 1
            elif 'NSF' in desc or 'RETURN' in desc:
                kinds['nsf_like'] += 1
            else:
                kinds['other'] += 1

        print("\nTop unmatched amounts (abs, count):")
        for amount, cnt in amt_freq.most_common(10):
            print(f"  {amount:,.2f}: {cnt}")

        print("\nUnmatched description types:")
        for k, v in kinds.items():
            print(f"  {k}: {v}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
