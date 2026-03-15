import argparse
import csv
import os
from datetime import datetime
from decimal import Decimal
import psycopg2

REFUND_ACTIONS = r"L:\\limo\\reports\\REFUND_ACTIONS_REVIEW.csv"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def load_nrd_candidates(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                tad = Decimal(row.get("total_amount_due") or "0")
                refund = Decimal(row.get("expected_refund") or "0")
                has500 = (row.get("has_500_payment", "False").strip().lower() == "true")
            except Exception:
                tad = Decimal("0")
                refund = Decimal("0")
                has500 = False
            # NRD pattern: $0 charges and a $500 payment flagged by review
            if tad == 0 and has500 and refund == Decimal("500"):
                rows.append({
                    "reserve_number": row.get("reserve_number").strip(),
                    "charter_id": row.get("charter_id").strip(),
                    "expected_refund": refund,
                })
    return rows


def ensure_charges_backup(cur, backup_table):
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {backup_table} AS 
        SELECT * FROM charter_charges WHERE 1=0
        """
    )


def backup_charges(cur, backup_table, reserve_number):
    # Backup by reserve_number to be robust against missing charter_id mapping
    cur.execute(
        f"INSERT INTO {backup_table} SELECT * FROM charter_charges WHERE reserve_number = %s",
        (reserve_number,),
    )


def insert_credit_ledger(cur, reserve_number, charter_id, amount):
    # Avoid duplicate credits in current schema
    cur.execute(
        """
        SELECT 1 FROM charter_credit_ledger 
        WHERE source_reserve_number = %s AND credit_amount = %s AND credit_reason = 'NRD_ESCROW'
        """,
        (reserve_number, amount),
    )
    if cur.fetchone():
        return None
    cur.execute(
        """
        INSERT INTO charter_credit_ledger (
            source_reserve_number, source_charter_id, client_id, credit_amount, credit_reason, remaining_balance,
            created_date, applied_date, applied_to_reserve_number, applied_to_charter_id, notes, created_by
        ) VALUES (%s, %s, NULL, %s, %s, %s, NOW(), NULL, NULL, NULL, %s, %s)
        RETURNING credit_id
        """,
        (
            reserve_number,
            int(charter_id) if str(charter_id).isdigit() else None,
            amount,
            'NRD_ESCROW',
            amount,
            'Non-refundable deposit held in escrow (kept, not refunded).',
            'NRD_ESCROW_SCRIPT',
        ),
    )
    return cur.fetchone()[0]


def annotate_payment_rows(cur, reserve_number, amount, credit_id):
    # Append a note on the exact $500 payment row(s) if present
    note = f" | NRD_ESCROW credit_id={credit_id}" if credit_id else " | NRD_ESCROW"
    cur.execute(
        """
        UPDATE payments 
        SET notes = CONCAT(COALESCE(notes,''), %s)
        WHERE reserve_number = %s AND ABS(amount - %s) < 0.005
        """,
        (note, reserve_number, float(amount)),
    )
    return cur.rowcount


def delete_charges(cur, reserve_number):
    cur.execute("DELETE FROM charter_charges WHERE reserve_number = %s", (reserve_number,))
    return cur.rowcount


def zero_charter(cur, reserve_number):
    cur.execute(
        """
        UPDATE charters 
        SET total_amount_due = 0.00, paid_amount = 0.00, balance = 0.00, cancelled = TRUE, updated_at = NOW()
        WHERE reserve_number = %s
        """,
        (reserve_number,),
    )
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Apply NRD escrow: keep payments, remove charges, zero charter")
    parser.add_argument("--write", action="store_true", help="Apply changes (defaults to dry-run)")
    args = parser.parse_args()

    candidates = load_nrd_candidates(REFUND_ACTIONS)
    if not candidates:
        print("No NRD candidates found from review file.")
        return

    print(f"NRD candidates: {len(candidates)} (criteria: $0 charges + $500 payment)")
    backup_table = f"charter_charges_backup_nrd_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    conn = get_conn()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        ensure_charges_backup(cur, backup_table)

        for item in candidates:
            rn = item["reserve_number"]
            cid = item["charter_id"]
            amt = Decimal("500.00")
            print(f"\n--- {rn} (charter_id={cid}) ---")

            # Summaries
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM charter_charges WHERE reserve_number=%s", (rn,))
            charges_sum = Decimal(str(cur.fetchone()[0] or 0))
            cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number=%s AND ABS(amount-500.00)<0.005", (rn,))
            cnt_500 = cur.fetchone()[0]
            print(f"Current: charges_sum={charges_sum} | $500 payments={cnt_500}")

            if not args.write:
                print(f"DRY-RUN: would backup charges to {backup_table}, delete charges, insert NRD_ESCROW credit $500, annotate payment row(s), and zero charter totals.")
                continue

            backup_charges(cur, backup_table, rn)
            deleted = delete_charges(cur, rn)
            credit_id = insert_credit_ledger(cur, rn, cid, amt)
            annotated = annotate_payment_rows(cur, rn, amt, credit_id)
            zeroed = zero_charter(cur, rn)

            print(f"Backed up charges, deleted={deleted}, credit_id={credit_id}, annotated_payments={annotated}, zeroed_charter={zeroed}")

        if args.write:
            conn.commit()
            print("\n=== Changes committed ===")
        else:
            conn.rollback()
            print("\n=== DRY-RUN only (no changes) ===")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
