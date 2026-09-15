"""Safe post-processing for newly imported bank statement transactions."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

NSF_RE = re.compile(r"(?:^|[^A-Z])NSF(?:[^A-Z]|$)", re.IGNORECASE)
FEE_TERMS = (
    "SERVICE CHARGE",
    "OVERDRAFT INTEREST",
    "OVERDRAFT S/C",
    "E-TRANSFER NETWORK FEE",
    "TRANSACTION FEE",
    "ACCOUNT FEE",
    "NSF FEE",
)
GENERIC_VENDORS = {
    "",
    "BANK DEPOSIT",
    "CASH WITHDRAWAL",
    "INTERNAL TRANSFER",
    "SQUARE",
}


@dataclass(frozen=True)
class PostProcessSummary:
    classified: int = 0
    nsf_transactions: int = 0
    fee_transactions: int = 0
    linked_receipts: int = 0
    created_fee_receipts: int = 0
    created_vendor_receipts: int = 0
    review_transactions: int = 0
    balances_updated: int = 0


def _clean_vendor(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" ,-.")
    value = re.sub(r"\s+\d{4}\*+\d{3,4}$", "", value).strip(" ,-.")
    return value[:100].upper()


def classify_description(description: str) -> tuple[str, str, bool, bool]:
    """Return ``(vendor, category, is_nsf, is_internal_transfer)``."""
    text = re.sub(r"\s+", " ", description or "").strip()
    upper = text.upper()
    is_nsf = bool(NSF_RE.search(upper))
    is_fee = any(term in upper for term in FEE_TERMS)
    is_transfer = "INTERNET TRANSFER" in upper and "E-TRANSFER" not in upper

    if is_fee:
        return "CIBC", "Bank Fees", is_nsf, False
    if is_nsf:
        vendor = re.sub(r".*?\bNSF\b(?:\s+RETURN|\s+REVERSAL)?", "", text,
                        flags=re.IGNORECASE)
        return _clean_vendor(vendor) or "NSF RETURN", "NSF Return", True, False
    if is_transfer:
        return "INTERNAL TRANSFER", "Internal Transfer", False, True
    if "SQUARE, INC" in upper:
        return "SQUARE", "Square Deposit", False, False

    patterns = (
        r"^Electronic Funds Transfer PREAUTHORIZED DEBIT\s+",
        r"^Electronic Funds Transfer MISC PAYMENT\s+",
        r"^Internet Banking INTERNET BILL PMT\d+\s+",
        r"^Internet Banking E-TRANSFER\s*\d+\s+",
        r"^Point of Sale - Interac (?:RETAIL )?PURCHASE\s+\d+\s+",
    )
    vendor = text
    for pattern in patterns:
        candidate = re.sub(pattern, "", text, flags=re.IGNORECASE)
        if candidate != text:
            vendor = candidate
            break
    if "ATM WITHDRAWAL" in upper or "ABM WITHDRAWAL" in upper:
        vendor = "CASH WITHDRAWAL"
    elif "ABM DEPOSIT" in upper or "ATM DEPOSIT" in upper:
        vendor = "BANK DEPOSIT"

    category = "Deposit" if "DEPOSIT" in upper else "Needs Review"
    return _clean_vendor(vendor), category, False, False


def _classify_imported(conn, import_batch: str) -> tuple[int, int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_id, description
              FROM banking_transactions
             WHERE import_batch = %s
             ORDER BY transaction_id
            """,
            (import_batch,),
        )
        rows = cur.fetchall()
        nsf_count = fee_count = 0
        payload = []
        for transaction_id, description in rows:
            vendor, category, is_nsf, is_transfer = classify_description(description)
            nsf_count += int(is_nsf)
            fee_count += int(category == "Bank Fees")
            payload.append(
                (vendor or None, category, is_nsf, is_transfer, transaction_id)
            )
        cur.executemany(
            """
            UPDATE banking_transactions
               SET vendor_extracted = %s,
                   category = %s,
                   is_nsf_charge = %s,
                   is_transfer = %s,
                   reconciliation_status = COALESCE(
                       reconciliation_status, 'unreconciled'
                   ),
                   verified = COALESCE(verified, FALSE),
                   updated_at = now()
             WHERE transaction_id = %s
            """,
            payload,
        )
    return len(rows), nsf_count, fee_count


