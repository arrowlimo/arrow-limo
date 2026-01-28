#!/usr/bin/env python
"""
Final reconciliation status report after all payment matching fixes.
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
    print("FINAL RECONCILIATION STATUS REPORT")
    print("=" * 80)
    print()
    
    # Payment matching status
    print("PAYMENT MATCHING STATUS")
    print("-" * 80)
    cur.execute("""
        SELECT COUNT(*) FROM payments
    """)
    total_payments = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cp.amount), 0)
        FROM charter_payments cp
    """)
    matched_count, matched_sum = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(p.payment_amount, p.amount)), 0)
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
    """)
    unmatched_count, unmatched_sum = cur.fetchone()
    
    match_rate = (matched_count / total_payments * 100) if total_payments > 0 else 0
    
    print(f"Total payments: {total_payments:,}")
    print(f"Matched to charters: {matched_count:,} ({match_rate:.1f}%)")
    print(f"  Total matched amount: ${float(matched_sum):,.2f}")
    print(f"Unmatched: {unmatched_count:,} ({100-match_rate:.1f}%)")
    print(f"  Total unmatched amount: ${float(unmatched_sum):,.2f}")
    print()
    
    # Charter balance distribution
    print("CHARTER BALANCE DISTRIBUTION (Non-Cancelled)")
    print("-" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER(WHERE balance > 0.01) AS positive,
            COUNT(*) FILTER(WHERE ABS(balance) <= 0.01) AS zero,
            COUNT(*) FILTER(WHERE balance < -0.01) AS negative,
            COALESCE(SUM(balance) FILTER(WHERE balance > 0.01), 0) AS positive_sum,
            COALESCE(SUM(balance) FILTER(WHERE balance < -0.01), 0) AS negative_sum,
            COUNT(*) AS total
        FROM charters
        WHERE (cancelled IS NULL OR cancelled = FALSE)
    """)
    pos, zero, neg, pos_sum, neg_sum, total = cur.fetchone()
    
    print(f"Total non-cancelled charters: {total:,}")
    print(f"  Positive (owed to you): {pos:,} ({pos/total*100:.1f}%) = ${float(pos_sum):,.2f}")
    print(f"  Zero balance: {zero:,} ({zero/total*100:.1f}%)")
    print(f"  Negative (credits): {neg:,} ({neg/total*100:.1f}%) = ${float(neg_sum):,.2f}")
    print()
    
    # Top outstanding balances
    print("TOP 20 OUTSTANDING BALANCES (Money Owed to You)")
    print("-" * 80)
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance,
               (SELECT COUNT(*) FROM charter_payments cp WHERE cp.charter_id = c.reserve_number::text) AS payment_count
        FROM charters c
        WHERE c.balance > 0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        ORDER BY c.balance DESC
        LIMIT 20
    """)
    for i, row in enumerate(cur.fetchall(), 1):
        reserve, date, total, paid, balance, pay_cnt = row
        print(f"{i:2}. {reserve} ({date}): ${float(balance):,.2f} outstanding")
        print(f"    Total: ${float(total or 0):,.2f}, Paid: ${float(paid or 0):,.2f}, Payments: {pay_cnt}")
    print()
    
    # Top credits
    print("TOP 20 CREDITS (Overpayments/Customer Credits)")
    print("-" * 80)
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.paid_amount, c.balance,
               (SELECT COUNT(*) FROM charter_payments cp WHERE cp.charter_id = c.reserve_number::text) AS payment_count,
               EXISTS(SELECT 1 FROM charter_refunds cr WHERE cr.charter_id::text = c.reserve_number::text) AS has_refund
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        ORDER BY c.balance ASC
        LIMIT 20
    """)
    for i, row in enumerate(cur.fetchall(), 1):
        reserve, date, total, paid, balance, pay_cnt, has_refund = row
        refund_flag = " [REFUND ISSUED]" if has_refund else ""
        print(f"{i:2}. {reserve} ({date}): ${float(balance):,.2f} credit{refund_flag}")
        print(f"    Total: ${float(total or 0):,.2f}, Paid: ${float(paid or 0):,.2f}, Payments: {pay_cnt}")
    print()
    
    # Data completeness
    print("DATA COMPLETENESS CHECK")
    print("-" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) FILTER(WHERE total_amount_due IS NULL OR total_amount_due = 0) AS missing_total,
            COUNT(*) FILTER(WHERE paid_amount IS NULL) AS missing_paid,
            COUNT(*) AS total
        FROM charters
        WHERE (cancelled IS NULL OR cancelled = FALSE)
    """)
    missing_total, missing_paid, total_charters = cur.fetchone()
    
    print(f"Charters missing total_amount_due: {missing_total:,} of {total_charters:,} ({missing_total/total_charters*100:.1f}%)")
    print(f"Charters missing paid_amount: {missing_paid:,} of {total_charters:,} ({missing_paid/total_charters*100:.1f}%)")
    print()
    
    # Refund tracking
    print("REFUND TRACKING")
    print("-" * 80)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM charter_refunds
    """)
    refund_count, refund_sum = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(DISTINCT c.reserve_number)
        FROM charters c
        WHERE c.balance < -0.01
        AND (c.cancelled IS NULL OR c.cancelled = FALSE)
        AND EXISTS(SELECT 1 FROM charter_refunds cr WHERE cr.charter_id::text = c.reserve_number::text)
    """)
    credits_with_refunds = cur.fetchone()[0]
    
    print(f"Total refunds issued: {refund_count:,} (${float(refund_sum):,.2f})")
    print(f"Credits with documented refunds: {credits_with_refunds:,} of {neg:,} ({credits_with_refunds/neg*100:.1f}%)")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"✓ Payment matching: {match_rate:.1f}% complete")
    print(f"✓ Outstanding receivables: ${float(pos_sum):,.2f}")
    print(f"✓ Customer credits: ${float(neg_sum):,.2f}")
    print(f"⚠ Data completeness: {missing_total:,} charters missing charge details")
    print(f"⚠ Unmatched payments: {unmatched_count:,} (${float(unmatched_sum):,.2f}) need investigation")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
