"""
Materialize 2013 banking transactions from unified_general_ledger.

Purpose
- Fill the 2013 banking gap by deriving bank-side entries from the imported QuickBooks General Ledger.
- Targets only bank accounts present in GL for 2013 (e.g., Scotia main, CIBC 1615).

Safety and idempotency
- Dry-run by default; use --write to insert.
- Deterministic transaction_hash to avoid duplicates; skips rows whose hash already exists in banking_transactions.
- Does not delete or update existing data.

Mapping
- GL account_code → banking_transactions.account_number (best-effort numeric extraction; otherwise a short token)
- GL transaction_date → transaction_date
- GL credit_amount → debit_amount (money leaving the bank)
- GL debit_amount → credit_amount (money entering the bank)
- GL description → description
- GL entity_name → vendor_extracted (if available)
- source_file/import_batch indicate GL derivation for traceability

Notes
- Rows with both debit_amount and credit_amount equal to 0 are skipped.
- Balance and posted_date left NULL; can be backfilled later if needed.
"""
import argparse
import os
import re
import sys
import hashlib
from datetime import datetime

import psycopg2


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REMOVED***"),
    )


BANK_ACCOUNT_CANDIDATES = [
    # 2013-era bank accounts observed in GL
    "1010 Scotia Bank Main",
    "1000 CIBC Bank 1615",
    # include others for completeness (won't match 2013 but harmless)
    "0228362 CIBC checking account",
    "3648117 CIBC Business Deposit account",
]


def extract_account_number(account_code: str) -> str:
    """Best-effort extraction of an account_number token for banking_transactions.
    Preference order:
    - 6–8 digit number in the text (e.g., 0228362, 3648117)
    - 4-digit number at end (e.g., 1615)
    - Otherwise the first 4 digits from the GL account code prefix (e.g., 1010)
    - Fallback to a compacted alphanumeric token of the account_code
    """
    if not account_code:
        return "UNKNOWN"
    # 6-8 digit sequences often represent actual bank numbers
    m = re.search(r"(\d{6,8})", account_code)
    if m:
        return m.group(1)
    # 4-digit number at end (like 1615)
    m = re.search(r"(\d{4})\s*$", account_code)
    if m:
        return m.group(1)
    # Leading 4-digit GL code
    m = re.match(r"^(\d{4})", account_code)
    if m:
        return m.group(1)
    # Fallback: strip non-alnum and truncate
    token = re.sub(r"[^A-Za-z0-9]+", "", account_code)
    return token[:16] if token else "UNKNOWN"


def load_existing_hashes(cur):
    cur.execute("SELECT transaction_hash FROM banking_transactions WHERE transaction_date BETWEEN %s AND %s", ("2013-01-01", "2013-12-31"))
    return {row[0] for row in cur.fetchall() if row[0]}


