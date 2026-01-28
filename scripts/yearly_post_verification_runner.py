#!/usr/bin/env python3
"""
Year-by-year post-verification runner
- Gate actions by accountant verification checkpoint per year
- Supports dry-run, report generation, payment method normalization, marking verified, and locks

Usage examples:
  python -X utf8 scripts/yearly_post_verification_runner.py --years 2014 --report --dry-run
  python -X utf8 scripts/yearly_post_verification_runner.py --years 2014 --mark-verified
  python -X utf8 scripts/yearly_post_verification_runner.py --years 2014 --apply-locks
  python -X utf8 scripts/yearly_post_verification_runner.py --years 2014 --normalize-payment-methods --report
  python -X utf8 scripts/yearly_post_verification_runner.py --years 2014,2015 --report --apply-locks

Verification checkpoint:
- A marker file under reports/ACCOUNTANT_VERIFIED_<YEAR>.txt gates locking actions
- Create marker via --mark-verified or manually after accountant signs off
"""
import argparse
import os
import sys
import psycopg2
from datetime import datetime, date

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

ALLOWED_METHODS = {"cash", "check", "credit_card", "debit_card", "bank_transfer", "trade_of_services", "unknown"}


def connect_db():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def parse_args():
    p = argparse.ArgumentParser(description="Run year-by-year post-verification tasks")
    p.add_argument("--years", required=True, help="Comma-separated list of years, e.g. 2014,2015")
    p.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    p.add_argument("--report", action="store_true", help="Generate year-specific reconciliation report")
    p.add_argument("--mark-verified", action="store_true", help="Create accountant verification marker file for the year(s)")
    p.add_argument("--apply-locks", action="store_true", help="Lock/verify receipts + banking for the year(s); requires marker")
    p.add_argument("--normalize-payment-methods", action="store_true", help="Normalize payments.payment_method for the year(s)")
    return p.parse_args()


def year_bounds(year: int):
    return date(year, 1, 1), date(year, 12, 31)


def marker_path(year: int):
    return os.path.join(REPORTS_DIR, f"ACCOUNTANT_VERIFIED_{year}.txt")


def ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def create_marker(year: int):
    ensure_reports_dir()
    path = marker_path(year)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Accountant Verification Marker\nYear: {year}\nDate: {datetime.now():%Y-%m-%d %H:%M:%S}\nInitiated by: AUTO_SYSTEM\n")
    return path


def has_marker(year: int):
    return os.path.exists(marker_path(year))


