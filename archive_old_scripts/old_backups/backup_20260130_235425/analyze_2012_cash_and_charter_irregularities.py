#!/usr/bin/env python3
"""
Analyze 2012 cash transactions (income + expense) and charter/payment/charge irregularities.

Cash Income Sources:
  - payments.payment_method = 'cash'
  - banking_transactions description patterns indicating cash deposit
  - receipts where description/vendor indicates cash received (rare; usually payments table)

Cash Expense Sources:
  - receipts paid in cash (if payment_method column exists or description contains 'CASH')
  - payments with negative amount and method 'cash' (refunds)

Charter Irregularities:
  1. total_amount_due mismatch vs SUM(charter_charges.amount)
  2. paid_amount mismatch vs SUM(payments.amount) by reserve_number (business key)
  3. Negative balances (< -1.00) indicating possible duplicate payments or over-refunds
  4. Overpaid (> total_amount_due * 1.05)
  5. Underpaid (balance > 0 AND payment_status in ('PAID','closed') )
  6. Missing charges (total_amount_due = 0 but payments exist)
  7. Missing payments (paid_amount > 0 but no payment rows found)

Outputs: Human-readable summary to stdout plus optional CSV dumps if --export provided.

Safe: Read-only queries only.
"""

import os
import sys
import csv
import psycopg2
from datetime import date
from decimal import Decimal

YEAR = 2012

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

EXPORT = '--export' in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def table_columns(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table,))
    return {r[0] for r in cur.fetchall()}

def fetch_cash_payments(cur):
    cols = table_columns(cur, 'payments')
    if 'payment_method' not in cols or 'payment_date' not in cols:
        return []
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
        FROM payments
        WHERE payment_method = 'cash'
          AND payment_date >= %s AND payment_date < %s
        ORDER BY payment_date
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    return cur.fetchall()

def fetch_cash_receipts(cur):
    cols = table_columns(cur, 'receipts')
    look_cols = []
    if 'receipt_date' in cols: look_cols.append('receipt_date')
    if not look_cols:
        return []
    payment_method_col = None
    for cand in ['payment_method','method','pay_method']:
        if cand in cols:
            payment_method_col = cand
            break
    # Expanded cash detection: CASH keyword, ATM/ABM withdrawals, cash purchase patterns, petty cash
    conditions = ["receipt_date >= %s", "receipt_date < %s"]
    cash_predicates = []
    if payment_method_col:
        cash_predicates.append(f"LOWER({payment_method_col}) = 'cash'")
    if 'vendor_name' in cols:
        cash_predicates.append("vendor_name ILIKE '%%cash%%'")
        cash_predicates.append("vendor_name ILIKE '%%atm%%'")
        cash_predicates.append("vendor_name ILIKE '%%abm%%'")
    if 'description' in cols:
        cash_predicates.append("description ILIKE '%%cash%%'")
        cash_predicates.append("description ILIKE '%%atm%%'")
        cash_predicates.append("description ILIKE '%%abm withdrawal%%'")
        cash_predicates.append("description ILIKE '%%petty cash%%'")
        cash_predicates.append("description ILIKE '%%paid cash%%'")
    predicate_sql = ""
    if cash_predicates:
        predicate_sql = " AND (" + " OR ".join(cash_predicates) + ")"
    query = (
        "SELECT receipt_id, vendor_name, description, gross_amount, receipt_date "
        "FROM receipts WHERE " + " AND ".join(conditions) + predicate_sql
    )
    params = [date(YEAR,1,1), date(YEAR+1,1,1)]
    try:
        cur.execute(query, params)
        rows = cur.fetchall()
        return rows
    except Exception as e:
        # Return empty list if any issue (missing table/columns or placeholder mismatch)
        print(f"[WARN] Failed to fetch cash receipts: {e}")
        return []
    