def _vendor_identity(value: str | None) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", (value or "").upper()).strip()
    words = [
        word for word in text.split()
        if word not in {"LTD", "LIMITED", "INC", "CORP", "CORPORATION"}
    ]
    return " ".join(words)


def _vendor_identity_matches(bank_vendor: str, receipt_vendor: str) -> bool:
    bank_name = _vendor_identity(bank_vendor)
    receipt_name = _vendor_identity(receipt_vendor)
    if bank_name in GENERIC_VENDORS or receipt_name in GENERIC_VENDORS:
        return False
    if len(bank_name) < 4 or len(receipt_name) < 4:
        return False
    return bank_name == receipt_name or bank_name in receipt_name or receipt_name in bank_name


def _link_unique_receipts(conn, import_batch: str) -> int:
    """Link one-to-one amount/date matches only when vendor identity agrees."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bt.transaction_id, bt.vendor_extracted,
                   r.receipt_id,
                   COALESCE(r.canonical_vendor, r.vendor_name)
              FROM banking_transactions bt
              JOIN receipts r
                ON ROUND(r.gross_amount::numeric, 2) =
                   ROUND(bt.debit_amount::numeric, 2)
               AND r.receipt_date BETWEEN bt.transaction_date - 7
                                      AND bt.transaction_date + 7
             WHERE bt.import_batch = %s
               AND bt.debit_amount IS NOT NULL
               AND bt.debit_amount > 0
               AND bt.receipt_id IS NULL
               AND bt.reconciled_receipt_id IS NULL
               AND r.banking_transaction_id IS NULL
               AND COALESCE(r.is_voided, FALSE) = FALSE
               AND COALESCE(r.is_nsf, FALSE) = FALSE
               AND COALESCE(r.exclude_from_reports, FALSE) = FALSE
            """,
            (import_batch,),
        )
        candidates = [
            (transaction_id, receipt_id)
            for transaction_id, bank_vendor, receipt_id, receipt_vendor
            in cur.fetchall()
            if _vendor_identity_matches(bank_vendor, receipt_vendor)
        ]
        by_bank = defaultdict(list)
        by_receipt = defaultdict(list)
        for transaction_id, receipt_id in candidates:
            by_bank[transaction_id].append(receipt_id)
            by_receipt[receipt_id].append(transaction_id)
        pairs = [
            (transaction_id, receipt_ids[0])
            for transaction_id, receipt_ids in by_bank.items()
            if len(receipt_ids) == 1 and len(by_receipt[receipt_ids[0]]) == 1
        ]
        for transaction_id, receipt_id in pairs:
            cur.execute(
                """
                UPDATE banking_transactions
                   SET receipt_id = %s,
                       reconciled_receipt_id = %s,
                       reconciliation_status = 'reconciled',
                       reconciliation_notes =
                           'Auto-linked: exact amount/date and matching vendor',
                       reconciled_at = now(),
                       reconciled_by = 'bank_statement_import',
                       updated_at = now()
                 WHERE transaction_id = %s
                """,
                (receipt_id, receipt_id, transaction_id),
            )
            cur.execute(
                """
                UPDATE receipts
                   SET banking_transaction_id = %s,
                       is_matched = TRUE,
                       is_verified_banking = TRUE,
                       updated_at = now()
                 WHERE receipt_id = %s
                   AND banking_transaction_id IS NULL
                """,
                (transaction_id, receipt_id),
            )
    return len(pairs)


