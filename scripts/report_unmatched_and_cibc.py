#!/usr/bin/env python3
"""
Unmatched charter payment analysis and CIBC export for manual review.
- Summarize unlinked payments by payment_method and detect likely multi-charter allocations via charter_payment_references
- Identify CIBC accounts and which holds Square auto-deposits (counts by 'SQUARE' description)
- List unmatched CIBC banking credits likely related to Square/Interac and export full banking rows CSV
- Verify Square payment_keys exist as payment_key in payments and look for wrong-column ingestion
Outputs:
  reports/unlinked_payments_summary.csv
  reports/cibc_candidates_unmatched.csv
  reports/cibc_full_export.csv
  reports/square_key_verification.csv
"""
import os, csv
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

OUT1 = r"l:/limo/reports/unlinked_payments_summary.csv"
OUT2 = r"l:/limo/reports/cibc_candidates_unmatched.csv"
OUT3 = r"l:/limo/reports/cibc_full_export.csv"
OUT4 = r"l:/limo/reports/square_key_verification.csv"
OUT5 = r"l:/limo/reports/cibc_account_square_counts.csv"
OUT6 = r"l:/limo/reports/cibc_accounts.csv"
OUT7 = r"l:/limo/reports/multi_charter_payments.csv"
OUT8 = r"l:/limo/reports/unlinked_with_hint_ids.csv"

# Load environment (workspace .env first)
load_dotenv('l:/limo/.env'); load_dotenv()

DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
# Fallback to known default used elsewhere if not provided
DB_PASSWORD = os.environ.get('DB_PASSWORD','***REMOVED***')
DB_HOST = os.environ.get('DB_HOST','localhost')
DB_PORT = int(os.environ.get('DB_PORT','5432'))

SQUARE_HINTS = ['SQUARE', 'SQ ', 'SQUARE CANADA', 'SQC']
ETRANS_HINTS = ['INTERAC', 'E-TRANSFER', 'ETRF', 'EMT']


