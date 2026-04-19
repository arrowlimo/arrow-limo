import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
AUDIT_DIR = Path(r"l:\limo\data\audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def d(val):
    if val is None:
        return Decimal("0")
    return Decimal(str(val))


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    report_lines = []
    report_lines.append("VERIFY REPORT: NSF / LEASE 2012-2014 / ITC / DUPLICATES")
    report_lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    report_lines.append("")

    # 1) NSF / STOP / CORRECTION marking checks
    report_lines.append("1) NSF / STOP PAYMENT / CORRECTION MARKING")

    keyword_patterns = {
        "nsf": r"(\\mNSF\\M|NON[- ]?SUFFICIENT|INSUFFICIENT|RETURNED ITEM|BOUNCED)",
        "stop": r"(STOP\\s*PAY(?:MENT)?|STOPPYMT)",
        "corr": r"(CORRECTION|ADJUSTMENT|REVERSAL|REVERSE|BANK ERROR)",
    }

    for key, pattern in keyword_patterns.items():
        cur.execute(
            f"""
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE COALESCE(is_nsf, false) = true) AS marked_nsf,
              COUNT(*) FILTER (WHERE COALESCE(is_voided, false) = true) AS marked_voided,
              COUNT(*) FILTER (WHERE COALESCE(exclude_from_reports, false) = true) AS marked_excluded
            FROM receipts
            WHERE (COALESCE(vendor_name,'') || ' ' || COALESCE(description,'')) ~* %s
            """,
            (pattern,),
        )
        r = cur.fetchone()
        report_lines.append(
            f"receipts keyword={key}: total={r['total']}, is_nsf={r['marked_nsf']}, is_voided={r['marked_voided']}, excluded={r['marked_excluded']}"
        )

    for key, pattern in keyword_patterns.items():
        cur.execute(
            f"""
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE COALESCE(is_nsf_charge, false) = true) AS marked_nsf_charge,
              COUNT(*) FILTER (WHERE COALESCE(category,'') ~* '(NSF|STOP|CORR)') AS categorized
            FROM banking_transactions
            WHERE COALESCE(description,'') ~* %s
            """,
            (pattern,),
        )
        r = cur.fetchone()
        report_lines.append(
            f"banking keyword={key}: total={r['total']}, is_nsf_charge={r['marked_nsf_charge']}, category-tagged={r['categorized']}"
        )

    # Potential unmarked rows
    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, is_nsf, is_voided, exclude_from_reports, description
        FROM receipts
        WHERE (COALESCE(vendor_name,'') || ' ' || COALESCE(description,'')) ~* '(\\mNSF\\M|NON[- ]?SUFFICIENT|INSUFFICIENT|RETURNED ITEM|BOUNCED|STOP\\s*PAY(?:MENT)?|CORRECTION|ADJUSTMENT|REVERSAL|REVERSE|BANK ERROR)'
          AND COALESCE(is_nsf,false)=false
          AND COALESCE(is_voided,false)=false
          AND COALESCE(exclude_from_reports,false)=false
        ORDER BY receipt_date, receipt_id
        LIMIT 50
        """
    )
    unmarked_receipts = cur.fetchall()
    report_lines.append(f"potentially-unmarked receipts (top 50): {len(unmarked_receipts)}")

    # 2) 2012-2014 lease receipts presence + GL + GST handling
    report_lines.append("")
    report_lines.append("2) LEASE RECEIPTS 2012-2014 (presence, GL coding, GST/ITC handling)")

    lease_regex = r"(LEASE|FORD\\s*CREDIT|TOYOTA\\s*CREDIT|GM\\s*FINANCIAL|MERCEDES|HONDA\\s*FINANCE|VEHICLE\\s*LEASE|AUTO\\s*LEASE|LOAN\\s*PAYMENT)"

    cur.execute(
        """
        WITH lease_receipts AS (
          SELECT *
          FROM receipts
          WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
            AND (
              COALESCE(vendor_name,'') ~* %s
              OR COALESCE(canonical_vendor,'') ~* %s
              OR COALESCE(description,'') ~* %s
              OR COALESCE(category,'') ~* %s
              OR COALESCE(expense::text,'') ~* %s
            )
        )
        SELECT
          COUNT(*) AS cnt,
          COALESCE(SUM(gross_amount),0) AS total,
          COUNT(*) FILTER (WHERE COALESCE(gl_account_code,'')='' AND COALESCE(gl_code,'')='') AS missing_gl,
          COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND COALESCE(gross_amount,0)>0 AND COALESCE(gst_amount,0)=0) AS missing_gst,
          COUNT(*) FILTER (WHERE vehicle_id IS NULL AND COALESCE(vehicle_number,'')='') AS missing_vehicle
        FROM lease_receipts
        """,
        (lease_regex, lease_regex, lease_regex, lease_regex, lease_regex),
    )
    lease_summary = cur.fetchone()
    report_lines.append(
        f"lease-like receipts: count={lease_summary['cnt']}, total=${d(lease_summary['total']):,.2f}, missing_gl={lease_summary['missing_gl']}, missing_gst={lease_summary['missing_gst']}, missing_vehicle_ref={lease_summary['missing_vehicle']}"
    )

    cur.execute(
        """
        WITH lease_receipts AS (
          SELECT *
          FROM receipts
          WHERE receipt_date >= DATE '2012-01-01' AND receipt_date < DATE '2015-01-01'
            AND (
              COALESCE(vendor_name,'') ~* %s
              OR COALESCE(canonical_vendor,'') ~* %s
              OR COALESCE(description,'') ~* %s
              OR COALESCE(category,'') ~* %s
              OR COALESCE(expense::text,'') ~* %s
            )
        )
        SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
               COUNT(*) AS cnt,
               COALESCE(SUM(gross_amount),0) AS total,
               COUNT(*) FILTER (WHERE COALESCE(gl_account_code,'')='' AND COALESCE(gl_code,'')='') AS missing_gl,
               COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND COALESCE(gross_amount,0)>0 AND COALESCE(gst_amount,0)=0) AS missing_gst
        FROM lease_receipts
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY yr
        """,
        (lease_regex, lease_regex, lease_regex, lease_regex, lease_regex),
    )
    lease_by_year = cur.fetchall()
    for r in lease_by_year:
        report_lines.append(
            f"year={r['yr']}: count={r['cnt']}, total=${d(r['total']):,.2f}, missing_gl={r['missing_gl']}, missing_gst={r['missing_gst']}"
        )

    # Compare to banking lease-like transactions in same period
    cur.execute(
        """
        WITH lease_banking AS (
          SELECT bt.transaction_id, bt.transaction_date, bt.description,
                 COALESCE(bt.debit_amount,0) AS debit_amount,
                 bt.account_number
          FROM banking_transactions bt
          WHERE bt.transaction_date >= DATE '2012-01-01' AND bt.transaction_date < DATE '2015-01-01'
            AND COALESCE(bt.debit_amount,0) > 0
            AND COALESCE(bt.description,'') ~* %s
        )
        SELECT
          COUNT(*) AS total_lease_banking,
          COUNT(*) FILTER (WHERE r.receipt_id IS NOT NULL) AS with_linked_receipt,
          COUNT(*) FILTER (WHERE r.receipt_id IS NULL) AS without_linked_receipt
        FROM lease_banking lb
        LEFT JOIN receipts r ON r.banking_transaction_id = lb.transaction_id
        """,
        (lease_regex,),
    )
    lease_bank_cov = cur.fetchone()
    report_lines.append(
        f"banking lease-like txns: total={lease_bank_cov['total_lease_banking']}, linked_receipt={lease_bank_cov['with_linked_receipt']}, missing_link={lease_bank_cov['without_linked_receipt']}"
    )

    # 3) ITC calculations
    report_lines.append("")
    report_lines.append("3) ITC CALCULATION CHECKS")

    # 3a: Lease profile ITC consistency
    cur.execute(
        """
        SELECT
          COUNT(*) AS profiles,
          COUNT(*) FILTER (
            WHERE ABS(
              COALESCE(itc_amount,0)
              - ROUND(COALESCE(total_gst_charged,0) * (COALESCE(business_use_percent,0) / 100.0), 2)
            ) > 0.02
          ) AS itc_mismatch,
          COUNT(*) FILTER (WHERE COALESCE(itc_verified,false)=true) AS verified_profiles
        FROM vehicle_lease_profiles
        """
    )
    itc_profile = cur.fetchone()
    report_lines.append(
        f"lease_profiles={itc_profile['profiles']}, itc_formula_mismatch={itc_profile['itc_mismatch']}, verified_profiles={itc_profile['verified_profiles']}"
    )

    # 3b: Receipt GST plausibility for ITC-like business expenses
    cur.execute(
        """
        WITH base AS (
          SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_exempt,
                 COALESCE(gl_account_code, gl_code, '') AS gl_used,
                 COALESCE(exclude_from_reports,false) AS excluded,
                 COALESCE(is_nsf,false) AS is_nsf,
                 ROUND((COALESCE(gross_amount,0) * 0.05 / 1.05)::numeric, 2) AS expected_gst
          FROM receipts
          WHERE COALESCE(gross_amount,0) > 0
            AND COALESCE(exclude_from_reports,false) = false
            AND COALESCE(is_nsf,false) = false
        )
        SELECT
          COUNT(*) AS cnt,
          COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND COALESCE(gst_amount,0)=0) AS zero_gst_nonexempt,
          COUNT(*) FILTER (WHERE COALESCE(gst_exempt,false)=false AND ABS(COALESCE(gst_amount,0)-expected_gst) > 0.05) AS gst_formula_outlier,
          COUNT(*) FILTER (WHERE COALESCE(gst_amount,0) > COALESCE(gross_amount,0) * 0.2) AS gst_unusually_high
        FROM base
        """
    )
    gst_check = cur.fetchone()
    report_lines.append(
        f"business receipts checked={gst_check['cnt']}, zero_gst_nonexempt={gst_check['zero_gst_nonexempt']}, gst_formula_outlier={gst_check['gst_formula_outlier']}, gst_unusually_high={gst_check['gst_unusually_high']}"
    )

    # 4) Duplicate receipts report (exact amount + same vendor within 3 days, cross-account)
    report_lines.append("")
    report_lines.append("4) DUPLICATE CANDIDATES (same vendor + exact amount within 3 days, no deletions)")

    cur.execute(
        """
        WITH base AS (
          SELECT
            r.receipt_id,
            r.receipt_date,
            UPPER(TRIM(COALESCE(NULLIF(r.canonical_vendor,''), r.vendor_name, ''))) AS vendor_norm,
            ROUND(COALESCE(r.gross_amount,0)::numeric, 2) AS amount,
            r.vendor_name,
            r.canonical_vendor,
            r.description,
            r.banking_transaction_id,
            bt.account_number
          FROM receipts r
          LEFT JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
          WHERE COALESCE(r.gross_amount,0) <> 0
            AND COALESCE(r.is_voided,false)=false
        )
        SELECT
          b1.receipt_id AS receipt_id_1,
          b1.receipt_date AS date_1,
          b2.receipt_id AS receipt_id_2,
          b2.receipt_date AS date_2,
          b1.vendor_norm,
          b1.amount,
          b1.vendor_name AS vendor_1,
          b2.vendor_name AS vendor_2,
          b1.account_number AS account_1,
          b2.account_number AS account_2,
          b1.banking_transaction_id AS banking_txn_1,
          b2.banking_transaction_id AS banking_txn_2,
          b1.description AS description_1,
          b2.description AS description_2,
          ABS(b2.receipt_date - b1.receipt_date) AS day_gap
        FROM base b1
        JOIN base b2
          ON b1.receipt_id < b2.receipt_id
         AND b1.vendor_norm <> ''
         AND b1.vendor_norm = b2.vendor_norm
         AND b1.amount = b2.amount
         AND ABS(b2.receipt_date - b1.receipt_date) <= 3
        ORDER BY b1.vendor_norm, b1.amount, b1.receipt_date, b2.receipt_date
        """
    )
    dup_rows = cur.fetchall()

    dup_csv = AUDIT_DIR / f"receipt_duplicates_vendor_amount_3days_{STAMP}.csv"
    with dup_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "receipt_id_1", "date_1", "receipt_id_2", "date_2", "vendor_norm", "amount",
            "vendor_1", "vendor_2", "account_1", "account_2", "banking_txn_1", "banking_txn_2",
            "day_gap", "description_1", "description_2"
        ])
        for r in dup_rows:
            w.writerow([
                r["receipt_id_1"], r["date_1"], r["receipt_id_2"], r["date_2"], r["vendor_norm"], float(d(r["amount"])),
                r["vendor_1"], r["vendor_2"], r["account_1"], r["account_2"], r["banking_txn_1"], r["banking_txn_2"],
                r["day_gap"], r["description_1"], r["description_2"]
            ])

    report_lines.append(f"duplicate pairs found={len(dup_rows)}")
    report_lines.append(f"duplicate csv={dup_csv}")

    # Focus accounts 8362/1615/6011
    focus = [
        r for r in dup_rows
        if ((r["account_1"] and any(x in str(r["account_1"]) for x in ["8362", "1615", "6011"]))
            or (r["account_2"] and any(x in str(r["account_2"]) for x in ["8362", "1615", "6011"])))
    ]
    report_lines.append(f"duplicate pairs touching 8362/1615/6011={len(focus)}")

    cross_8362_1615 = [
        r for r in dup_rows
        if (r["account_1"] and r["account_2"] and
            (("8362" in str(r["account_1"]) and "1615" in str(r["account_2"]))
             or ("1615" in str(r["account_1"]) and "8362" in str(r["account_2"]))))
    ]
    report_lines.append(f"explicit cross-account 8362<->1615 duplicate pairs={len(cross_8362_1615)}")

    cross_8362_6011 = [
        r for r in dup_rows
        if (r["account_1"] and r["account_2"] and
            (("8362" in str(r["account_1"]) and "6011" in str(r["account_2"]))
             or ("6011" in str(r["account_1"]) and "8362" in str(r["account_2"]))))
    ]
    report_lines.append(f"explicit cross-account 8362<->6011 duplicate pairs={len(cross_8362_6011)}")

    # Top obvious monthly-style duplicates (insurance-like)
    cur.execute(
        """
        WITH base AS (
          SELECT
            UPPER(TRIM(COALESCE(NULLIF(canonical_vendor,''), vendor_name, ''))) AS vendor_norm,
            ROUND(COALESCE(gross_amount,0)::numeric, 2) AS amount,
            receipt_id,
            receipt_date
          FROM receipts
          WHERE COALESCE(gross_amount,0) <> 0
            AND COALESCE(is_voided,false)=false
        )
        SELECT vendor_norm, amount, COUNT(*) AS cnt,
               MIN(receipt_date) AS first_date,
               MAX(receipt_date) AS last_date
        FROM base
        GROUP BY vendor_norm, amount
        HAVING COUNT(*) >= 2
        ORDER BY cnt DESC, vendor_norm
        LIMIT 25
        """
    )
    top_repeat = cur.fetchall()
    report_lines.append("top repeated vendor+amount combos (not all are errors):")
    for r in top_repeat:
        report_lines.append(
            f"  {r['vendor_norm']} | ${d(r['amount']):,.2f} | count={r['cnt']} | {r['first_date']}..{r['last_date']}"
        )

    # Write details of unmarked receipts sample
    unmarked_csv = AUDIT_DIR / f"potentially_unmarked_nsf_stop_corr_receipts_{STAMP}.csv"
    with unmarked_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["receipt_id", "receipt_date", "vendor_name", "gross_amount", "is_nsf", "is_voided", "exclude_from_reports", "description"])
        for r in unmarked_receipts:
            w.writerow([
                r["receipt_id"], r["receipt_date"], r["vendor_name"], float(d(r["gross_amount"])),
                r["is_nsf"], r["is_voided"], r["exclude_from_reports"], r["description"]
            ])
    report_lines.append(f"potentially unmarked sample csv={unmarked_csv}")

    report_path = AUDIT_DIR / f"verify_nsf_lease_itc_duplicates_{STAMP}.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    conn.rollback()  # Explicitly keep this run read-only.
    cur.close()
    conn.close()

    print(f"REPORT_PATH: {report_path}")
    print(f"DUPLICATE_CSV: {dup_csv}")
    print(f"UNMARKED_CSV: {unmarked_csv}")
    print("\n".join(report_lines[:40]))


if __name__ == "__main__":
    main()
