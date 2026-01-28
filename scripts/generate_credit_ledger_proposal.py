#!/usr/bin/env python3
"""Generate credit ledger allocation proposal for overpaid charters.

Strategy:
  For each overpaid charter (paid_amount > total_amount_due):
    1. Compute excess = min(pg_paid - pg_due, pg_paid - lms_est_charge)
    2. Categorize by pattern:
         - UNIFORM_INSTALLMENT: Many payments of same amount (e.g. 014899 seven $774 payments)
         - LARGE_ETR: Single or few large e-transfer payments suggesting multi-charter prepayment
         - CANCELLED_EXCESS: Cancelled charter with overpay (retained deposit policy)
         - MIXED: Other overpay patterns
    3. Propose action:
         - CREDIT_LEDGER: Move excess to client credit for future use
         - REALLOCATE: Suggest other unpaid charters of same client for reallocation
         - VERIFY_DEPOSIT: Manual review for cancelled/deposit policy confirmation

Outputs:
  CSV: l:/limo/reports/credit_ledger_proposal.csv
  Summary stats by category and recommended action

No database writes performed (dry-run only).

Usage:
  python scripts/generate_credit_ledger_proposal.py
  python scripts/generate_credit_ledger_proposal.py --min-excess 1000  # Filter minimum excess
"""

import os
import csv
import psycopg2
import pyodbc
from collections import defaultdict, Counter
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
LMS_PATH = os.getenv("LMS_MDB_PATH", r"L:\limo\backups\lms.mdb")

CSV_PATH = "l:/limo/reports/credit_ledger_proposal.csv"
UNIFORM_THRESHOLD = 0.95  # 95% of payments same amount
LARGE_ETR_THRESHOLD = 2500  # Single ETR >= this suggests multi-charter


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def lms_conn():
    if not os.path.exists(LMS_PATH):
        raise FileNotFoundError(f"LMS not found at {LMS_PATH}")
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    return pyodbc.connect(conn_str)


def fetch_overpaid(cur):
    cur.execute(
        """
        SELECT reserve_number, charter_id, client_id, total_amount_due, paid_amount, 
               balance, cancelled, status, charter_date
        FROM charters
        WHERE reserve_number IS NOT NULL AND paid_amount > total_amount_due
        ORDER BY (paid_amount - total_amount_due) DESC
        """
    )
    return cur.fetchall()


def fetch_payments(cur, reserve_number):
    cur.execute(
        """
        SELECT payment_id, amount, payment_date, payment_key
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
        """,
        (reserve_number,)
    )
    return cur.fetchall()


def fetch_lms_est(cur_lms, reserve_number):
    for col in ["Est_Charge", "EstCharge"]:
        try:
            cur_lms.execute(
                f"SELECT {col}, Deposit FROM Reserve WHERE Reserve_No = ?",
                (reserve_number,)
            )
            row = cur_lms.fetchone()
            if row:
                est = float(row[0]) if row[0] not in (None, '', 0) else None
                dep = float(row[1]) if row[1] not in (None, '', 0) else 0.0
                return est if est else dep
        except:
            continue
    return None


def categorize_pattern(payments):
    if not payments:
        return 'NO_PAYMENTS', {}
    amounts = [float(p[1]) for p in payments]
    amount_counts = Counter(amounts)
    most_common_amount, most_common_count = amount_counts.most_common(1)[0]
    uniform_ratio = most_common_count / len(amounts)
    
    etr_payments = [p for p in payments if p[3] and p[3].startswith('ETR:')]
    etr_total = sum(float(p[1]) for p in etr_payments)
    large_etr_count = sum(1 for p in etr_payments if float(p[1]) >= LARGE_ETR_THRESHOLD)
    
    if uniform_ratio >= UNIFORM_THRESHOLD and len(amounts) >= 3:
        return 'UNIFORM_INSTALLMENT', {
            'common_amount': most_common_amount,
            'count': most_common_count,
            'total_count': len(amounts)
        }
    elif large_etr_count >= 1:
        return 'LARGE_ETR', {
            'etr_total': etr_total,
            'large_etr_count': large_etr_count
        }
    elif etr_total > sum(amounts) * 0.5:
        return 'ETR_DOMINATED', {'etr_total': etr_total}
    else:
        return 'MIXED', {}


def propose_action(category, cancelled, excess, pattern_info):
    if cancelled:
        return 'VERIFY_DEPOSIT_NONREFUNDABLE'
    if category in ('UNIFORM_INSTALLMENT', 'MIXED'):
        return 'CREDIT_LEDGER'
    if category in ('LARGE_ETR', 'ETR_DOMINATED'):
        return 'REALLOCATE_MULTI_CHARTER'
    return 'MANUAL_REVIEW'


