#!/usr/bin/env python
"""
Quick analysis:
1. Non-cancelled charters balance distribution (zero, positive, negative)
2. Count of unmatched payments (payments not linked to charter_payments)
"""
import psycopg2


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 80)
    print("NON-CANCELLED CHARTERS BALANCE DISTRIBUTION")
    print("=" * 80)

    # Balance distribution for non-cancelled
    cur.execute("""
        SELECT 
          COUNT(*) FILTER(WHERE COALESCE(balance,0) = 0) AS zero_bal,
          COUNT(*) FILTER(WHERE balance > 0.01) AS positive_bal,
          COUNT(*) FILTER(WHERE balance < -0.01) AS negative_bal,
          COUNT(*) AS total
        FROM charters
        WHERE (cancelled IS NULL OR cancelled = FALSE)
    """)
    zero, positive, negative, total = cur.fetchone()

    print(f"\nTotal non-cancelled charters: {total:,}")
    print(f"  Zero balance (±$0.01):  {zero:,} ({100*zero/total:.1f}%)")
    print(f"  Positive balance:       {positive:,} ({100*positive/total:.1f}%)")
    print(f"  Negative balance:       {negative:,} ({100*negative/total:.1f}%)")

    # Sum of positive and negative
    cur.execute("""
        SELECT 
          COALESCE(SUM(balance) FILTER(WHERE balance > 0.01), 0) AS positive_sum,
          COALESCE(SUM(balance) FILTER(WHERE balance < -0.01), 0) AS negative_sum
        FROM charters
        WHERE (cancelled IS NULL OR cancelled = FALSE)
    """)
    pos_sum, neg_sum = cur.fetchone()
    print(f"\n  Positive balance sum:   ${float(pos_sum):,.2f}")
    print(f"  Negative balance sum:   ${float(neg_sum):,.2f}")

    print("\n" + "=" * 80)
    print("UNMATCHED PAYMENTS ANALYSIS")
    print("=" * 80)

    # Unmatched payments: payments table rows not in charter_payments
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(payment_amount,amount,0)),0)
        FROM payments p
        WHERE NOT EXISTS (
          SELECT 1 FROM charter_payments cp
          WHERE cp.payment_id = p.payment_id
        )
    """)
    unmatched_count, unmatched_sum = cur.fetchone()

    # Total payments
    cur.execute("SELECT COUNT(*), COALESCE(SUM(COALESCE(payment_amount,amount,0)),0) FROM payments")
    total_payments, total_sum = cur.fetchone()

    print(f"\nTotal payments in table: {total_payments:,}")
    print(f"  Matched to charters:   {total_payments - unmatched_count:,} ({100*(total_payments-unmatched_count)/total_payments:.1f}%)")
    print(f"  Unmatched:             {unmatched_count:,} ({100*unmatched_count/total_payments:.1f}%)")

    print(f"\nPayment amounts:")
    print(f"  Total (non-null):      ${float(total_sum):,.2f}")
    print(f"  Unmatched (non-null):  ${float(unmatched_sum):,.2f}")

    # Check how many payments have NULL amounts
    cur.execute("SELECT COUNT(*) FROM payments WHERE payment_amount IS NULL AND amount IS NULL")
    null_amounts = cur.fetchone()[0]
    print(f"\nPayments with NULL amounts: {null_amounts:,} ({100*null_amounts/total_payments:.1f}%)")

    print("\n" + "=" * 80)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
