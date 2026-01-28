import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional, List, Tuple

import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OD_PATTERNS = [
    r"over\s*due\s*charge\s*on\s*(?P<base>[0-9]+\.[0-9]{2})",
    r"over\s*due\s*charge\s*(?P<base>[0-9]+\.[0-9]{2})",
    r"late\s*fee\s*on\s*(?P<base>[0-9]+\.[0-9]{2})",
    r"OD\s*fee\s*on\s*(?P<base>[0-9]+\.[0-9]{2})",
    r"over\s*due\s*charde\s*on\s*(?P<base>[0-9]+\.[0-9]{2})",  # common typo
]

@dataclass
class InvoiceRow:
    receipt_id: int
    vendor: str
    date: str
    amount: float
    amount_column: str  # which column to update (expense|gross_amount|net_amount)
    description: str
    category: Optional[str]
    invoice_number: Optional[str]
    payment_method: Optional[str]
    is_invoice: Optional[bool]
    canonical_vendor: Optional[str]
    vendor_account_id: Optional[int]

@dataclass
class SplitResult:
    base_amount: float
    fee_amount: float
    reason: str


def parse_base_amount_from_description(desc: str) -> Optional[float]:
    if not desc:
        return None
    text = desc.lower()
    for pat in OD_PATTERNS:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group("base"))
            except Exception:
                continue
    # Fallback: pick the largest number-like token in description
    nums = re.findall(r"([0-9]+\.[0-9]{2})", text)
    if nums:
        try:
            return float(sorted(nums, key=lambda x: float(x))[-1])
        except Exception:
            pass
    return None


def compute_split(row: InvoiceRow) -> Optional[SplitResult]:
    base = parse_base_amount_from_description(row.description or "")
    if base is None:
        return None
    fee = round(row.amount - base, 2)
    if fee <= 0.0:
        return None
    return SplitResult(base_amount=base, fee_amount=fee, reason=f"Derived base {base:.2f} from description; fee {fee:.2f}")


def fetch_candidate_invoices(cur, vendor_filter: Optional[str]) -> List[InvoiceRow]:
    # Discover column presence to avoid hard assumptions
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_schema='public' AND table_name='receipts'
    """)
    cols = {r[0] for r in cur.fetchall()}

    select_cols = [
        "receipt_id",
        "vendor_name" if "vendor_name" in cols else "canonical_vendor",
        "receipt_date" if "receipt_date" in cols else "date",
        # pull multiple amount candidates so we can choose
        "COALESCE(expense, 0) AS expense",
        "COALESCE(gross_amount, 0) AS gross_amount",
        "COALESCE(net_amount, 0) AS net_amount",
        "description",
        "canonical_vendor" if "canonical_vendor" in cols else "NULL AS canonical_vendor",
        "vendor_account_id" if "vendor_account_id" in cols else "NULL AS vendor_account_id",
    ]
    # Optional columns not strictly needed for split; keep minimal set to avoid index errors

    where_clauses = ["1=1"]
    if vendor_filter:
        column = "vendor_name" if "vendor_name" in cols else "canonical_vendor"
        where_clauses.append(f"LOWER({column}) = LOWER('{vendor_filter}')")

    sql = f"SELECT {', '.join(select_cols)} FROM receipts WHERE " + " AND ".join(where_clauses) + " ORDER BY receipt_id"

    cur.execute(sql)

    rows: List[InvoiceRow] = []
    for r in cur.fetchall():
        receipt_id = r[0]
        vendor = r[1]
        date = str(r[2])
        expense_val = float(r[3] or 0.0)
        gross_val = float(r[4] or 0.0)
        net_val = float(r[5] or 0.0)
        description = (r[6] or "").strip()
        canonical_vendor = r[7]
        vendor_account_id = r[8]
        category = None
        invoice_number = None
        payment_method = None
        is_invoice = None

        # choose the first non-zero among expense, gross_amount, net_amount
        chosen_amount, chosen_col = 0.0, "expense"
        for val, col in ((expense_val, "expense"), (gross_val, "gross_amount"), (net_val, "net_amount")):
            if val and abs(val) > 0.0:
                chosen_amount, chosen_col = val, col
                break

        rows.append(InvoiceRow(receipt_id, vendor, date, chosen_amount, chosen_col, description, category, invoice_number, payment_method, is_invoice, canonical_vendor, vendor_account_id))
    return rows


def ensure_parent_child_support(cur) -> Tuple[bool, Optional[str]]:
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_schema='public' AND table_name='receipts' AND column_name='parent_receipt_id'
    """)
    exists = cur.fetchone() is not None
    return exists, "parent_receipt_id" if exists else None