def _create_fee_receipts(conn, import_batch: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, debit_amount
              FROM banking_transactions
             WHERE import_batch = %s
               AND category = 'Bank Fees'
               AND debit_amount > 0
               AND receipt_id IS NULL
               AND reconciled_receipt_id IS NULL
             ORDER BY transaction_id
            """,
            (import_batch,),
        )
        rows = cur.fetchall()
        created = 0
        for transaction_id, txn_date, description, amount in rows:
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor, description,
                    currency, gross_amount, gst_amount, net_amount, revenue,
                    gl_account_code, gl_code, payment_method,
                    banking_transaction_id, created_from_banking,
                    auto_categorized, business_personal, source_system,
                    source_reference, receipt_review_status,
                    receipt_review_notes, validation_status,
                    is_verified_banking, is_matched, gst_exempt
                )
                VALUES (
                    %s, 'CIBC', 'CIBC', %s,
                    'CAD', %s, 0, %s, 0,
                    '5710', '5710', 'bank_debit',
                    %s, TRUE, TRUE, 'Business', 'BANK_STATEMENT_IMPORT',
                    %s, 'auto_classified',
                    'Automatically created from a CIBC bank fee; verify during review.',
                    'PENDING', TRUE, TRUE, TRUE
                )
                RETURNING receipt_id
                """,
                (txn_date, description, amount, amount, transaction_id,
                 import_batch),
            )
            receipt_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE banking_transactions
                   SET receipt_id = %s,
                       reconciled_receipt_id = %s,
                       reconciliation_status = 'reconciled',
                       reconciliation_notes =
                           'Auto-created CIBC bank fee receipt (GL 5710)',
                       reconciled_at = now(),
                       reconciled_by = 'bank_statement_import',
                       updated_at = now()
                 WHERE transaction_id = %s
                """,
                (receipt_id, receipt_id, transaction_id),
            )
            created += 1
    return created


def _historical_vendor_gl_map(conn) -> dict[str, tuple[str, str]]:
    """Return vendors with at least 3 linked receipts and >=80% one-GL use."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT UPPER(TRIM(bt.vendor_extracted)),
                   r.gl_account_code,
                   UPPER(TRIM(COALESCE(r.canonical_vendor, r.vendor_name))),
                   COUNT(*)
              FROM banking_transactions bt
              JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
             WHERE NULLIF(TRIM(bt.vendor_extracted), '') IS NOT NULL
               AND NULLIF(TRIM(r.gl_account_code), '') IS NOT NULL
               AND COALESCE(r.exclude_from_reports, FALSE) = FALSE
               AND COALESCE(r.is_voided, FALSE) = FALSE
               AND COALESCE(r.is_nsf, FALSE) = FALSE
             GROUP BY 1, 2, 3
            """
        )
        grouped = defaultdict(list)
        for vendor, gl_code, receipt_vendor, count in cur.fetchall():
            grouped[vendor].append((count, gl_code, receipt_vendor))
    result = {}
    for vendor, choices in grouped.items():
        total = sum(item[0] for item in choices)
        top_count, top_gl, top_vendor = max(choices)
        if total >= 3 and top_count / total >= 0.80:
            result[vendor] = (top_gl, top_vendor)
    return result


def _create_high_confidence_vendor_receipts(conn, import_batch: str) -> int:
    vendor_map = _historical_vendor_gl_map(conn)
    if not vendor_map:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, debit_amount,
                   UPPER(TRIM(vendor_extracted))
              FROM banking_transactions
             WHERE import_batch = %s
               AND debit_amount > 0
               AND receipt_id IS NULL
               AND reconciled_receipt_id IS NULL
               AND COALESCE(is_nsf_charge, FALSE) = FALSE
               AND COALESCE(is_transfer, FALSE) = FALSE
               AND category <> 'Bank Fees'
             ORDER BY transaction_id
            """,
            (import_batch,),
        )
        rows = cur.fetchall()
        created = 0
        for transaction_id, txn_date, description, amount, vendor in rows:
            if vendor in GENERIC_VENDORS or vendor not in vendor_map:
                continue
            gl_code, canonical_vendor = vendor_map[vendor]
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor, description,
                    currency, gross_amount, gst_amount, net_amount, revenue,
                    gl_account_code, gl_code, payment_method,
                    banking_transaction_id, created_from_banking,
                    auto_categorized, business_personal, source_system,
                    source_reference, receipt_review_status,
                    receipt_review_notes, validation_status,
                    is_verified_banking, is_matched
                )
                VALUES (
                    %s, %s, %s, %s,
                    'CAD', %s, 0, %s, 0,
                    %s, %s, 'bank_debit',
                    %s, TRUE, TRUE, 'Business', 'BANK_STATEMENT_IMPORT',
                    %s, 'needs_review',
                    'Created from a historically consistent vendor/GL mapping; verify GST and source document.',
                    'PENDING', TRUE, TRUE
                )
                RETURNING receipt_id
                """,
                (txn_date, canonical_vendor, canonical_vendor, description,
                 amount, amount, gl_code, gl_code, transaction_id, import_batch),
            )
            receipt_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE banking_transactions
                   SET receipt_id = %s,
                       reconciled_receipt_id = %s,
                       reconciliation_status = 'reconciled',
                       reconciliation_notes =
                           'Auto-created receipt from >=80%% historical vendor/GL mapping',
                       reconciled_at = now(),
                       reconciled_by = 'bank_statement_import',
                       updated_at = now()
                 WHERE transaction_id = %s
                """,
                (receipt_id, receipt_id, transaction_id),
            )
            created += 1
    return created