def ensure_account_registered(cur, account_number: str, account_name_hint: str = None, account_type: str = "legacy"):
    """Ensure the given account_number exists in cibc_accounts to satisfy FK.
    If missing, insert a minimal, inactive registry row using best-effort metadata.
    This table is used as a generic bank account registry despite its historical name.
    """
    # verify table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name='cibc_accounts'
        )
    """)
    if not cur.fetchone()[0]:
        # If the registry doesn't exist, we cannot satisfy FK anyway; just return
        return

    cur.execute("SELECT 1 FROM cibc_accounts WHERE account_number=%s", (account_number,))
    if cur.fetchone():
        return

    # derive last4: take last 4 numeric chars if available, else last 4 of the token
    import re as _re
    digits = ''.join(_re.findall(r"\d", account_number))
    last4 = (digits[-4:] if len(digits) >= 4 else account_number[-4:]).rjust(4, '0')

    # build a friendly name
    account_name = account_name_hint or f"Legacy Bank Account {account_number}"

    # Insert as inactive to avoid implying it's an actively ingested CIBC feed
    cur.execute(
        """
        INSERT INTO cibc_accounts (account_number, account_name, account_type, last4, is_active)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (account_number) DO NOTHING
        """,
        (account_number, account_name[:100], account_type, last4[:4], False),
    )


def main():
    parser = argparse.ArgumentParser(description="Materialize 2013 banking transactions from unified_general_ledger")
    parser.add_argument("--write", action="store_true", help="Apply inserts to database")
    parser.add_argument("--year", type=int, default=2013, help="Year to materialize (default 2013)")
    args = parser.parse_args()

    year = args.year
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    batch_id = f"gl-{year}-materialization-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Ensure source table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='unified_general_ledger'
            )
        """)
        if not cur.fetchone()[0]:
            print("[FAIL] unified_general_ledger not found. Aborting.")
            sys.exit(1)

        # Inspect banking_transactions columns to build dynamic insert
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='banking_transactions'
            ORDER BY ordinal_position
        """)
        bt_cols = [r[0] for r in cur.fetchall()]

        needed = {"account_number", "transaction_date", "description", "debit_amount", "credit_amount", "vendor_extracted", "category", "source_file", "import_batch", "transaction_hash"}
        missing = needed - set(bt_cols)
        if missing:
            print(f"[WARN] banking_transactions missing expected columns: {sorted(missing)}. Proceeding with available subset.")

        existing_hashes = load_existing_hashes(cur)

        # Query GL for candidate bank account rows
        cur.execute(
            """
            SELECT transaction_date, account_code, description, debit_amount, credit_amount, entity_name
            FROM unified_general_ledger
            WHERE transaction_date >= %s AND transaction_date < %s
              AND account_code = ANY(%s)
            ORDER BY transaction_date, account_code
            """,
            (start, end, BANK_ACCOUNT_CANDIDATES),
        )

        rows = cur.fetchall()
        prepared = []
        skipped_zero = 0
        skipped_dupe = 0

        for (txn_date, account_code, desc, debit, credit, entity_name) in rows:
            debit = float(debit or 0)
            credit = float(credit or 0)
            if (debit == 0.0 and credit == 0.0):
                skipped_zero += 1
                continue

            # Map to bank semantics: GL credit → bank debit (money out), GL debit → bank credit (money in)
            bank_debit = credit
            bank_credit = debit

            acct_num = extract_account_number(account_code or "")
            vendor = (entity_name or None)
            description = (desc or "").strip()

            # Deterministic hash for idempotency
            hash_str = f"{acct_num}|{txn_date}|{description}|{bank_debit:.2f}|{bank_credit:.2f}|GL:{account_code}"
            txn_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()
            if txn_hash in existing_hashes:
                skipped_dupe += 1
                continue

            record = {
                "account_number": acct_num,
                "transaction_date": txn_date,
                "description": description,
                "debit_amount": bank_debit if bank_debit else None,
                "credit_amount": bank_credit if bank_credit else None,
                "vendor_extracted": vendor,
                "category": "from_gl",
                "source_file": f"unified_general_ledger:{account_code}",
                "import_batch": batch_id,
                "transaction_hash": txn_hash,
            }
            prepared.append(record)

        print(f"Found {len(rows)} GL rows for {year} across {len(BANK_ACCOUNT_CANDIDATES)} bank accounts")
        print(f"Prepared {len(prepared)} banking rows | skipped zero-amount: {skipped_zero}, skipped existing-hash: {skipped_dupe}")

        if not prepared:
            print("Nothing to do.")
            return

        if not args.write:
            print("\n[OK] DRY RUN: No changes written. Use --write to insert.")
            return

        # Before inserting, ensure all account_numbers exist in the registry to satisfy FK
        # Map each account_number to a representative account_name hint from its source_file tail
        acct_hints = {}
        for rec in prepared:
            acct = rec.get("account_number")
            if acct and acct not in acct_hints:
                # Try to derive a readable name from the GL account code embedded in source_file
                src = rec.get("source_file") or ""
                hint = src.split(":", 1)[-1] if ":" in src else src
                acct_hints[acct] = hint

        for acct, hint in acct_hints.items():
            try:
                ensure_account_registered(cur, acct, account_name_hint=hint, account_type="legacy")
            except Exception:
                # Don't fail the whole run if registry insert fails; continue and let FK surface it
                pass
        try:
            # commit registry additions (if any)
            conn.commit()
        except Exception:
            conn.rollback()

        # Build INSERT dynamically using available columns
        insert_cols = [
            c for c in [
                "account_number",
                "transaction_date",
                "description",
                "debit_amount",
                "credit_amount",
                "vendor_extracted",
                "category",
                "source_file",
                "import_batch",
                "transaction_hash",
            ] if c in bt_cols
        ]
        placeholders = ",".join(["%s"] * len(insert_cols))
        sql = f"INSERT INTO banking_transactions ({', '.join(insert_cols)}) VALUES ({placeholders})"

        inserted = 0
        for rec in prepared:
            vals = [rec.get(c) for c in insert_cols]
            try:
                cur.execute(sql, vals)
                inserted += 1
            except Exception as e:
                # Reset failed transaction block and continue
                try:
                    conn.rollback()
                except Exception:
                    pass
                # tolerate duplicates in case a unique constraint was added later
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    continue
                print(f"[WARN] Insert error: {e}\n  record={rec}")
            else:
                # commit per successful row to avoid large txn aborts
                conn.commit()
        print(f"\n[OK] Inserted {inserted} new 2013 banking rows from GL into banking_transactions")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
