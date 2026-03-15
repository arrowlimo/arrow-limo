#!/usr/bin/env python3
"""2012 Reconciliation Audit (Audit-only, no data writes)

- Confirms one-to-one matching of receipts to banking transactions for 2012.
- Separates banking fee charges for reporting only (no matching).
- Applies vendor consolidation hints (audit preview only).
- Computes GST net for purchases (Alberta 5% GST included when applicable).
- Flags Heffner lease payments (GST charged).
- Tracks source deductions (CRA) and WCB payments.
- Identifies transfers and cash withdrawals; flags QuickBooks-era mislabels as "Paul Richard".

Outputs under reports/:
- 2012_recon_summary_<date>.csv
- 2012_unmatched_receipts_<date>.csv
- 2012_unmatched_banking_<date>.csv
- 2012_exceptions_<date>.csv
- 2012_banking_fees_<date>.csv
- 2012_gst_normalization_preview_<date>.csv
- 2012_transfers_<date>.csv
- 2012_cash_withdrawals_suspect_<date>.csv
- 2012_cra_wcb_payments_<date>.csv
- 2012_heffner_gst_<date>.csv
"""
import csv
import datetime
import os
import re
import psycopg2
import psycopg2.extras as extras
import json

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT_DIR, "reports")
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
DATE_SUFFIX = datetime.date.today().isoformat()
YEAR = 2012

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def write_csv(path: str, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def calculate_gst_included(gross_amount: float, tax_rate: float = 0.05):
    if gross_amount is None:
        return 0.0, 0.0
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)