def main():
    os.makedirs('l:/limo/reports', exist_ok=True)
    with psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Unlinked payments by method and top note hints
            cur.execute("""
                SELECT COALESCE(LOWER(payment_method),'unknown') AS method,
                       COUNT(*) AS cnt,
                       COALESCE(SUM(amount),0) AS total
                  FROM payments
                 WHERE reserve_number IS NULL AND amount > 0
                 GROUP BY method
                 ORDER BY cnt DESC
            """)
            summary = cur.fetchall()
            with open(OUT1, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['method','unlinked_count','unlinked_total'])
                for r in summary:
                    w.writerow([r['method'], r['cnt'], float(r['total'])])

            # 2) Multi-charter applied payments (if reference table exists)
            cur.execute("SELECT to_regclass('public.charter_payment_references')")
            has_refs = cur.fetchone()['to_regclass'] is not None
            multi = []
            if has_refs:
                cur.execute("""
                    SELECT p.payment_id, p.payment_key, p.payment_method,
                           COUNT(DISTINCT cpr.charter_id) AS charter_count,
                           SUM(cpr.amount_applied) AS applied_total
                      FROM charter_payment_references cpr
                      JOIN payments p ON p.payment_id=cpr.payment_id
                  GROUP BY p.payment_id, p.payment_key, p.payment_method
                    HAVING COUNT(DISTINCT cpr.charter_id) > 1
                  ORDER BY charter_count DESC
                  LIMIT 200
                """)
                multi = cur.fetchall()

            # 3) Identify CIBC accounts and Square auto-deposit accounts by frequency of 'SQUARE' credits
            cur.execute("""
                SELECT bank_id, institution_name, account_number, account_name
                  FROM bank_accounts
                 WHERE institution_name ILIKE '%CIBC%'
                 ORDER BY account_name
            """)
            cibc_accounts = cur.fetchall()
            cibc_ids = [r['bank_id'] for r in cibc_accounts]
            # Write CIBC accounts file
            with open(OUT6, 'w', newline='', encoding='utf-8') as f:
                if cibc_accounts:
                    w = csv.DictWriter(f, fieldnames=list(cibc_accounts[0].keys()))
                    w.writeheader(); w.writerows(cibc_accounts)
                else:
                    f.write('')

            square_counts = []
            if cibc_ids:
                cur.execute(
                    """
                    SELECT bank_id, COUNT(*) AS sq_count
                      FROM banking_transactions
                     WHERE bank_id = ANY(%s) AND UPPER(description) LIKE '%%SQUARE%%'
                  GROUP BY bank_id ORDER BY sq_count DESC
                    """,
                    (cibc_ids,)
                )
                square_counts = cur.fetchall()
                # Write Square auto-deposit counts by CIBC bank account
                with open(OUT5, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f); w.writerow(['bank_id','account_number','account_name','square_count'])
                    acct_map = {r['bank_id']: r for r in cibc_accounts}
                    for r in square_counts:
                        a = acct_map.get(r['bank_id']) or {}
                        w.writerow([r['bank_id'], a.get('account_number',''), a.get('account_name',''), r['sq_count']])
            # 4) Unmatched CIBC credits likely to be customer payments (Square/Interac)
            #    Consider unmatched if there is NO receipt on the same date with similar inflow amount
            #    Use receipts_finance_view if available
            cur.execute("SELECT to_regclass('public.receipts_finance_view')")
            has_rv = cur.fetchone()['to_regclass'] is not None
            cibc_unmatched = []
            if has_rv and cibc_ids:
                cur.execute(
                    """
                    SELECT bt.*
                      FROM banking_transactions bt
                     WHERE bt.bank_id = ANY(%s)
                       AND bt.credit_amount IS NOT NULL AND bt.credit_amount > 0
                       AND (
                            UPPER(bt.description) LIKE '%%SQUARE%%' OR
                            UPPER(bt.description) LIKE '%%INTERAC%%' OR UPPER(bt.description) LIKE '%%E-TRANSFER%%' OR UPPER(bt.description) LIKE '%%ETRF%%' OR UPPER(bt.description) LIKE '%%EMT%%'
                       )
                       AND NOT EXISTS (
                            SELECT 1 FROM receipts_finance_view v
                            WHERE v.receipt_date = bt.transaction_date
                              AND v.inflow_amount > 0
                              AND ABS(v.inflow_amount - bt.credit_amount) <= 2.00
                       )
                     ORDER BY bt.transaction_date DESC
                    """,
                    (cibc_ids,)
                )
                cibc_unmatched = cur.fetchall()

            with open(OUT2, 'w', newline='', encoding='utf-8') as f:
                if cibc_unmatched:
                    w = csv.DictWriter(f, fieldnames=list(cibc_unmatched[0].keys()))
                    w.writeheader(); w.writerows(cibc_unmatched)
                else:
                    f.write('')

            # 5) Full export of all CIBC banking rows for manual review
            cur.execute(
                """
                SELECT * FROM banking_transactions WHERE bank_id = ANY(%s) ORDER BY transaction_date DESC
                """,
                (cibc_ids,)
            )
            all_cibc = cur.fetchall()
            with open(OUT3, 'w', newline='', encoding='utf-8') as f:
                if all_cibc:
                    w = csv.DictWriter(f, fieldnames=list(all_cibc[0].keys()))
                    w.writeheader(); w.writerows(all_cibc)
                else:
                    f.write('')

            # 6) Verify Square payment_key integrity: ensure payments with method=credit_card have payment_key matching Square id shape
            cur.execute(
                """
                SELECT payment_id, payment_key, amount, payment_date
                  FROM payments
                 WHERE LOWER(payment_method)='credit_card'
                   AND (payment_key IS NULL OR length(payment_key) < 12)
                 ORDER BY payment_date DESC
                 LIMIT 200
                """
            )
            bad_keys = cur.fetchall()
            with open(OUT4, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['payment_id','payment_key','amount','payment_date'])
                for r in bad_keys:
                    w.writerow([r['payment_id'], r['payment_key'], float(r['amount'] or 0), r['payment_date']])

            # 7) Write multi-charter payments if present
            if multi:
                with open(OUT7, 'w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=list(multi[0].keys()))
                    w.writeheader(); w.writerows(multi)

            # 8) Extract unlinked payments with #hint charter IDs in notes
            cur.execute(
                """
                SELECT payment_id, payment_date, amount, payment_method, payment_key, notes
                  FROM payments
                 WHERE reserve_number IS NULL AND notes ~ '#\\d{3,7}'
                 ORDER BY payment_date DESC
                """
            )
            hints = cur.fetchall()
            if hints:
                with open(OUT8, 'w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=list(hints[0].keys()))
                    w.writeheader(); w.writerows(hints)

    print('Wrote:')
    print(' ', OUT1)
    print(' ', OUT2)
    print(' ', OUT3)
    print(' ', OUT4)
    print(' ', OUT5)
    print(' ', OUT6)
    print(' ', OUT7)
    print(' ', OUT8)


if __name__ == '__main__':
    main()