def _recalculate_running_balance(
    conn, account_number: str, import_batch: str
) -> int:
    """Store running totals on new rows without rewriting prior history."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH running AS (
                SELECT transaction_id,
                       SUM(COALESCE(credit_amount, 0) -
                           COALESCE(debit_amount, 0)) OVER (
                           ORDER BY transaction_date, transaction_id
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                       ) AS running_balance
                  FROM banking_transactions
                 WHERE account_number = %s
                   AND import_batch = %s
            )
            UPDATE banking_transactions bt
               SET balance = running.running_balance,
                   updated_at = now()
              FROM running
             WHERE bt.transaction_id = running.transaction_id
            """,
            (account_number, import_batch),
        )
        return cur.rowcount


def post_process_import(conn, account_number: str, import_batch: str,
                        commit: bool = True) -> PostProcessSummary:
    """Classify, link, create safe receipts, balance, and queue review."""
    classified, nsf_count, fee_count = _classify_imported(conn, import_batch)
    linked = _link_unique_receipts(conn, import_batch)
    fee_receipts = _create_fee_receipts(conn, import_batch)
    vendor_receipts = _create_high_confidence_vendor_receipts(conn, import_batch)
    balances = _recalculate_running_balance(conn, account_number, import_batch)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE banking_transactions
               SET reconciliation_notes = COALESCE(
                      reconciliation_notes,
                      'Imported statement transaction requires manual verification'
                  ),
                  reconciliation_status = COALESCE(
                      reconciliation_status, 'unreconciled'
                  )
            WHERE import_batch = %s
              AND reconciliation_status <> 'reconciled'
            """,
            (import_batch,),
        )
        review_count = cur.rowcount
    if commit:
        conn.commit()
    return PostProcessSummary(
        classified=classified,
        nsf_transactions=nsf_count,
        fee_transactions=fee_count,
        linked_receipts=linked,
        created_fee_receipts=fee_receipts,
        created_vendor_receipts=vendor_receipts,
        review_transactions=review_count,
        balances_updated=balances,
    )


__all__ = [
    "PostProcessSummary",
    "classify_description",
    "post_process_import",
]
