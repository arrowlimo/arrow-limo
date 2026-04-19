import re
import sys
from datetime import date

import psycopg2
from psycopg2.extras import RealDictCursor

APPLY = "--apply" in sys.argv

RULES = [
    ("5260", "Driver Salaries", [
        "ANGEL ESCOBAR", "DALE MENARD", "PAUL MANSELL", "JEANNIE SHILLINGTON",
        "DOUG REDMOND", "JESSE GORDON", "ZAC KELLER", "KEVIN BOULLEY",
        "DUSTAN TOWNSEND", "LOGAN MOSINSKY", "LOGAN MASINSKY",
        "CHANTEL THOMAS", "CHANTAL THOMAS", "JACK CARTER",
        "MIKE WOODROW", "MICHAEL RICHARD", "MIKE RICHARD",
        "VIC PFIEFER", "KEVIN KOSIK", "MARK LINTON", "BARRY FORSBERG",
        "BARNEY FORSBERG", "LARRY TAYLOR",
    ]),
    ("5120", "Vehicle Maintenance & Repairs", [
        "PARRS AUTOMOTIVE", "PARRS AUTO", "EARLS AUTO", "KIRKS TIRE", "FIBRENEW", "D&M ALIGN",
    ]),
    ("2210", "Vehicle Loans", [
        "HEFFNER AUTO FINANCE", "HEFFNER LEXUS", "HEFFNER CIRCLE", "HEFFNER AUTO", "HEFFNER LEASING",
    ]),
    ("5300", "Payroll Tax Remittances", ["REVENUE CANADA", "CRA", "MINISTER OF FINANCE"]),
    ("5430", "Telephone & Internet", ["TELUS", "SHAW"]),
    ("5100", "Advertising & Marketing", ["ACTION PAGES", "WELCOME WAGON", "BIG 105", "WORD OF LIFE"]),
    ("5500", "Insurance", ["IFS", "COOP INSURANCE", "MAYFAIR FINANCIAL INSURANCE", "MAYFAIR"]),
    ("5450", "Licenses & Registration", ["RED DEER REGISTRIES", "AGLC"]),
    ("5730", "Interest Expense", ["IFS PREMIUM"]),
    ("2500", "Loan Payments", ["KAREN RICHARD"]),
    ("1099", "Inter-Account Clearing", ["ARROW LIMOUSINE", "ARROW LIMO"]),
    ("5210", "Owner / Officer Salaries", ["PAUL RICHARD"]),
]


def infer_gl(payee: str | None, memo: str | None):
    search = f"{payee or ''} {memo or ''}".upper()
    for gl_code, gl_desc, keywords in RULES:
        if any(keyword in search for keyword in keywords):
            return gl_code, gl_desc
    return "2910", "Cheque Register Review"


def infer_date(effective_date, account_number, cheque_number):
    if effective_date is not None:
        return effective_date

    digits = re.sub(r"\D", "", str(cheque_number or ""))
    num = int(digits) if digits else 0
    acct = (account_number or "").strip()

    if acct == "903990106011":
        return date(2014, 1, 1) if num >= 300 else date(2013, 1, 1)

    return date(2012, 1, 1)