def generate_report(conn, year: int):
    start, end = year_bounds(year)
    cur = conn.cursor()

    print(f"\n=== YEAR {year} RECONCILIATION REPORT ===")

    # Banking summary for year
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN verified = TRUE THEN 1 END) as verified,
            COUNT(CASE WHEN reconciliation_status = 'reconciled' THEN 1 END) as reconciled,
            COUNT(CASE WHEN reconciled_payment_id IS NOT NULL THEN 1 END) as to_payments,
            COUNT(CASE WHEN reconciled_receipt_id IS NOT NULL THEN 1 END) as to_receipts,
            SUM(COALESCE(credit_amount,0)) as credits,
            SUM(COALESCE(debit_amount,0)) as debits
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
        """,
        (start, end),
    )
    total, verified, reconciled, to_pay, to_rec, credits, debits = cur.fetchone()
    print(f"Banking: total={total:,}, verified={verified:,}, reconciled={reconciled:,}, to_payments={to_pay:,}, to_receipts={to_rec:,}, credits=${credits:,.2f}, debits=${debits:,.2f}")

    # Receipts summary for year
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN is_verified_banking = TRUE THEN 1 END) as verified,
            COUNT(CASE WHEN created_from_banking = TRUE THEN 1 END) as auto_created,
            COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as banking_link,
            SUM(COALESCE(gross_amount,0)) as total_gross
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
        """,
        (start, end),
    )
    r_total, r_verified, r_auto, r_link, r_gross = cur.fetchone()
    print(f"Receipts: total={r_total:,}, verified={r_verified:,}, auto_created={r_auto:,}, banking_link={r_link:,}, gross=${r_gross:,.2f}")

    # Charter payments summary for year
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid,
            SUM(COALESCE(amount,0)) as total_amount
        FROM payments
        WHERE reserve_number ~ '^[0-9]{6}$' AND payment_date BETWEEN %s AND %s
        """,
        (start, end),
    )
    p_total, p_paid, p_amount = cur.fetchone()
    print(f"Charter Payments: total={p_total:,}, status_paid={p_paid:,}, amount=${p_amount:,.2f}")

    cur.close()

    # Persist to file
    ensure_reports_dir()
    out = os.path.join(REPORTS_DIR, f"Yearly_Reconciliation_Report_{year}_{datetime.now():%Y-%m-%d_%H%M}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"YEAR {year} RECONCILIATION REPORT\n")
        f.write(f"Banking: total={total:,}, verified={verified:,}, reconciled={reconciled:,}, to_payments={to_pay:,}, to_receipts={to_rec:,}, credits=${credits:,.2f}, debits=${debits:,.2f}\n")
        f.write(f"Receipts: total={r_total:,}, verified={r_verified:,}, auto_created={r_auto:,}, banking_link={r_link:,}, gross=${r_gross:,.2f}\n")
        f.write(f"Charter Payments: total={p_total:,}, status_paid={p_paid:,}, amount=${p_amount:,.2f}\n")
    print(f"Saved: {out}")


def normalize_payment_methods(conn, year: int, dry_run: bool):
    start, end = year_bounds(year)
    cur = conn.cursor()

    # Find distinct methods for the year
    cur.execute(
        """
        SELECT COALESCE(payment_method, '<NULL>') AS method, COUNT(*)
        FROM payments
        WHERE payment_date BETWEEN %s AND %s
        GROUP BY payment_method
        ORDER BY COUNT(*) DESC
        """,
        (start, end),
    )
    rows = cur.fetchall()
    print("Payment methods (before):")
    for m, c in rows:
        print(f"  {m:20s} {c:8d}")

    # Normalize: if not in allowed set and not NULL, set to 'unknown'
    cur.execute(
        """
        UPDATE payments
        SET payment_method = 'unknown'
        WHERE payment_date BETWEEN %s AND %s
          AND (payment_method IS NULL OR payment_method NOT IN (%s))
        """ % ("%s", "%s", ",".join(["%s"] * len(ALLOWED_METHODS))),
        (start, end, *list(ALLOWED_METHODS)),
    )
    updated = cur.rowcount
    if dry_run:
        conn.rollback()
        print(f"[DRY-RUN] Would normalize {updated:,} rows to 'unknown'")
    else:
        conn.commit()
        print(f"✅ Normalized {updated:,} rows to 'unknown' where out-of-set or NULL")

    # Show after
    cur.execute(
        """
        SELECT COALESCE(payment_method, '<NULL>') AS method, COUNT(*)
        FROM payments
        WHERE payment_date BETWEEN %s AND %s
        GROUP BY payment_method
        ORDER BY COUNT(*) DESC
        """,
        (start, end),
    )
    rows = cur.fetchall()
    print("Payment methods (after):")
    for m, c in rows:
        print(f"  {m:20s} {c:8d}")

    cur.close()


def apply_locks(conn, year: int, dry_run: bool):
    start, end = year_bounds(year)
    cur = conn.cursor()

    # Lock receipts (mark verified)
    cur.execute(
        """
        UPDATE receipts
        SET is_verified_banking = TRUE,
            verified_at = CURRENT_TIMESTAMP,
            verified_source = 'Accountant verified - yearly lock'
        WHERE receipt_date BETWEEN %s AND %s
          AND (is_verified_banking IS NULL OR is_verified_banking = FALSE)
        """,
        (start, end),
    )
    r_count = cur.rowcount

    # Lock banking transactions (mark verified where linked)
    cur.execute(
        """
        UPDATE banking_transactions
        SET verified = TRUE,
            reconciliation_status = 'reconciled',
            reconciled_at = CURRENT_TIMESTAMP,
            reconciled_by = 'AUTO_SYSTEM (yearly lock)'
        WHERE transaction_date BETWEEN %s AND %s
          AND (reconciled_payment_id IS NOT NULL OR reconciled_receipt_id IS NOT NULL)
          AND (verified IS NULL OR verified = FALSE OR reconciliation_status != 'reconciled')
        """,
        (start, end),
    )
    b_count = cur.rowcount

    if dry_run:
        conn.rollback()
        print(f"[DRY-RUN] Would lock {r_count:,} receipts and {b_count:,} banking transactions for {year}")
    else:
        conn.commit()
        print(f"✅ Locked {r_count:,} receipts and {b_count:,} banking transactions for {year}")

    cur.close()


def main():
    args = parse_args()
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]

    conn = connect_db()

    print("\n" + "="*80)
    print("YEAR-BY-YEAR POST-VERIFICATION RUNNER")
    print("="*80)
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Dry-run: {args.dry_run}")
    print(f"Actions: report={args.report}, mark_verified={args.mark_verified}, apply_locks={args.apply_locks}, normalize_payment_methods={args.normalize_payment_methods}")
    print("-"*80)

    ensure_reports_dir()

    for year in years:
        print(f"\n▶ Processing year {year}")
        # Report first (safe)
        if args.report:
            generate_report(conn, year)
        
        # Mark verified (creates marker file)
        if args.mark_verified:
            path = marker_path(year)
            if has_marker(year):
                print(f"ℹ️  Marker already exists: {path}")
            else:
                path = create_marker(year)
                print(f"✅ Created verification marker: {path}")
        
        # Normalize payment methods (safe)
        if args.normalize_payment_methods:
            normalize_payment_methods(conn, year, args.dry_run)
        
        # Apply locks (gated by marker)
        if args.apply_locks:
            if not has_marker(year):
                print(f"⛔ Cannot apply locks for {year} - accountant verification marker not found: {marker_path(year)}")
            else:
                apply_locks(conn, year, args.dry_run)

    conn.close()
    print("\n" + "="*80)
    print("DONE")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
