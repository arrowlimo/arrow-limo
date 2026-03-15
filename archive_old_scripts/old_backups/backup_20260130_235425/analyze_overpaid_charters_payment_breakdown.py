#!/usr/bin/env python3
"""Detailed breakdown of overpaid charters and their applied payments.

Focus:
  - Enumerate every charter where paid_amount > total_amount_due (or balance < 0)
  - Include cancellation status (cancelled flag, status field if present)
  - List all applied payments with key metadata (id, amount, date, key prefix)
  - Flag potential duplication/misallocation patterns:
        * Duplicate signature: (reserve_number, payment_date, amount)
        * Same payment_key repeated
        * Excess ratio paid / due > 1.30 (configurable) or absolute overpay > $50
  - Distinguish cancelled vs active overpaid charters
  - Surface e-transfer derived payments (payment_key LIKE 'ETR:%') separately
  - Show recommendation: CREDIT_LEDGER, REFUND_REVIEW, SPLIT_ALLOCATION, or VERIFY_DEPOSIT

No writes performed; read-only analysis.

Rationale for user question:
User reported previous state where only cancelled runs had balances; now broad overpayments appear.
Script helps confirm whether new e-transfer payment ingestion introduced duplicate or misallocated rows.

Exit codes:
  0 success
  2 partial (DB errors but some output)

"""

import os
import csv
import psycopg2
from collections import defaultdict, Counter
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

OVERPAY_RATIO_THRESHOLD = 1.30  # >130% of due
OVERPAY_ABSOLUTE_THRESHOLD = 50  # dollars
LARGE_ETR_SINGLE_THRESHOLD = 2500  # single e-transfer suggesting multi-charter allocation
MULTI_CHARTER_WINDOW_DAYS = 30
CSV_OUTPUT_PATH = "l:/limo/reports/overpaid_charters_breakdown.csv"


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_overpaid_charters(cur):
        cur.execute(
                """
                SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance,
                             COALESCE(cancelled, FALSE) AS cancelled,
                             COALESCE(status, '') AS status,
                             client_id, charter_date
                FROM charters
                WHERE reserve_number IS NOT NULL
                    AND paid_amount > total_amount_due  -- direct overpay condition
                ORDER BY (paid_amount - total_amount_due) DESC
                """
        )
        return cur.fetchall()


def fetch_payments_for_reserves(cur, reserves):
    cur.execute(
        """
        SELECT payment_id, reserve_number, amount, payment_date, payment_key, created_at
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY reserve_number, payment_date, payment_id
        """,
        (reserves,)
    )
    rows = cur.fetchall()
    by_reserve = defaultdict(list)
    for r in rows:
        by_reserve[r[1]].append(r)
    return by_reserve


def fetch_confirmation_deposits(cur, reserves):
    cur.execute(
        """
        SELECT matched_account_number AS reserve_number, amount
        FROM email_financial_events
        WHERE source='outlook_charter_confirmation'
          AND matched_account_number = ANY(%s)
          AND amount IS NOT NULL
        """,
        (reserves,)
    )
    rows = cur.fetchall()
    m = defaultdict(list)
    for rv, amt in rows:
        m[rv].append(float(amt))
    return m


def fetch_other_client_charters(cur, client_id, base_date):
    cur.execute(
        """
        SELECT reserve_number, charter_id, total_amount_due, paid_amount, balance, charter_date
        FROM charters
        WHERE client_id = %s
          AND charter_date BETWEEN %s AND %s
          AND reserve_number IS NOT NULL
        """,
        (client_id, base_date - timedelta(days=MULTI_CHARTER_WINDOW_DAYS), base_date + timedelta(days=MULTI_CHARTER_WINDOW_DAYS))
    )
    return cur.fetchall()