SQL = """
WITH active_checks AS (
    SELECT id, cheque_number, cheque_date, cleared_date, payee, amount, status,
           banking_transaction_id, memo, account_number
    FROM cheque_register
    WHERE amount > 0
      AND COALESCE(status, '') <> 'VOID'
),
base AS (
    SELECT ac.*,
           EXISTS (
               SELECT 1
               FROM receipts r
               WHERE COALESCE(r.is_voided, false) = false
                 AND ac.banking_transaction_id IS NOT NULL
                 AND r.banking_transaction_id = ac.banking_transaction_id
           ) AS bank_match,
           EXISTS (
               SELECT 1
               FROM receipts r
               WHERE COALESCE(r.is_voided, false) = false
                 AND (
                     (COALESCE(r.description, '') || ' ' || COALESCE(r.source_reference, '') || ' ' || COALESCE(r.comment, ''))
                     ~* ('(^|[^0-9])((CHQ)|(CHEQUE))\\s*#?\\s*' || ac.cheque_number || '([^0-9]|$)')
                 )
           ) AS chq_text_match,
           EXISTS (
               SELECT 1
               FROM receipts r
               WHERE COALESCE(r.is_voided, false) = false
                 AND ac.cheque_date IS NOT NULL
                 AND ABS(COALESCE(r.gross_amount, 0) - ac.amount) < 0.005
                 AND r.receipt_date = ac.cheque_date
           ) AS exact_date_amount_match
    FROM active_checks ac
),
unresolved AS (
    SELECT *
    FROM base
    WHERE NOT (bank_match OR chq_text_match OR exact_date_amount_match)
),
probable AS (
    SELECT DISTINCT u.id
    FROM unresolved u
    JOIN receipts r
      ON COALESCE(r.is_voided, false) = false
     AND ABS(COALESCE(r.gross_amount, 0) - u.amount) < 0.005
     AND (u.cheque_date IS NULL OR r.receipt_date BETWEEN u.cheque_date - INTERVAL '30 days' AND u.cheque_date + INTERVAL '30 days')
     AND NULLIF(TRIM(COALESCE(u.payee, '')), '') IS NOT NULL
     AND UPPER(COALESCE(r.vendor_name, '') || ' ' || COALESCE(r.description, '')) LIKE '%' || UPPER(SPLIT_PART(TRIM(u.payee), ' ', 1)) || '%'
)
SELECT u.id,
       u.cheque_number,
       COALESCE(u.cheque_date, u.cleared_date) AS effective_date,
       u.payee,
       u.amount,
       u.status,
       u.banking_transaction_id,
       u.memo,
       u.account_number
FROM unresolved u
LEFT JOIN probable p
  ON p.id = u.id
WHERE p.id IS NULL
ORDER BY COALESCE(u.cheque_date, u.cleared_date) NULLS FIRST, u.cheque_number;
"""


conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
conn.autocommit = False
cur = conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute(SQL)
    rows = cur.fetchall()
    print(f"Rows requiring backfill: {len(rows)}")

    inserted = 0
    skipped = 0

    for row in rows:
        source_reference = f"CHQ{row['cheque_number']}-REG{row['id']}"
        cur.execute(
            """
            SELECT receipt_id
            FROM receipts
            WHERE source_reference = %s
            LIMIT 1
            """,
            (source_reference,),
        )
        existing = cur.fetchone()
        if existing:
            skipped += 1
            print(f"SKIP existing receipt {existing['receipt_id']} for {source_reference}")
            continue

        payee = (row["payee"] or "").strip() or f"UNKNOWN CHQ {row['cheque_number']}"
        memo = (row["memo"] or "").strip()
        effective_date = infer_date(row["effective_date"], row["account_number"], row["cheque_number"])
        gl_code, gl_desc = infer_gl(payee, memo)
        description = memo or f"Cheque register backfill for CHQ {row['cheque_number']}"
        if "CHQ" not in description.upper():
            description = f"CHQ {row['cheque_number']} - {description}"
        if (row.get("status") or "").upper() == "NSF":
            description += " [NSF status]"

        print(
            f"{'APPLY' if APPLY else 'DRY'} {source_reference} | {effective_date} | {payee} | ${float(row['amount']):,.2f} | GL {gl_code}"
        )

        if not APPLY:
            continue

        cur.execute(
            """
            INSERT INTO receipts (
                source_system,
                source_reference,
                receipt_date,
                vendor_name,
                canonical_vendor,
                description,
                currency,
                gross_amount,
                payment_method,
                pay_method,
                fiscal_year,
                gl_code,
                gl_description,
                category,
                banking_transaction_id,
                created_from_banking,
                receipt_source,
                verified_source,
                exclude_from_reports,
                created_at,
                updated_at
            ) VALUES (
                'manual',
                %s,
                %s,
                %s,
                %s,
                %s,
                'CAD',
                %s,
                'cheque',
                'CHQ',
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'cheque_register_gapfill_20260413',
                'cheque_register',
                true,
                NOW(),
                NOW()
            )
            RETURNING receipt_id
            """,
            (
                source_reference,
                effective_date,
                payee,
                payee,
                description,
                row["amount"],
                effective_date.year,
                gl_code,
                gl_desc,
                gl_desc,
                row["banking_transaction_id"],
                bool(row["banking_transaction_id"]),
            ),
        )
        receipt_row = cur.fetchone()
        receipt_id = receipt_row["receipt_id"]
        inserted += 1

        if row["banking_transaction_id"]:
            cur.execute(
                """
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
                  AND receipt_id IS NULL
                """,
                (receipt_id, row["banking_transaction_id"]),
            )

    if APPLY:
        conn.commit()
    else:
        conn.rollback()

    print(f"Inserted: {inserted}")
    print(f"Skipped existing: {skipped}")
    print("Mode:", "APPLY" if APPLY else "DRY RUN")

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