def analyze(min_excess=0):
    pg = pg_conn()
    cur_pg = pg.cursor()
    overpaid = fetch_overpaid(cur_pg)
    lms = lms_conn()
    cur_lms = lms.cursor()
    
    proposals = []
    for (reserve_number, charter_id, client_id, pg_due, pg_paid, pg_balance, 
         cancelled, status, charter_date) in overpaid:
        
        payments = fetch_payments(cur_pg, reserve_number)
        lms_est = fetch_lms_est(cur_lms, reserve_number)
        
        # Compute excess (conservative: min of two differences)
        excess_pg = float(pg_paid or 0) - float(pg_due or 0)
        if lms_est is not None:
            excess_lms = float(pg_paid or 0) - lms_est
            excess = min(excess_pg, excess_lms)
        else:
            excess = excess_pg
        
        if excess < min_excess:
            continue
        
        category, pattern_info = categorize_pattern(payments)
        action = propose_action(category, bool(cancelled), excess, pattern_info)
        
        proposals.append({
            'reserve_number': reserve_number,
            'charter_id': charter_id,
            'client_id': client_id,
            'charter_date': charter_date,
            'pg_due': float(pg_due or 0),
            'pg_paid': float(pg_paid or 0),
            'lms_est': lms_est,
            'excess': excess,
            'cancelled': bool(cancelled),
            'status': status,
            'category': category,
            'action': action,
            'payment_count': len(payments),
            'pattern_info': str(pattern_info) if pattern_info else '',
        })
    
    cur_pg.close(); pg.close(); cur_lms.close(); lms.close()
    return proposals


def export_csv(proposals):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'reserve_number', 'charter_id', 'client_id', 'charter_date', 'pg_total_due',
            'pg_paid_amount', 'lms_est_charge', 'excess_amount', 'cancelled', 'status',
            'category', 'proposed_action', 'payment_count', 'pattern_info'
        ])
        for p in proposals:
            w.writerow([
                p['reserve_number'], p['charter_id'], p['client_id'], p['charter_date'],
                f"{p['pg_due']:.2f}", f"{p['pg_paid']:.2f}",
                f"{p['lms_est']:.2f}" if p['lms_est'] is not None else '',
                f"{p['excess']:.2f}", p['cancelled'], p['status'], p['category'],
                p['action'], p['payment_count'], p['pattern_info']
            ])
    return CSV_PATH


def summarize(proposals):
    total_excess = sum(p['excess'] for p in proposals)
    cat_counts = Counter(p['category'] for p in proposals)
    action_counts = Counter(p['action'] for p in proposals)
    
    print("=== Credit Ledger Remediation Proposal ===")
    print(f"Total overpaid charters analyzed: {len(proposals)}")
    print(f"Total excess amount: ${total_excess:,.2f}")
    print(f"\nCategory breakdown:")
    for cat, count in cat_counts.most_common():
        cat_excess = sum(p['excess'] for p in proposals if p['category'] == cat)
        print(f"  {cat}: {count} charters (${cat_excess:,.2f})")
    print(f"\nProposed actions:")
    for action, count in action_counts.most_common():
        action_excess = sum(p['excess'] for p in proposals if p['action'] == action)
        print(f"  {action}: {count} charters (${action_excess:,.2f})")
    
    print(f"\nTop 10 by excess:")
    sorted_proposals = sorted(proposals, key=lambda p: p['excess'], reverse=True)
    for p in sorted_proposals[:10]:
        print(f"  reserve={p['reserve_number']} excess=${p['excess']:.2f} "
              f"category={p['category']} action={p['action']} payments={p['payment_count']}")


def main():
    parser = ArgumentParser(description='Generate credit ledger allocation proposal')
    parser.add_argument('--min-excess', type=float, default=0.0,
                       help='Minimum excess amount to include (default: 0)')
    args = parser.parse_args()
    
    try:
        proposals = analyze(args.min_excess)
        summarize(proposals)
        path = export_csv(proposals)
        print(f"\nCSV written: {path}")
        print("\nNext steps:")
        print("  1. Review CSV for accuracy (especially UNIFORM_INSTALLMENT cases)")
        print("  2. For CREDIT_LEDGER actions: create charter_credit_ledger entries")
        print("  3. For REALLOCATE actions: identify target charters and create split allocations")
        print("  4. For VERIFY actions: confirm retention policy with client/contract")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(2)


if __name__ == '__main__':
    main()