def insert_fee_child(cur, parent: InvoiceRow, fee_amount: float, parent_col: Optional[str]) -> Optional[int]:
    # Idempotency: signature based on parent id + fee amount + invoice_number
    signature = f"AUTO_SPLIT_FEE|parent={parent.receipt_id}|fee={fee_amount:.2f}|inv={parent.invoice_number or ''}"

    # Check if already inserted
    # Match using description signature and vendor_name/canonical_vendor plus expense amount
    cur.execute(
        "SELECT receipt_id FROM receipts WHERE description LIKE %s AND (LOWER(vendor_name)=LOWER(%s) OR LOWER(canonical_vendor)=LOWER(%s)) AND COALESCE(expense, gross_amount, net_amount)=%s",
        (signature + '%', parent.vendor, parent.vendor, fee_amount),
    )
    r = cur.fetchone()
    if r:
        return int(r[0])

    # Build insert with optional parent linkage
    linkage_cols = []
    linkage_vals = []
    if parent_col:
        linkage_cols.append(parent_col)
        linkage_vals.append(parent.receipt_id)

    cols = ["vendor_name", "canonical_vendor", "vendor_account_id", "receipt_date", "expense", "description"] + linkage_cols
    vals = [parent.vendor, parent.canonical_vendor, parent.vendor_account_id, parent.date, fee_amount, signature + f" | OD/Late fee for invoice {parent.invoice_number or ''}"] + linkage_vals

    placeholders = ", ".join(["%s"] * len(vals))
    sql = f"INSERT INTO receipts ({', '.join(cols)}) VALUES ({placeholders}) RETURNING receipt_id"
    cur.execute(sql, vals)
    new_id = cur.fetchone()[0]
    return int(new_id)


def update_parent_amount(cur, parent: InvoiceRow, base_amount: float):
    if abs(parent.amount - base_amount) < 0.01:
        return
    cur.execute(f"UPDATE receipts SET {parent.amount_column}=%s WHERE receipt_id=%s", (base_amount, parent.receipt_id))


def main():
    ap = argparse.ArgumentParser(description="Auto-split vendor invoices with OD/late fee into base + fee line items")
    ap.add_argument("--vendor", default="WCB", help="Vendor name filter (default: WCB)")
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    ap.add_argument("--write", action="store_true", help="Apply changes (mutually exclusive with --dry-run)")
    args = ap.parse_args()

    if args.dry_run and args.write:
        print("❌ Use either --dry-run or --write, not both.")
        sys.exit(2)

    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        rows = fetch_candidate_invoices(cur, args.vendor)
        parent_child_supported, parent_col = ensure_parent_child_support(cur)

        candidates = []
        for row in rows:
            split = compute_split(row)
            if split:
                candidates.append((row, split))

        if not candidates:
            print("No candidate invoices requiring split found.")
            return

        print(f"Found {len(candidates)} candidate invoice(s) for vendor {args.vendor}.")
        for parent, split in candidates:
            print(f"- ID {parent.receipt_id} | inv={parent.invoice_number or ''} | total={parent.amount:.2f} -> base={split.base_amount:.2f}, fee={split.fee_amount:.2f} | {split.reason}")

        if args.dry_run or not args.write:
            print("Dry-run only. No changes applied.")
            return

        # Apply changes atomically
        conn.autocommit = False
        for parent, split in candidates:
            update_parent_amount(cur, parent, split.base_amount)
            insert_fee_child(cur, parent, split.fee_amount, parent_col if parent_child_supported else None)
        conn.commit()
        print(f"✅ Applied splits for {len(candidates)} invoice(s).")
    except Exception as e:
        conn.rollback()
        print(f"❌ Rolled back due to error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
