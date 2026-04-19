import csv
from pathlib import Path
import psycopg2

BASE = Path(r"L:\limo\archive\tmp_zip_analysis")
DIRECT_FILE = BASE / "gl_direct_matches_completed.csv"
YEAR_FILES = [
    BASE / f"gl_vs_banking_unmatched_receipt_verification_{y}.csv" for y in (2012, 2013, 2014, 2015, 2016, 2017)
]

OUT_CONFIRMED = BASE / "confirmed_entries_added.csv"
OUT_COMPARE = BASE / "confirmed_entries_vs_receipts.csv"
OUT_CASH_REIMB = BASE / "receipts_cash_reimbursed_not_linked_to_banking.csv"
OUT_SUMMARY = BASE / "confirmed_and_receipts_summary.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")


def key(gl_date, gl_chq, gl_vendor, gl_amount):
    return f"{gl_date}|{(gl_chq or '').strip().lower()}|{(gl_vendor or '').strip().lower()}|{gl_amount}"


def load_confirmed_entries():
    confirmed = {}

    # 1) direct matches file
    with open(DIRECT_FILE, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            k = key(row.get("gl_date"), row.get("gl_chq"), row.get("gl_vendor"), row.get("gl_amount"))
            confirmed[k] = {
                "source": "direct_completed",
                "verification": "DIRECT_MATCH",
                "gl_date": row.get("gl_date"),
                "gl_chq": row.get("gl_chq"),
                "gl_vendor": row.get("gl_vendor"),
                "gl_amount": row.get("gl_amount"),
                "gl_account": row.get("gl_account"),
                "bank_txn_id": row.get("bank_id"),
                "bank_txn_date": row.get("bank_date"),
                "bank_debit": row.get("bank_debit"),
                "bank_desc": row.get("bank_desc"),
                "bank_check": row.get("bank_check"),
                "receipt_id": row.get("receipt_id") or row.get("reconciled_receipt_id") or "",
                "notes": row.get("match_reason") or "",
            }

    # 2) year verification files: only confirmed statuses
    for fpath in YEAR_FILES:
        if not fpath.exists():
            continue
        with open(fpath, encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                ver = (row.get("verification") or "").strip()
                if ver not in ("DIRECT_MATCH", "MERGED_MATCH", "RECEIPT_ONLY"):
                    continue
                k = key(row.get("gl_date"), row.get("gl_chq"), row.get("gl_vendor"), row.get("gl_amount"))
                # preserve direct file row as primary; add/update if not present
                if k not in confirmed:
                    confirmed[k] = {
                        "source": fpath.name,
                        "verification": ver,
                        "gl_date": row.get("gl_date"),
                        "gl_chq": row.get("gl_chq"),
                        "gl_vendor": row.get("gl_vendor"),
                        "gl_amount": row.get("gl_amount"),
                        "gl_account": row.get("gl_account"),
                        "bank_txn_id": row.get("bank_txn_id"),
                        "bank_txn_date": row.get("bank_txn_date"),
                        "bank_debit": row.get("bank_debit"),
                        "bank_desc": row.get("bank_desc"),
                        "bank_check": row.get("bank_check"),
                        "receipt_id": row.get("receipt_id") or "",
                        "notes": row.get("notes") or "",
                    }
                else:
                    # If existing has no receipt_id, enrich it.
                    if (not confirmed[k].get("receipt_id")) and row.get("receipt_id"):
                        confirmed[k]["receipt_id"] = row.get("receipt_id")
                    # Keep a note of extra confirmation source
                    extra = confirmed[k].get("notes", "")
                    src_tag = f"+{ver}@{fpath.name}"
                    if src_tag not in extra:
                        confirmed[k]["notes"] = (extra + " " + src_tag).strip()

    rows = list(confirmed.values())
    rows.sort(key=lambda x: (x.get("gl_date") or "", x.get("gl_vendor") or "", x.get("gl_amount") or ""))
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def compare_confirmed_to_receipts(conn, confirmed_rows):
    cur = conn.cursor()
    out = []

    for r in confirmed_rows:
        rid = r.get("receipt_id")
        bank_txn_id = r.get("bank_txn_id")

        # If receipt_id is missing in the CSV row but bank transaction exists,
        # backfill it from banking_transactions links.
        if (not rid) and bank_txn_id:
            cur.execute(
                """
                SELECT receipt_id, reconciled_receipt_id
                FROM banking_transactions
                WHERE transaction_id = %s
                """,
                (bank_txn_id,),
            )
            b = cur.fetchone()
            if b:
                rid = b[0] if b[0] is not None else b[1]
                if rid is not None:
                    rid = str(rid)
                    r["receipt_id"] = rid
        row = dict(r)
        row.update(
            {
                "receipt_exists": "0",
                "receipt_date": "",
                "receipt_vendor": "",
                "receipt_amount": "",
                "receipt_payment_method": "",
                "receipt_is_driver_reimbursement": "",
                "receipt_reimbursed_via": "",
                "receipt_banking_transaction_id": "",
                "receipt_is_matched": "",
                "bank_links_via_banking_table": "0",
            }
        )

        if rid:
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       payment_method, is_driver_reimbursement, reimbursed_via,
                       banking_transaction_id, is_matched
                FROM receipts
                WHERE receipt_id = %s
                """,
                (rid,),
            )
            rr = cur.fetchone()
            if rr:
                row.update(
                    {
                        "receipt_exists": "1",
                        "receipt_date": str(rr[1]) if rr[1] is not None else "",
                        "receipt_vendor": rr[2] or "",
                        "receipt_amount": str(rr[3]) if rr[3] is not None else "",
                        "receipt_payment_method": rr[4] or "",
                        "receipt_is_driver_reimbursement": str(rr[5]) if rr[5] is not None else "",
                        "receipt_reimbursed_via": rr[6] or "",
                        "receipt_banking_transaction_id": str(rr[7]) if rr[7] is not None else "",
                        "receipt_is_matched": str(rr[8]) if rr[8] is not None else "",
                    }
                )

            # link via banking table receipt refs
            cur.execute(
                """
                SELECT COUNT(*)
                FROM banking_transactions
                WHERE receipt_id = %s OR reconciled_receipt_id = %s
                """,
                (rid, rid),
            )
            cnt = cur.fetchone()[0]
            row["bank_links_via_banking_table"] = str(cnt)

        out.append(row)

    cur.close()
    return out


def extract_cash_reimbursed_unlinked(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
               r.payment_method, r.canonical_pay_method,
               r.is_driver_reimbursement, r.reimbursed_via,
               r.banking_transaction_id, r.is_matched, r.receipt_source
        FROM receipts r
        WHERE (
                COALESCE(r.payment_method, '') ILIKE 'cash%%'
                OR COALESCE(r.canonical_pay_method, '') ILIKE 'cash%%'
                OR COALESCE(r.payment_method, '') ILIKE '%%reimb%%'
                OR COALESCE(r.reimbursed_via, '') <> ''
                OR COALESCE(r.is_driver_reimbursement, FALSE) = TRUE
              )
          AND COALESCE(r.is_voided, FALSE) = FALSE
          AND COALESCE(r.exclude_from_reports, FALSE) = FALSE
          AND r.receipt_date BETWEEN DATE '2012-01-01' AND DATE '2017-12-31'
          AND COALESCE(r.banking_transaction_id, 0) = 0
          AND NOT EXISTS (
                SELECT 1 FROM banking_transactions b
                WHERE b.receipt_id = r.receipt_id OR b.reconciled_receipt_id = r.receipt_id
          )
        ORDER BY r.receipt_date, r.receipt_id
        """
    )
    rows = []
    for rr in cur.fetchall():
        rows.append(
            {
                "receipt_id": rr[0],
                "receipt_date": str(rr[1]) if rr[1] is not None else "",
                "vendor_name": rr[2] or "",
                "gross_amount": str(rr[3]) if rr[3] is not None else "",
                "payment_method": rr[4] or "",
                "canonical_pay_method": rr[5] or "",
                "is_driver_reimbursement": str(rr[6]) if rr[6] is not None else "",
                "reimbursed_via": rr[7] or "",
                "banking_transaction_id": str(rr[8]) if rr[8] is not None else "",
                "is_matched": str(rr[9]) if rr[9] is not None else "",
                "receipt_source": rr[10] or "",
            }
        )
    cur.close()
    return rows


def main():
    confirmed = load_confirmed_entries()

    confirmed_fields = [
        "source",
        "verification",
        "gl_date",
        "gl_chq",
        "gl_vendor",
        "gl_amount",
        "gl_account",
        "bank_txn_id",
        "bank_txn_date",
        "bank_debit",
        "bank_desc",
        "bank_check",
        "receipt_id",
        "notes",
    ]
    write_csv(OUT_CONFIRMED, confirmed, confirmed_fields)

    conn = psycopg2.connect(**DB)
    compare = compare_confirmed_to_receipts(conn, confirmed)
    cash_unlinked = extract_cash_reimbursed_unlinked(conn)
    conn.close()

    compare_fields = confirmed_fields + [
        "receipt_exists",
        "receipt_date",
        "receipt_vendor",
        "receipt_amount",
        "receipt_payment_method",
        "receipt_is_driver_reimbursement",
        "receipt_reimbursed_via",
        "receipt_banking_transaction_id",
        "receipt_is_matched",
        "bank_links_via_banking_table",
    ]
    write_csv(OUT_COMPARE, compare, compare_fields)

    cash_fields = [
        "receipt_id",
        "receipt_date",
        "vendor_name",
        "gross_amount",
        "payment_method",
        "canonical_pay_method",
        "is_driver_reimbursement",
        "reimbursed_via",
        "banking_transaction_id",
        "is_matched",
        "receipt_source",
    ]
    write_csv(OUT_CASH_REIMB, cash_unlinked, cash_fields)

    by_ver = {}
    for r in confirmed:
        v = r.get("verification", "")
        by_ver[v] = by_ver.get(v, 0) + 1

    missing_receipt = sum(1 for r in compare if r.get("receipt_exists") != "1")
    no_bank_link = sum(1 for r in compare if r.get("bank_links_via_banking_table") in ("0", "", None))

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("Confirmed Entries + Receipt Comparison Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Confirmed entries added: {len(confirmed)}\n")
        for k in sorted(by_ver):
            f.write(f"- {k}: {by_ver[k]}\n")
        f.write(f"Confirmed entries missing receipt record: {missing_receipt}\n")
        f.write(f"Confirmed entries with no bank link via banking table: {no_bank_link}\n")
        f.write(f"Cash/reimbursed receipts not linked to banking (2012-2017): {len(cash_unlinked)}\n")

    print(f"Confirmed entries added: {len(confirmed)}")
    print(f"Missing receipt on confirmed rows: {missing_receipt}")
    print(f"No bank link on confirmed rows: {no_bank_link}")
    print(f"Cash/reimbursed receipts not linked to banking: {len(cash_unlinked)}")
    print(f"Wrote: {OUT_CONFIRMED}")
    print(f"Wrote: {OUT_COMPARE}")
    print(f"Wrote: {OUT_CASH_REIMB}")
    print(f"Wrote: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