def fetch_cash_banking_deposits(cur):
    cols = table_columns(cur, 'banking_transactions')
    if 'transaction_date' not in cols:
        return []
    # Expanded heuristics: CASH, CURRENCY, COIN, generic DEPOSIT, DEP, physical branch deposits
    # Exclude: CREDIT MEMO (merchant card batches), INTERAC (e-transfers), MCC PAYMENT (card processing)
    cur.execute("""
        SELECT transaction_id, transaction_date, description, credit_amount
        FROM banking_transactions
        WHERE transaction_date >= %s AND transaction_date < %s
          AND credit_amount IS NOT NULL AND credit_amount > 0
          AND (
              description ILIKE '%%cash%%' 
              OR description ILIKE '%%currency%%' 
              OR description ILIKE '%%coin%%'
              OR (description ILIKE '%%deposit%%' AND description NOT ILIKE '%%credit memo%%')
              OR (description ILIKE '%%dep %%' AND description NOT ILIKE '%%credit%%')
              OR description ILIKE '%%branch deposit%%'
              OR description ILIKE '%%teller%%'
          )
          AND description NOT ILIKE '%%credit memo%%'
          AND description NOT ILIKE '%%interac%%'
          AND description NOT ILIKE '%%mcc payment%%'
          AND description NOT ILIKE '%%e-transfer%%'
        ORDER BY transaction_date
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    return cur.fetchall()

def charter_irregularities(cur):
    issues = {}
    # 1 total_amount_due mismatch
    cur.execute("""
        WITH charge_sums AS (
            SELECT c.reserve_number, SUM(cc.amount) AS charge_sum
            FROM charters c
            LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
            WHERE c.charter_date >= %s AND c.charter_date < %s
            GROUP BY c.reserve_number
        )
        SELECT c.reserve_number, c.total_amount_due, charge_sums.charge_sum
        FROM charters c
        LEFT JOIN charge_sums ON charge_sums.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
          AND c.total_amount_due IS NOT NULL
          AND charge_sums.charge_sum IS NOT NULL
          AND ABS(c.total_amount_due - charge_sums.charge_sum) > 0.01
        ORDER BY c.reserve_number
        LIMIT 2000
    """, (date(YEAR,1,1), date(YEAR+1,1,1), date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['total_due_mismatch'] = cur.fetchall()

    # 2 paid_amount mismatch vs payments
    # NOTE: Uses ALL payments regardless of date to handle cross-year refunds
    cur.execute("""
        WITH payment_sums AS (
            SELECT reserve_number, SUM(amount) AS paid_sum
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT c.reserve_number, c.paid_amount, COALESCE(payment_sums.paid_sum,0) AS calc_paid
        FROM charters c
        LEFT JOIN payment_sums ON payment_sums.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
          AND c.paid_amount IS NOT NULL
          AND ABS(c.paid_amount - COALESCE(payment_sums.paid_sum,0)) > 0.01
        ORDER BY c.reserve_number
        LIMIT 2000
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['paid_amount_mismatch'] = cur.fetchall()

    # 3 negative balances
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
          AND balance < -1.00
        ORDER BY balance ASC
        LIMIT 500
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['negative_balance'] = cur.fetchall()

    # 4 overpaid
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
          AND total_amount_due > 0
          AND paid_amount > total_amount_due * 1.05
        ORDER BY paid_amount - total_amount_due DESC
        LIMIT 500
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['overpaid'] = cur.fetchall()

    # 5 underpaid with paid status
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, payment_status
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
          AND balance > 0.01
          AND payment_status IN ('PAID','paid','Closed','closed')
        ORDER BY balance DESC
        LIMIT 500
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['underpaid_status'] = cur.fetchall()

    # 6 missing charges (total_amount_due = 0, payments exist)
    cur.execute("""
        SELECT c.reserve_number, c.total_amount_due, c.paid_amount
        FROM charters c
        JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
          AND c.total_amount_due = 0
        GROUP BY c.reserve_number, c.total_amount_due, c.paid_amount
        LIMIT 500
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['missing_charges'] = cur.fetchall()

    # 7 paid_amount > 0 but no payment rows
    cur.execute("""
        SELECT c.reserve_number, c.paid_amount, c.total_amount_due
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
          AND c.paid_amount > 0.01
        GROUP BY c.reserve_number, c.paid_amount, c.total_amount_due
        HAVING COUNT(p.payment_id) = 0
        LIMIT 500
    """, (date(YEAR,1,1), date(YEAR+1,1,1)))
    issues['no_payment_rows'] = cur.fetchall()

    return issues

def print_section(title):
    print("\n" + title)
    print('-'*len(title))

def main():
    conn = get_conn()
    cur = conn.cursor()

    print(f"Analyzing CASH transactions and charter irregularities for {YEAR}...")

    cash_payments = fetch_cash_payments(cur)
    cash_receipts = fetch_cash_receipts(cur)
    cash_deposits = fetch_cash_banking_deposits(cur)
    irregular = charter_irregularities(cur)

    # CASH SUMMARY
    print_section("CASH INCOME (payments.payment_method='cash')")
    total_cash_income = sum(p[2] for p in cash_payments)
    print(f"Count: {len(cash_payments)} | Total: ${total_cash_income:,.2f}")
    for p in cash_payments[:15]:
        pid, reserve, amt, pdate, method, notes = p
        print(f" {pdate} | Rsv {reserve} | ${amt:,.2f} | {notes if notes else ''}")
    if len(cash_payments) > 15:
        print(f" ... ({len(cash_payments)-15} more)")

    print_section("CASH EXPENSE (receipts contains 'cash')")
    total_cash_exp = sum(r[3] for r in cash_receipts)
    print(f"Count: {len(cash_receipts)} | Total: ${total_cash_exp:,.2f}")
    for r in cash_receipts[:15]:
        rid, vendor, desc, amt, rdate = r
        print(f" {rdate} | Receipt {rid} | ${amt:,.2f} | {vendor} | {desc[:60] if desc else ''}")
    if len(cash_receipts) > 15:
        print(f" ... ({len(cash_receipts)-15} more)")

    print_section("BANKING CASH-LIKE DEPOSITS (description patterns)")
    total_cash_dep = sum(d[3] for d in cash_deposits)
    print(f"Count: {len(cash_deposits)} | Total: ${total_cash_dep:,.2f}")
    for d in cash_deposits[:15]:
        tid, tdate, desc, amt = d
        print(f" {tdate} | Tx {tid} | ${amt:,.2f} | {desc[:70]}")
    if len(cash_deposits) > 15:
        print(f" ... ({len(cash_deposits)-15} more)")

    # Irregularities
    print_section("CHARTER IRREGULARITIES SUMMARY")
    def show_issue(key, label, rows, sample_fmt):
        print(f"{label}: {len(rows)}")
        for row in rows[:10]:
            print("  " + sample_fmt(row))
        if len(rows) > 10:
            print(f"  ... ({len(rows)-10} more)")
    show_issue('total_due_mismatch', 'Total due mismatch', irregular['total_due_mismatch'], lambda r: f"Rsv {r[0]} due {r[1]:.2f} vs charges {r[2]:.2f}")
    show_issue('paid_amount_mismatch', 'Paid amount mismatch', irregular['paid_amount_mismatch'], lambda r: f"Rsv {r[0]} paid {r[1]:.2f} vs payments {r[2]:.2f}")
    show_issue('negative_balance', 'Negative balance (< -1)', irregular['negative_balance'], lambda r: f"Rsv {r[0]} bal {r[3]:.2f} due {r[1]:.2f} paid {r[2]:.2f}")
    show_issue('overpaid', 'Overpaid >105%', irregular['overpaid'], lambda r: f"Rsv {r[0]} paid {r[2]:.2f} due {r[1]:.2f} bal {r[3]:.2f}")
    show_issue('underpaid_status', 'Underpaid but status PAID', irregular['underpaid_status'], lambda r: f"Rsv {r[0]} bal {r[3]:.2f} due {r[1]:.2f} paid {r[2]:.2f}")
    show_issue('missing_charges', 'Missing charges (due=0, payments exist)', irregular['missing_charges'], lambda r: f"Rsv {r[0]} due {r[1]:.2f} paid {r[2]:.2f}")
    show_issue('no_payment_rows', 'Paid amount but no payment rows', irregular['no_payment_rows'], lambda r: f"Rsv {r[0]} paid {r[1]:.2f} due {r[2]:.2f}")

    # Root cause hints
    print_section("ROOT CAUSE HINTS")
    print("- Reserve number business key must be used; mismatches often caused by charter_id joins in legacy scripts.")
    print("- total_amount_due inconsistencies usually stem from missing or incorrect charter_charges entries or legacy migration errors.")
    print("- Overpayments commonly caused by duplicate payment imports (batch re-run) – verify composite uniqueness (reserve_number, amount, date).")
    print("- Negative balances beyond small rounding indicate duplicate payments or manual corrections without balance recalculation.")
    print("- Paid status with positive balance indicates recalculation scripts using charter_id instead of reserve_number OR late payment not included in paid_amount field.")
    print("- Missing charges (due=0) but payments present arise when Est_Charge not imported – fix by inserting synthetic charter_charge from LMS Est_Charge.")
    print("- Paid amount but no payment rows: imported charters where paid_amount field set from source but payment detail not migrated.")

    if EXPORT:
        out_dir = os.path.join(os.getcwd(), f"analysis_{YEAR}")
        os.makedirs(out_dir, exist_ok=True)
        def dump_csv(name, rows, header):
            with open(os.path.join(out_dir, name), 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(rows)
        dump_csv('cash_payments.csv', cash_payments, ['payment_id','reserve_number','amount','payment_date','payment_method','notes'])
        dump_csv('cash_receipts.csv', cash_receipts, ['receipt_id','vendor_name','description','gross_amount','receipt_date'])
        dump_csv('cash_deposits.csv', cash_deposits, ['transaction_id','transaction_date','description','credit_amount'])
        for key, rows in irregular.items():
            if key == 'total_due_mismatch':
                dump_csv('total_due_mismatch.csv', rows, ['reserve_number','total_amount_due','charge_sum'])
            elif key == 'paid_amount_mismatch':
                dump_csv('paid_amount_mismatch.csv', rows, ['reserve_number','paid_amount','calc_paid'])
            elif key == 'negative_balance':
                dump_csv('negative_balance.csv', rows, ['reserve_number','total_amount_due','paid_amount','balance'])
            elif key == 'overpaid':
                dump_csv('overpaid.csv', rows, ['reserve_number','total_amount_due','paid_amount','balance'])
            elif key == 'underpaid_status':
                dump_csv('underpaid_status.csv', rows, ['reserve_number','total_amount_due','paid_amount','balance','payment_status'])
            elif key == 'missing_charges':
                dump_csv('missing_charges.csv', rows, ['reserve_number','total_amount_due','paid_amount'])
            elif key == 'no_payment_rows':
                dump_csv('no_payment_rows.csv', rows, ['reserve_number','paid_amount','total_amount_due'])
        print(f"\nCSV exports written to {out_dir}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
