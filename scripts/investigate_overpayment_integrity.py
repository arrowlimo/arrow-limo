#!/usr/bin/env python3
"""Investigate overpayment integrity and confirmation deposit mismatches.

Goals:
  1. Verify overpaid charters (balance < 0) are not already refunded (negative payment rows).
  2. Identify charters with extreme overpayment ratios (paid_amount > 3x total_amount_due).
  3. Analyze confirmation email deposit amounts vs recorded payments; flag large deltas.
  4. Detect fragmentation (many small payments) vs single large payment inconsistencies.
  5. Produce manual_review list with reason codes.

Reason Codes:
  EXCESS_OVERPAY      paid_amount > 3 * total_amount_due
  LARGE_NEG_BAL       balance < -500
  NO_REFUND_FOUND     Overpaid but no negative payment rows
  DEPOSIT_MISMATCH    Sum(deposit emails) differs from payments total by >30% and >$200
  HIGH_FRAGMENTATION  payment_count >= 10 and avg_payment < total_amount_due * 0.05
  SUSPICIOUS_CONFIRM  Confirmation deposit > total_amount_due

Output: Printed report only (no DB writes).
"""

import os
import psycopg2
from collections import defaultdict
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


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
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE balance < 0 AND reserve_number IS NOT NULL
        ORDER BY balance ASC
        """
    )
    return cur.fetchall()


def fetch_payments(cur, reserves):
    cur.execute(
        """
        SELECT reserve_number, amount, payment_date, payment_key
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY payment_date
        """,
        (reserves,)
    )
    rows = cur.fetchall()
    by_reserve = defaultdict(list)
    for r in rows:
        by_reserve[r[0]].append(r)
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
    deposits = defaultdict(list)
    for rv, amt in rows:
        deposits[rv].append(amt)
    return deposits


def analyze():
    conn = get_conn()
    cur = conn.cursor()
    overpaid = fetch_overpaid_charters(cur)
    reserves = [row[1] for row in overpaid]
    payments_map = fetch_payments(cur, reserves)
    deposits_map = fetch_confirmation_deposits(cur, reserves)

    manual_review = []

    for charter_id, reserve_number, total_due, paid_amount, balance in overpaid:
        reasons = []
        payment_rows = payments_map.get(reserve_number, [])
        neg_payments = [p for p in payment_rows if p[1] < 0]
        payment_count = len(payment_rows)
        total_payment_sum = sum(p[1] for p in payment_rows)
        avg_payment = total_payment_sum / payment_count if payment_count else 0
        deposits = deposits_map.get(reserve_number, [])
        deposits_sum = sum(deposits) if deposits else 0

        # Sanity: paid_amount may differ from total_payment_sum if historical imports truncated; rely on DB field for ratio
        if total_due and float(paid_amount or 0) > float(total_due) * 3:
            reasons.append("EXCESS_OVERPAY")
        if balance < -500:
            reasons.append("LARGE_NEG_BAL")
        if balance < 0 and not neg_payments:
            reasons.append("NO_REFUND_FOUND")
        if deposits_sum > 0:
            # mismatch threshold: >30% and >$200 absolute difference vs payments sum
            diff = abs(deposits_sum - total_payment_sum)
            if total_payment_sum > 0:
                pct = diff / total_payment_sum
                if pct > 0.30 and diff > 200:
                    reasons.append("DEPOSIT_MISMATCH")
            else:
                # No payment but have deposit emails
                reasons.append("DEPOSIT_MISMATCH")
            if deposits_sum > total_due:
                reasons.append("SUSPICIOUS_CONFIRM")
        if payment_count >= 10 and total_due and avg_payment < float(total_due) * 0.05:
            reasons.append("HIGH_FRAGMENTATION")

        if reasons:
            manual_review.append({
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'total_due': float(total_due or 0),
                'paid_amount': float(paid_amount or 0),
                'balance': float(balance or 0),
                'payment_count': payment_count,
                'negative_payment_count': len(neg_payments),
                'deposits_sum': float(deposits_sum),
                'reasons': reasons,
            })

    cur.close(); conn.close()
    return manual_review


def main():
    review = analyze()
    print("=== Manual Review Candidates ===")
    print(f"Total flagged charters: {len(review)}")
    # Sort by severity: number of reasons then absolute negative balance
    review.sort(key=lambda r: (-len(r['reasons']), r['balance']))
    for r in review[:50]:
        print(
            f"reserve={r['reserve_number']} charter_id={r['charter_id']} due=${r['total_due']:.2f} "
            f"paid=${r['paid_amount']:.2f} bal=${r['balance']:.2f} pay_ct={r['payment_count']} "
            f"neg_pay={r['negative_payment_count']} deposits=${r['deposits_sum']:.2f} reasons={','.join(r['reasons'])}"
        )
    # Summary counts per reason
    from collections import Counter
    c = Counter()
    for r in review:
        for reason in r['reasons']:
            c[reason] += 1
    print("\nReason distribution:")
    for reason, count in c.most_common():
        print(f"  {reason}: {count}")
    print("\nSuggested remediation order:")
    print("  1. EXCESS_OVERPAY + NO_REFUND_FOUND (potential missing refund entries)")
    print("  2. DEPOSIT_MISMATCH (validate email deposit vs payments; create missing payment or adjust)")
    print("  3. HIGH_FRAGMENTATION (consider consolidation or audit rounding entries)")
    print("  4. SUSPICIOUS_CONFIRM (confirm if deposit email represents multi-charter or future booking prepayment)")


if __name__ == '__main__':
    main()