def analyze():
    conn = get_conn()
    cur = conn.cursor()
    overpaid = fetch_overpaid_charters(cur)
    if not overpaid:
        print("No overpaid charters found.")
        cur.close(); conn.close()
        return []

    reserves = [row[1] for row in overpaid]
    payments_map = fetch_payments_for_reserves(cur, reserves)
    confirmation_map = fetch_confirmation_deposits(cur, reserves)

    results = []
    for charter_id, reserve_number, total_due, paid_amount, balance, cancelled, status, client_id, charter_date in overpaid:
        payments = payments_map.get(reserve_number, [])
        # Build duplicate signatures
        signature_counts = Counter()
        key_counts = Counter()
        etransfer_total = 0.0
        largest_single_etr = 0.0
        etr_rows = 0
        single_large_etr_rows = []
        for payment_id, rv, amount, pdate, pkey, created_at in payments:
            sig = (rv, pdate, float(amount))
            signature_counts[sig] += 1
            if pkey:
                key_counts[pkey] += 1
            if pkey and pkey.startswith("ETR:"):
                etransfer_total += float(amount)
                etr_rows += 1
                if float(amount) > largest_single_etr:
                    largest_single_etr = float(amount)
                if float(amount) >= LARGE_ETR_SINGLE_THRESHOLD:
                    single_large_etr_rows.append((payment_id, float(amount), pdate, pkey))

        duplicate_signatures = [s for s, c in signature_counts.items() if c > 1]
        duplicate_keys = [k for k, c in key_counts.items() if c > 1]

        overpay_delta = float(paid_amount or 0) - float(total_due or 0)
        ratio = (float(paid_amount or 0) / float(total_due or 1)) if total_due else 0

        # Recommendation logic
        recommendation = []
        if cancelled:
            recommendation.append("VERIFY_DEPOSIT_NONREFUNDABLE")
        if ratio > OVERPAY_RATIO_THRESHOLD or overpay_delta > OVERPAY_ABSOLUTE_THRESHOLD:
            if not cancelled:
                recommendation.append("CREDIT_LEDGER")
        if duplicate_signatures or duplicate_keys:
            recommendation.append("DUPLICATE_CHECK")
        if etransfer_total > 0 and (etransfer_total > float(total_due) * 1.2):
            recommendation.append("SPLIT_ALLOCATION_REVIEW")
        zero_due_flag = (float(total_due or 0) == 0.0)
        if zero_due_flag:
            recommendation.append("MISSING_CHARGES_OR_PREPAY")

        confirmation_sum = sum(confirmation_map.get(reserve_number, []))
        if confirmation_sum and confirmation_sum > float(total_due or 0) * 1.2:
            recommendation.append("CONFIRMATION_EXCEEDS_DUE")

        # Multi-charter prepayment detection: other charters for same client in window with unpaid balances
        multi_charter_candidates = []
        if client_id and (single_large_etr_rows or etransfer_total > float(total_due) * 2):
            other = fetch_other_client_charters(cur, client_id, charter_date or date.today())
            for o_reserve, o_id, o_due, o_paid, o_balance, o_date in other:
                if o_reserve == reserve_number:
                    continue
                # looking for charters with positive balance (still owing) or due>0 but paid<due
                if float(o_due or 0) > 0 and (float(o_paid or 0) < float(o_due or 0)):
                    multi_charter_candidates.append((o_reserve, float(o_due or 0) - float(o_paid or 0)))
        if multi_charter_candidates:
            recommendation.append("REALLOCATE_TO_MULTI_CHARTERS")

        results.append({
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'total_due': float(total_due or 0),
            'paid_amount': float(paid_amount or 0),
            'balance': float(balance or 0),
            'overpay_delta': overpay_delta,
            'ratio': ratio,
            'cancelled': bool(cancelled),
            'status': status,
            'payment_rows': payments,
            'duplicate_signatures': duplicate_signatures,
            'duplicate_keys': duplicate_keys,
            'recommendation': recommendation,
            'etransfer_total': etransfer_total,
            'largest_single_etr': largest_single_etr,
            'single_large_etr_rows': single_large_etr_rows,
            'confirmation_sum': confirmation_sum,
            'multi_charter_candidates': multi_charter_candidates,
            'zero_due_flag': zero_due_flag,
        })

    cur.close(); conn.close()
    return results