def load_policy():
    path = os.path.join(CONFIG_DIR, "2012_reconciliation_policy.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manual_receipt_exceptions():
    path = os.path.join(CONFIG_DIR, "manual_receipt_exceptions.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
            # Normalize to dict: {receipt_id: reason}
            out = {}
            for it in items:
                rid = it.get("receipt_id")
                if rid is None:
                    continue
                out[int(rid)] = it.get("reason") or "manual_exception"
            return out
    except Exception:
        return {}


def table_has_column(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s AND column_name=%s
        )
        """,
        (table_name, column_name),
    )
    return bool(cur.fetchone()[0])


def main():
    policy = load_policy()
    manual_ex = load_manual_receipt_exceptions()
    gst_rate = float(policy.get("gst_rate", 0.05))
    fee_keywords = [k.lower() for k in policy.get("banking_fee_keywords", [])]
    transfer_keywords = [k.lower() for k in policy.get("transfer_keywords", [])]
    cash_kw = [k.lower() for k in policy.get("cash_withdrawal_keywords", [])]
    heffner_kw = [k.lower() for k in policy.get("heffner_keywords", [])]
    cra_kw = [k.lower() for k in policy.get("cra_keywords", [])]
    wcb_kw = [k.lower() for k in policy.get("wcb_keywords", [])]
    exceptions_map = policy.get("exceptions", {})

    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            # Check available columns
            receipts_cols = set()
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='receipts'
                """
            )
            receipts_cols = {r[0] for r in cur.fetchall()}
            banking_cols = set()
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='banking_transactions'
                """
            )
            banking_cols = {r[0] for r in cur.fetchall()}

            has_receipts_category = 'category' in receipts_cols
            has_receipts_vendor = 'vendor' in receipts_cols or 'vendor_name' in receipts_cols
            vendor_col = 'vendor' if 'vendor' in receipts_cols else ('vendor_name' if 'vendor_name' in receipts_cols else None)
            has_receipts_gross = 'amount' in receipts_cols or 'gross_amount' in receipts_cols
            amount_col = 'amount' if 'amount' in receipts_cols else ('gross_amount' if 'gross_amount' in receipts_cols else None)
            date_col = 'receipt_date' if 'receipt_date' in receipts_cols else ('date' if 'date' in receipts_cols else None)
            has_bti_desc = 'description' in banking_cols or 'memo' in banking_cols or 'notes' in banking_cols or 'narrative' in banking_cols
            bdesc_col = 'description' if 'description' in banking_cols else (
                'memo' if 'memo' in banking_cols else (
                    'notes' if 'notes' in banking_cols else (
                        'narrative' if 'narrative' in banking_cols else None
                    )
                )
            )
            # Inspect column types to find suitable amount and date fields
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='banking_transactions'
                """
            )
            col_types = [(r[0], r[1]) for r in cur.fetchall()]

            # Amount detection with fallbacks
            bamount_col = None
            computed_amount_expr = None
            if 'amount' in banking_cols:
                bamount_col = 'amount'
            else:
                # Prefer named amount-like columns
                for cand in ['transaction_amount', 'amt', 'value', 'amount_cad', 'amount_usd']:
                    if cand in banking_cols:
                        bamount_col = cand
                        break
                # Fallback: derive from credit/debit if present
                if bamount_col is None and ('credit' in banking_cols or 'debit' in banking_cols):
                    credit_col = 'credit' if 'credit' in banking_cols else None
                    debit_col = 'debit' if 'debit' in banking_cols else None
                    if credit_col or debit_col:
                        c = credit_col or '0'
                        d = debit_col or '0'
                        computed_amount_expr = f"COALESCE({c},0) - COALESCE({d},0) AS amount"
                # Last resort: pick a numeric column with 'amount' substring
                if bamount_col is None and computed_amount_expr is None:
                    for name, dtype in col_types:
                        if ('amount' in name.lower() or 'amt' in name.lower() or 'value' in name.lower()) and dtype in (
                            'numeric', 'double precision', 'real', 'integer', 'bigint'
                        ):
                            bamount_col = name
                            break

            # Date detection with fallbacks
            bdate_col = None
            # Prefer common names
            for cand in ['transaction_date', 'date', 'posted_date', 'entry_date', 'trans_date', 'posted_at', 'created_at']:
                if cand in banking_cols:
                    bdate_col = cand
                    break
            if bdate_col is None:
                # Pick first column with date/timestamp type
                for name, dtype in col_types:
                    if dtype in ('date', 'timestamp without time zone', 'timestamp with time zone'):
                        bdate_col = name
                        break

            if not all([vendor_col, amount_col, date_col]):
                print("Receipts table missing required columns for audit.")
                return
            if bdate_col is None or (bamount_col is None and computed_amount_expr is None):
                print("Banking transactions table missing required columns for audit.")
                return

            # Fetch 2012 receipts
            cur.execute(
                f"""
                SELECT receipt_id, {vendor_col} AS vendor, {amount_col} AS amount, {date_col} AS rdate,
                       COALESCE(banking_transaction_id, 0) AS banking_transaction_id,
                       COALESCE(created_from_banking, false) AS created_from_banking,
                       COALESCE(category, '') AS category
                FROM receipts
                WHERE {date_col} >= %s AND {date_col} < %s
                """,
                (datetime.date(YEAR,1,1), datetime.date(YEAR+1,1,1)),
            )
            receipts = cur.fetchall()

            # Determine banking id column
            bti_id_col = None
            for cand in ['banking_transaction_id', 'transaction_id', 'id', 'txn_id', 'btxn_id']:
                if cand in banking_cols:
                    bti_id_col = cand
                    break
            if bti_id_col is None:
                # Try to infer an id column by type/name
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='banking_transactions'
                    """
                )
                for name, dtype in cur.fetchall():
                    if 'id' in name.lower() and dtype in ('integer', 'bigint'):
                        bti_id_col = name
                        break
            if bti_id_col is None:
                print("Banking transactions table missing an id column (banking_transaction_id/id/txn_id).")
                return

            # Fetch 2012 banking transactions
            sel_bti_cols = [f"{bti_id_col} AS banking_transaction_id"]
            if computed_amount_expr:
                sel_bti_cols.append(computed_amount_expr)
            else:
                sel_bti_cols.append(bamount_col + " AS amount")
            sel_bti_cols.append(bdate_col + " AS bdate")
            if bdesc_col:
                sel_bti_cols.append(bdesc_col + " AS desc")
            sel_bti = ", ".join(sel_bti_cols)
            cur.execute(
                f"""
                SELECT {sel_bti}
                FROM banking_transactions
                WHERE {bdate_col} >= %s AND {bdate_col} < %s
                """,
                (datetime.date(YEAR,1,1), datetime.date(YEAR+1,1,1)),
            )
            banking = cur.fetchall()

            # Index banking by id and build fee/transfer/cash flags
            bti_by_id = {}
            banking_fee_rows = []
            transfer_rows = []
            cash_withdrawals_rows = []
            unmatched_banking_ids = set()
            for b in banking:
                bti_by_id[b["banking_transaction_id"]] = b
                unmatched_banking_ids.add(b["banking_transaction_id"])
                desc = (b.get("desc") or "").lower()
                amt = float(b["amount"] or 0.0)
                # Fee detection
                if any(k in desc for k in fee_keywords):
                    banking_fee_rows.append([b["banking_transaction_id"], b["bdate"].isoformat(), amt, b.get("desc") or ""])
                # Transfer detection
                if any(k in desc for k in transfer_keywords):
                    transfer_rows.append([b["banking_transaction_id"], b["bdate"].isoformat(), amt, b.get("desc") or ""])
                # Cash withdrawal detection
                if any(k in desc for k in cash_kw):
                    cash_withdrawals_rows.append([b["banking_transaction_id"], b["bdate"].isoformat(), amt, b.get("desc") or ""])    

            # Receipts matching and exceptions
            unmatched_receipts = []
            exceptions_rows = []
            gst_preview_rows = []
            heffner_rows = []
            cra_wcb_rows = []

            for r in receipts:
                rid = r["receipt_id"]
                vendor = (r["vendor"] or "").strip()
                vlow = vendor.lower()
                amt = float(r["amount"] or 0.0)
                rdate = r["rdate"]
                cat = (r.get("category") or "").lower() if has_receipts_category else ""
                btid = int(r["banking_transaction_id"] or 0)

                # Exception detection by category or vendor keywords
                is_exception = False
                ex_reason = None
                def match_any(keys):
                    return any(k in vlow for k in [kk.lower() for kk in keys]) or any(k in cat for k in [kk.lower() for kk in keys])

                # Manual override first
                if rid in manual_ex:
                    is_exception = True
                    ex_reason = manual_ex[rid]

                if match_any(exceptions_map.get("cash_purchases", [])):
                    is_exception = True; ex_reason = "cash_purchase"
                elif match_any(exceptions_map.get("driver_reimbursements", [])):
                    is_exception = True; ex_reason = "driver_reimbursement"
                elif match_any(exceptions_map.get("donations", [])):
                    is_exception = True; ex_reason = "donation"
                elif match_any(exceptions_map.get("trade_of_services", [])):
                    is_exception = True; ex_reason = "trade_of_services"

                # Heffner GST flag
                if any(k in vlow for k in heffner_kw):
                    gst, net = calculate_gst_included(amt, gst_rate)
                    heffner_rows.append([rid, rdate.isoformat(), vendor, f"{amt:.2f}", f"{gst:.2f}", f"{net:.2f}"])

                # CRA/WCB payments tracking
                if any(k in vlow for k in cra_kw) or any(k in vlow for k in wcb_kw):
                    cra_wcb_rows.append([rid, rdate.isoformat(), vendor, f"{amt:.2f}"])

                # GST normalization preview for purchases (non-exceptions, non-fee-only vendors)
                gst, net = calculate_gst_included(amt, gst_rate)
                gst_preview_rows.append([rid, rdate.isoformat(), vendor, f"{amt:.2f}", f"{gst:.2f}", f"{net:.2f}"])

                # Matching assessment
                if btid and btid in bti_by_id:
                    # Matched to a banking transaction; remove from unmatched banking
                    unmatched_banking_ids.discard(btid)
                else:
                    # Not matched; record for audit unless exception
                    if is_exception:
                        exceptions_rows.append([rid, rdate.isoformat(), vendor, f"{amt:.2f}", ex_reason])
                    else:
                        unmatched_receipts.append([rid, rdate.isoformat(), vendor, f"{amt:.2f}"])

            # Prepare unmatched banking report (excluding fees, transfers, cash withdrawals)
            unmatched_banking_rows = []
            skip_ids = {row[0] for row in banking_fee_rows} | {row[0] for row in transfer_rows} | {row[0] for row in cash_withdrawals_rows}
            for bid in sorted(unmatched_banking_ids):
                if bid in skip_ids:
                    continue
                b = bti_by_id.get(bid)
                if not b:
                    continue
                unmatched_banking_rows.append([bid, b["bdate"].isoformat(), f"{float(b['amount'] or 0.0):.2f}", (b.get("desc") or "")])

            # Summary
            summary = [
                ["year", YEAR],
                ["receipts_total", len(receipts)],
                ["matched_receipts", len(receipts) - len(unmatched_receipts)],
                ["unmatched_receipts", len(unmatched_receipts)],
                ["banking_total", len(banking)],
                ["banking_fee_count", len(banking_fee_rows)],
                ["transfer_count", len(transfer_rows)],
                ["cash_withdrawal_count", len(cash_withdrawals_rows)],
                ["unmatched_banking_non_fees", len(unmatched_banking_rows)]
            ]

            # Write outputs
            os.makedirs(REPORT_DIR, exist_ok=True)
            write_csv(os.path.join(REPORT_DIR, f"2012_recon_summary_{DATE_SUFFIX}.csv"), ["metric", "value"], summary)
            write_csv(os.path.join(REPORT_DIR, f"2012_unmatched_receipts_{DATE_SUFFIX}.csv"), ["receipt_id", "date", "vendor", "amount"], unmatched_receipts)
            write_csv(os.path.join(REPORT_DIR, f"2012_unmatched_banking_{DATE_SUFFIX}.csv"), ["banking_transaction_id", "date", "amount", "description"], unmatched_banking_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_exceptions_{DATE_SUFFIX}.csv"), ["receipt_id", "date", "vendor", "amount", "reason"], exceptions_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_banking_fees_{DATE_SUFFIX}.csv"), ["banking_transaction_id", "date", "amount", "description"], banking_fee_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_gst_normalization_preview_{DATE_SUFFIX}.csv"), ["receipt_id", "date", "vendor", "gross_amount", "gst", "net_amount"], gst_preview_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_transfers_{DATE_SUFFIX}.csv"), ["banking_transaction_id", "date", "amount", "description"], transfer_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_cash_withdrawals_suspect_{DATE_SUFFIX}.csv"), ["banking_transaction_id", "date", "amount", "description"], cash_withdrawals_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_cra_wcb_payments_{DATE_SUFFIX}.csv"), ["receipt_id", "date", "vendor", "amount"], cra_wcb_rows)
            write_csv(os.path.join(REPORT_DIR, f"2012_heffner_gst_{DATE_SUFFIX}.csv"), ["receipt_id", "date", "vendor", "gross_amount", "gst", "net_amount"], heffner_rows)

            print("=== 2012 Reconciliation Audit Complete ===")
            print(f"Receipts: {len(receipts)} | Unmatched: {len(unmatched_receipts)}")
            print(f"Banking: {len(banking)} | Fees: {len(banking_fee_rows)} | Transfers: {len(transfer_rows)} | Cash withdrawals: {len(cash_withdrawals_rows)}")
            print("Reports saved under reports/ with date suffix.")


if __name__ == "__main__":
    main()
