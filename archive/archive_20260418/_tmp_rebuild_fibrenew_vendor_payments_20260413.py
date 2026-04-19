import re
import sys
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

APPLY = "--apply" in sys.argv
VENDOR_NAME = "FIBRENEW"
VENDOR_ACCOUNT_ID = 1
GENERATED_NOTE_PREFIX = "Auto-linked from Fibrenew receipt #"
BACKUP_TABLE = "backup_fibrenew_payment_like_invoices_20260413"


def is_generic_description(desc):
    s = (desc or "").strip().upper()
    if not s:
        return True
    if re.fullmatch(r"CHQ\s*#?\s*\d+\s*FIBRENEW", s):
        return True
    if s in {"FIBRENEW", "PAYMENT"}:
        return True
    return False


def score_receipt(row):
    desc = (row.get("description") or "").strip()
    score = 0
    if not is_generic_description(desc):
        score += 1000
    if row.get("banking_transaction_id"):
        score += 100
    if (row.get("receipt_source") or "").lower().startswith("manual"):
        score += 25
    score += len(desc)
    return score


def infer_method(row):
    return row.get("payment_method") or row.get("pay_method") or "unknown"


conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
conn.autocommit = False
cur = conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute(
        """
        SELECT vendor_invoice_id, invoice_number, invoice_date, invoice_amount, notes
        FROM vendor_invoices
        WHERE vendor_name = %s
          AND COALESCE(invoice_number, '') <> 'BANKING_IMPORT'
        ORDER BY invoice_date, vendor_invoice_id
        """,
        (VENDOR_NAME,),
    )
    invoice_rows = cur.fetchall()

    payment_like_invoice_ids = []
    invoices = []
    for row in invoice_rows:
        notes = (row.get("notes") or "").strip().upper()
        if notes.startswith("PAYMENT "):
            payment_like_invoice_ids.append(row["vendor_invoice_id"])
            continue
        invoices.append({
            "invoice_id": row["vendor_invoice_id"],
            "invoice_number": row.get("invoice_number"),
            "invoice_date": row["invoice_date"],
            "notes": row.get("notes") or "",
            "remaining": Decimal(str(row["invoice_amount"] or 0)),
        })

    cur.execute(
        """
        SELECT receipt_id, receipt_date, gross_amount, payment_method, pay_method,
               source_reference, description, receipt_source, banking_transaction_id
        FROM receipts
        WHERE vendor_account_id = %s
          AND COALESCE(is_voided, false) = false
        ORDER BY receipt_date, receipt_id
        """,
        (VENDOR_ACCOUNT_ID,),
    )
    receipt_rows = cur.fetchall()

    groups = {}
    for row in receipt_rows:
        key = (row["receipt_date"], Decimal(str(row["gross_amount"] or 0)))
        groups.setdefault(key, []).append(row)

    candidate_receipts = []
    skipped_duplicates = []

    for _key, rows in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        if len(rows) == 1:
            candidate_receipts.append(rows[0])
            continue

        any_generic = any(is_generic_description(r.get("description")) for r in rows)
        any_detailed = any(not is_generic_description(r.get("description")) for r in rows)

        if any_generic and any_detailed:
            best = sorted(rows, key=score_receipt, reverse=True)[0]
            # Borrow a banking transaction id from the duplicate set when available.
            if not best.get("banking_transaction_id"):
                for other in rows:
                    if other.get("banking_transaction_id"):
                        best = dict(best)
                        best["banking_transaction_id"] = other["banking_transaction_id"]
                        break
            candidate_receipts.append(best)
            for other in rows:
                if other["receipt_id"] != best["receipt_id"]:
                    skipped_duplicates.append(other)
        else:
            candidate_receipts.extend(rows)

    allocations = []
    invoice_index = 0

    for receipt in candidate_receipts:
        remaining_payment = Decimal(str(receipt["gross_amount"] or 0)).quantize(Decimal("0.01"))
        if remaining_payment <= 0:
            continue

        receipt_allocs = []
        while remaining_payment > Decimal("0.00") and invoice_index < len(invoices):
            invoice = invoices[invoice_index]
            if invoice["remaining"] <= Decimal("0.00"):
                invoice_index += 1
                continue

            applied = min(invoice["remaining"], remaining_payment)
            if applied <= Decimal("0.00"):
                break

            receipt_allocs.append({
                "receipt": receipt,
                "invoice_id": invoice["invoice_id"],
                "invoice_number": invoice["invoice_number"],
                "payment_amount": applied,
            })
            invoice["remaining"] -= applied
            remaining_payment -= applied

            if invoice["remaining"] <= Decimal("0.00"):
                invoice_index += 1

        allocations.extend(receipt_allocs)

    total_allocated = sum((a["payment_amount"] for a in allocations), Decimal("0.00"))

    print(f"Candidate Fibrenew receipts: {len(candidate_receipts)}")
    print(f"Skipped duplicate-style rows: {len(skipped_duplicates)}")
    print(f"Allocations to insert: {len(allocations)}")
    print(f"Total allocated: ${total_allocated:,.2f}")
    print(f"Payment-like invoice ids to remove: {payment_like_invoice_ids}")

    if not APPLY:
        for alloc in allocations[:15]:
            r = alloc["receipt"]
            print(
                f"DRY receipt {r['receipt_id']} {r['receipt_date']} ${float(alloc['payment_amount']):,.2f} -> invoice {alloc['invoice_number']} ({alloc['invoice_id']})"
            )
        conn.rollback()
        print("Mode: DRY RUN")
        sys.exit(0)

    # Backup and remove the clearly misclassified payment-like invoice row(s).
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} AS SELECT * FROM vendor_invoices WHERE 1=0"
    )
    if payment_like_invoice_ids:
        cur.execute(
            f"INSERT INTO {BACKUP_TABLE} SELECT * FROM vendor_invoices WHERE vendor_invoice_id = ANY(%s)",
            (payment_like_invoice_ids,),
        )
        cur.execute(
            "DELETE FROM vendor_invoices WHERE vendor_invoice_id = ANY(%s)",
            (payment_like_invoice_ids,),
        )

    # Clear previously generated Fibrenew payment links and rebuild.
    cur.execute(
        "DELETE FROM vendor_invoice_payments WHERE notes LIKE %s",
        (GENERATED_NOTE_PREFIX + "%",),
    )

    inserted = 0
    linked_receipts = 0
    single_invoice_receipt_ids = set()

    alloc_count_by_receipt = {}
    for alloc in allocations:
        alloc_count_by_receipt.setdefault(alloc["receipt"]["receipt_id"], 0)
        alloc_count_by_receipt[alloc["receipt"]["receipt_id"]] += 1

    for alloc in allocations:
        receipt = alloc["receipt"]
        payment_amount = alloc["payment_amount"].quantize(Decimal("0.01"))
        payment_method = infer_method(receipt)
        reference = receipt.get("source_reference") or f"receipt#{receipt['receipt_id']}"
        note_desc = (receipt.get("description") or "").strip()
        notes = (
            f"{GENERATED_NOTE_PREFIX}{receipt['receipt_id']}; "
            f"source={receipt.get('receipt_source') or 'unknown'}; {note_desc}"
        )

        cur.execute(
            """
            INSERT INTO vendor_invoice_payments (
                receipt_id, payment_date, payment_amount, payment_method,
                reference, banking_transaction_id, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                alloc["invoice_id"],
                receipt["receipt_date"],
                float(payment_amount),
                payment_method,
                reference,
                receipt.get("banking_transaction_id"),
                notes,
            ),
        )
        inserted += 1

        if alloc_count_by_receipt[receipt["receipt_id"]] == 1:
            cur.execute(
                "UPDATE receipts SET vendor_invoice_id = %s WHERE receipt_id = %s",
                (alloc["invoice_id"], receipt["receipt_id"]),
            )
            linked_receipts += cur.rowcount
            single_invoice_receipt_ids.add(receipt["receipt_id"])

    conn.commit()
    print(f"Inserted payment rows: {inserted}")
    print(f"Single-invoice receipt links updated: {linked_receipts}")
    print("Mode: APPLY")

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