def print_summary(results):
    print("=== Overpaid Charter Payment Breakdown ===")
    print(f"Total overpaid charters: {len(results)}")
    cancelled_ct = sum(1 for r in results if r['cancelled'])
    active_ct = len(results) - cancelled_ct
    print(f"Cancelled overpaid: {cancelled_ct} | Active overpaid: {active_ct}")

    dup_sig_ct = sum(1 for r in results if r['duplicate_signatures'])
    dup_key_ct = sum(1 for r in results if r['duplicate_keys'])
    print(f"Potential duplicate signatures: {dup_sig_ct} | duplicate keys: {dup_key_ct}")

    high_ratio_ct = sum(1 for r in results if r['ratio'] > OVERPAY_RATIO_THRESHOLD)
    print(f"Ratio > {OVERPAY_RATIO_THRESHOLD:.2f}: {high_ratio_ct}")

    # Show top 25 by overpay delta
    results.sort(key=lambda r: r['overpay_delta'], reverse=True)
    print("\nTop 25 overpay deltas:")
    for r in results[:25]:
        print(
            f"reserve={r['reserve_number']} charter_id={r['charter_id']} due=${r['total_due']:.2f} "
            f"paid=${r['paid_amount']:.2f} overpay=${r['overpay_delta']:.2f} ratio={r['ratio']:.2f} "
            f"cancelled={r['cancelled']} dupsig={len(r['duplicate_signatures'])} dupkey={len(r['duplicate_keys'])} "
            f"reco={','.join(r['recommendation']) or 'NONE'}"
        )

    # Detailed block for first 5 severe cases
    print("\nDetailed payment rows for first 5 severe cases:")
    for r in results[:5]:
        print(
            f"\n--- reserve {r['reserve_number']} (charter_id {r['charter_id']}) overpay ${r['overpay_delta']:.2f} ratio {r['ratio']:.2f} cancelled={r['cancelled']} ---"
        )
        for payment_id, rv, amount, pdate, pkey, created_at in r['payment_rows']:
            flag = ''
            sig = (rv, pdate, float(amount))
            if sig in r['duplicate_signatures']:
                flag = 'DUP_SIG'
            if pkey and pkey in r['duplicate_keys']:
                flag = (flag + ' DUP_KEY').strip()
            if pkey and pkey.startswith('ETR:'):
                flag = (flag + ' ETRANSFER').strip()
            print(
                f"  payment_id={payment_id} date={pdate} amount=${float(amount):.2f} key={pkey or ''} {flag}".rstrip()
            )

    print("\nRecommendation meanings:")
    print("  VERIFY_DEPOSIT_NONREFUNDABLE: Cancelled charter with excess; confirm deposit retention policy.")
    print("  CREDIT_LEDGER: Active charter overpaid; move excess into client credit ledger for future use.")
    print("  DUPLICATE_CHECK: Potential duplicate payment rows sharing signature or key.")
    print("  SPLIT_ALLOCATION_REVIEW: Large e-transfer total suggests funds meant for multiple charters.")
    print("  MISSING_CHARGES_OR_PREPAY: Paid >0 while total_due=0 or charges missing; reconstruct or credit.")
    print("  CONFIRMATION_EXCEEDS_DUE: Confirmation email deposit sum far exceeds stated charges.")
    print("  REALLOCATE_TO_MULTI_CHARTERS: Candidate excess to redistribute among other unpaid charters for same client.")

    # CSV export
    try:
        os.makedirs(os.path.dirname(CSV_OUTPUT_PATH), exist_ok=True)
        with open(CSV_OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'reserve_number','charter_id','total_due','paid_amount','overpay_delta','ratio','cancelled','status',
                'etransfer_total','largest_single_etr','confirmation_sum','dup_sig_ct','dup_key_ct','zero_due_flag',
                'recommendations','multi_charter_candidates_count'
            ])
            for r in results:
                writer.writerow([
                    r['reserve_number'], r['charter_id'], f"{r['total_due']:.2f}", f"{r['paid_amount']:.2f}", f"{r['overpay_delta']:.2f}", f"{r['ratio']:.2f}",
                    r['cancelled'], r['status'], f"{r['etransfer_total']:.2f}", f"{r['largest_single_etr']:.2f}", f"{r['confirmation_sum']:.2f}",
                    len(r['duplicate_signatures']), len(r['duplicate_keys']), r['zero_due_flag'], ';'.join(r['recommendation']),
                    len(r['multi_charter_candidates'])
                ])
        print(f"\nCSV exported: {CSV_OUTPUT_PATH}")
    except Exception as e:
        print(f"CSV export failed: {e}")


def main():
    try:
        results = analyze()
        print_summary(results)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(2)


if __name__ == "__main__":
    main()
