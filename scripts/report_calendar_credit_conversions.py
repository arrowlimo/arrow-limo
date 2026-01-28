import os
import psycopg2
import json
import datetime

"""Report calendar_import credit conversions without deleting payments.
Lists: credit rows created, associated payment (still present or missing), and charter cancellation status.
"""

CREDIT_REASON = 'CANCELLED_DEPOSIT'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT credit_id, source_reserve_number, source_charter_id, credit_amount, remaining_balance, created_date
        FROM charter_credit_ledger
        WHERE created_by = 'calendar_import' AND credit_reason = %s
        ORDER BY created_date DESC, credit_id
    """, (CREDIT_REASON,))
    credits = cur.fetchall()

    report = []
    missing_payments = []
    totals = {'credits_count': 0, 'credits_sum': 0.0, 'payments_missing': 0}

    for credit_id, reserve_number, charter_id, credit_amt, remaining_bal, created_dt in credits:
        # Find charter cancellation state
        cur.execute("SELECT cancelled, paid_amount, balance, total_amount_due FROM charters WHERE reserve_number=%s", (reserve_number,))
        ch = cur.fetchone()
        cancelled = ch[0] if ch else None
        paid_amount = ch[1] if ch else None
        balance = ch[2] if ch else None
        total_due = ch[3] if ch else None

        # Attempt to locate flagged payment (admin_notes marker) with similar amount
        try:
            cur.execute(
                """
                SELECT payment_id, amount, payment_date, admin_notes
                FROM payments
                WHERE reserve_number = %s
                  AND amount = %s
                ORDER BY payment_date
                LIMIT 1
                """,
                (reserve_number, credit_amt)
            )
        except Exception:
            conn.rollback()
            cur.execute(
                """
                SELECT payment_id, amount, payment_date, NULL as admin_notes
                FROM payments
                WHERE reserve_number = %s
                  AND amount = %s
                ORDER BY payment_date
                LIMIT 1
                """,
                (reserve_number, credit_amt)
            )
        pay = cur.fetchone()

        payment_present = pay is not None
        payment_id = pay[0] if payment_present else None
        admin_notes = pay[3] if payment_present else None

        if not payment_present:
            missing_payments.append(reserve_number)
            totals['payments_missing'] += 1

        report.append({
            'credit_id': credit_id,
            'reserve_number': reserve_number,
            'charter_id': charter_id,
            'credit_amount': float(credit_amt),
            'remaining_balance': float(remaining_bal),
            'created_date': created_dt.isoformat() if created_dt else None,
            'charter_cancelled': cancelled,
            'charter_paid_amount': float(paid_amount) if paid_amount is not None else None,
            'charter_balance': float(balance) if balance is not None else None,
            'charter_total_due': float(total_due) if total_due is not None else None,
            'payment_present': payment_present,
            'payment_id': payment_id,
            'payment_admin_notes': admin_notes,
        })

        totals['credits_count'] += 1
        totals['credits_sum'] += float(credit_amt)

    cur.close(); conn.close()

    out = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'totals': totals,
        'missing_payment_reserve_numbers': missing_payments,
        'entries': report
    }
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
