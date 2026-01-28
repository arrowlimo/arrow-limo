#!/usr/bin/env python3
"""
Compare QuickBooks CSV line-items to existing accounting tables in almsdata.

Process:
- Load CSVs from L:\\limo\\quickbooks (journal 2025.CSV, sept 2025 ledger old 2005 files.CSV)
- Normalize to line items with date, debit, credit, amount, memo, account, name, num
- Create a temporary table in Postgres and bulk-insert staged rows
- Auto-detect existing target tables and columns in almsdata
- Perform SQL joins to count matches and unmatched per table and per source file
- Write a summary CSV report qb_compare_results.csv at repo root

No data is permanently imported; only a temporary table is used and dropped at the end.
"""

import csv
import os
import sys
import psycopg2
from datetime import datetime

QB_DIR = r"L:\\limo\\quickbooks"
CIBC_DIR = r"L:\\limo\\CIBC UPLOADS"

def discover_csv_files():
    files = []
    # Include known QB files first for deterministic ordering
    for fname in ["journal 2025.CSV", "sept 2025 ledger old 2005 files.CSV"]:
        fp = os.path.join(QB_DIR, fname)
        if os.path.exists(fp):
            files.append(fp)
    # Recursively include all CSVs under CIBC uploads
    if os.path.isdir(CIBC_DIR):
        for root, _, fns in os.walk(CIBC_DIR):
            for fn in fns:
                if fn.lower().endswith('.csv'):
                    files.append(os.path.join(root, fn))
    return files

REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qb_compare_results.csv")
UNMATCHED_BY_YEAR_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "qb_unmatched_by_year.csv")


def connect_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
        port=int(os.environ.get("DB_PORT", "5432")),
    )


def parse_date(val: str):
    if not val:
        return None
    val = val.strip()
    # Try common formats
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(val, fmt).date()
        except Exception:
            pass
    return None


def to_float(val):
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", "")
    if s == "":
        return 0.0
    # Handle parentheses as negative
    neg = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "")
    try:
        f = float(s)
        return -f if neg else f
    except Exception:
        return 0.0


def load_csv_rows(file_path):
    rows = []
    fname = os.path.basename(file_path)
    if not os.path.exists(file_path):
        return rows

    # Use cp1252 per observed encoding in sample file
    with open(file_path, "r", encoding="cp1252", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        # Normalize header lookup
        def col(name):
            # Return first header equal ignoring case/whitespace
            for h in headers:
                if h.lower().strip() == name.lower().strip():
                    return h
            return None

        # Column mappings for the two CSV shapes
        trans_col = col("Trans #")
        type_col = col("Type")
        date_col = col("Date")
        num_col = col("Num")
        name_col = col("Name")
        memo_col = col("Memo") or col("Description")
        account_col = col("Account")
        debit_col = col("Debit")
        credit_col = col("Credit")
        amount_col = col("Amount")
        balance_col = col("Balance")

        for r in reader:
            tx_date = parse_date(r.get(date_col) if date_col else None)
            if not tx_date:
                # Skip rows without a date
                continue

            debit = to_float(r.get(debit_col)) if debit_col else 0.0
            credit = to_float(r.get(credit_col)) if credit_col else 0.0
            amt = to_float(r.get(amount_col)) if amount_col else (debit - credit)

            rows.append({
                "source_file": fname,
                "transaction_date": tx_date,
                "type": (r.get(type_col) or "").strip() if type_col else "",
                "num": (r.get(num_col) or r.get(trans_col) or "").strip(),
                "name": (r.get(name_col) or "").strip() if name_col else "",
                "memo": (r.get(memo_col) or "").strip() if memo_col else "",
                "account": (r.get(account_col) or "").strip() if account_col else "",
                "debit": debit,
                "credit": credit,
                "amount": amt,
                "balance": to_float(r.get(balance_col)) if balance_col else None,
            })

    return rows


def create_temp_table(cur):
    cur.execute(
        """
        DROP TABLE IF EXISTS tmp_qb_staging_compare;
        CREATE TEMP TABLE tmp_qb_staging_compare (
            id SERIAL PRIMARY KEY,
            source_file TEXT,
            transaction_date DATE,
            type TEXT,
            num TEXT,
            name TEXT,
            memo TEXT,
            account TEXT,
            debit NUMERIC(14,2),
            credit NUMERIC(14,2),
            amount NUMERIC(14,2),
            balance NUMERIC(14,2),
            -- normalized helper columns
            norm_amount NUMERIC(14,2),
            norm_memo TEXT,
            norm_account TEXT,
            norm_name TEXT
        );
        CREATE INDEX ON tmp_qb_staging_compare(transaction_date);
        CREATE INDEX ON tmp_qb_staging_compare(amount);
        CREATE INDEX ON tmp_qb_staging_compare(debit);
        CREATE INDEX ON tmp_qb_staging_compare(credit);
        CREATE INDEX ON tmp_qb_staging_compare(norm_amount);
        """
    )


def bulk_insert(cur, rows):
    if not rows:
        return 0
    args = [
        (
            r["source_file"], r["transaction_date"], r["type"], r["num"],
            r["name"], r["memo"], r["account"], r["debit"], r["credit"], r["amount"], r["balance"]
        ) for r in rows
    ]
    cur.executemany(
        """
        INSERT INTO tmp_qb_staging_compare (
            source_file, transaction_date, type, num, name, memo, account,
            debit, credit, amount, balance
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        args,
    )
    # Normalize amount (debit - credit when provided) and text fields for fuzzy matching
    cur.execute(
        """
        UPDATE tmp_qb_staging_compare
        SET debit = COALESCE(debit,0),
            credit = COALESCE(credit,0),
            amount = COALESCE(amount,0);

        UPDATE tmp_qb_staging_compare
        SET norm_amount = CASE 
                              WHEN (debit <> 0 OR credit <> 0) THEN debit - credit
                              ELSE amount
                          END,
            norm_memo = NULLIF(btrim(regexp_replace(lower(COALESCE(memo,'')), '[^a-z0-9]+', ' ', 'g')), ''),
            norm_account = NULLIF(btrim(regexp_replace(lower(COALESCE(account,'')), '[^a-z0-9]+', ' ', 'g')), ''),
            norm_name = NULLIF(btrim(regexp_replace(lower(COALESCE(name,'')), '[^a-z0-9]+', ' ', 'g')), '');
        """
    )
    return len(rows)


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table_name,)
    )
    return bool(cur.fetchone()[0])


def column_exists(cur, table_name, column_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s AND column_name=%s
        )
        """,
        (table_name, column_name)
    )
    return bool(cur.fetchone()[0])


def compare_against_targets(cur):
    results = []

    # Candidate target sets (line tables with optional header join for dates)
    targets = []

    # qb_transactions_staging (flat)
    if table_exists(cur, 'qb_transactions_staging'):
        targets.append({
            'name': 'qb_transactions_staging',
            'query_strict': """
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(t.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN qb_transactions_staging t
                  ON t.transaction_date = s.transaction_date
           AND COALESCE(t.amount, COALESCE(t.debit_amount,0) - COALESCE(t.credit_amount,0)) = s.norm_amount
                GROUP BY s.source_file
                ORDER BY s.source_file
            """,
            'query_fuzzy': """
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(t.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                                LEFT JOIN qb_transactions_staging t
                                    ON t.transaction_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
           AND ABS(COALESCE(t.amount, COALESCE(t.debit_amount,0) - COALESCE(t.credit_amount,0)) - s.norm_amount) <= 0.01
           AND (
               (s.norm_memo IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(t.memo,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_memo || '%')
            OR (s.norm_name IS NOT NULL AND (
                NULLIF(btrim(regexp_replace(lower(COALESCE(t.customer_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_name || '%'
                OR NULLIF(btrim(regexp_replace(lower(COALESCE(t.vendor_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_name || '%'
                OR NULLIF(btrim(regexp_replace(lower(COALESCE(t.employee_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_name || '%'
               ))
            OR (s.norm_account IS NOT NULL AND (
                NULLIF(btrim(regexp_replace(lower(COALESCE(t.account_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_account || '%'
                OR NULLIF(btrim(regexp_replace(lower(COALESCE(t.account_code,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_account || '%'
               ))
           )
                GROUP BY s.source_file
                ORDER BY s.source_file
            """
        })

    # general_ledger_lines joined to general_ledger_entries for date
    if table_exists(cur, 'general_ledger_lines') and table_exists(cur, 'general_ledger_entries') \
       and column_exists(cur, 'general_ledger_lines', 'header_id') \
       and column_exists(cur, 'general_ledger_entries', 'entry_date'):
                targets.append({
                        'name': 'general_ledger_lines',
                        'query_strict': """
                                SELECT s.source_file,
                                             COUNT(*) AS staged_rows,
                                             COUNT(gl.*) AS matched_rows
                                FROM tmp_qb_staging_compare s
                                LEFT JOIN general_ledger_lines gl
                                    ON COALESCE(gl.debit_amount,0) - COALESCE(gl.credit_amount,0) = s.norm_amount
                                LEFT JOIN general_ledger_entries ge ON ge.entry_id = gl.header_id
                                WHERE ge.entry_date = s.transaction_date
                                GROUP BY s.source_file
                                ORDER BY s.source_file
                        """,
                        'query_fuzzy': """
                                SELECT s.source_file,
                                             COUNT(*) AS staged_rows,
                                             COUNT(gl.*) AS matched_rows
                                FROM tmp_qb_staging_compare s
                                LEFT JOIN general_ledger_lines gl
                                    ON ABS(COALESCE(gl.debit_amount,0) - COALESCE(gl.credit_amount,0) - s.norm_amount) <= 0.01
                                LEFT JOIN general_ledger_entries ge ON ge.entry_id = gl.header_id
                                WHERE ge.entry_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
                                    AND (
                                                (s.norm_memo IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(gl.description,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_memo || '%')
                                         OR (s.norm_account IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(gl.account_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_account || '%')
                                    )
                                GROUP BY s.source_file
                                ORDER BY s.source_file
                        """
                })

    # journal_line_items joined to general_journal for date
    if table_exists(cur, 'journal_line_items') and table_exists(cur, 'general_journal') \
       and column_exists(cur, 'journal_line_items', 'journal_entry_id') \
       and (column_exists(cur, 'general_journal', 'entry_date') or column_exists(cur, 'general_journal', 'transaction_date')):
        date_col = 'entry_date' if column_exists(cur, 'general_journal', 'entry_date') else 'transaction_date'
        targets.append({
            'name': 'journal_line_items',
        'query_strict': f"""
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(jli.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN journal_line_items jli
            ON COALESCE(jli.debit_amount,0) - COALESCE(jli.credit_amount,0) = s.norm_amount
                LEFT JOIN general_journal gj ON gj.journal_entry_id = jli.journal_entry_id
                WHERE gj.{date_col} = s.transaction_date
                GROUP BY s.source_file
                ORDER BY s.source_file
            """,
        'query_fuzzy': f"""
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(jli.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN journal_line_items jli
            ON ABS(COALESCE(jli.debit_amount,0) - COALESCE(jli.credit_amount,0) - s.norm_amount) <= 0.01
                LEFT JOIN general_journal gj ON gj.journal_entry_id = jli.journal_entry_id
                WHERE gj.{date_col} BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
                  AND (
                (s.norm_memo IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(jli.line_description,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_memo || '%')
               OR (s.norm_account IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(jli.account_name,'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_account || '%')
                  )
                GROUP BY s.source_file
                ORDER BY s.source_file
            """
        })

    # journal_entries + journal_entry_details
    if table_exists(cur, 'journal_entries') and table_exists(cur, 'journal_entry_details') \
       and column_exists(cur, 'journal_entries', 'journal_id') \
       and column_exists(cur, 'journal_entry_details', 'journal_id') \
       and (column_exists(cur, 'journal_entries', 'transaction_date') or column_exists(cur, 'journal_entries', 'entry_date')):
        je_date = 'transaction_date' if column_exists(cur, 'journal_entries', 'transaction_date') else 'entry_date'
        targets.append({
            'name': 'journal_entry_details',
            'query': f"""
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(d.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN journal_entry_details d
                  ON (
                        (s.debit > 0 AND COALESCE(d.debit_amount,0) = s.debit)
                     OR (s.credit > 0 AND COALESCE(d.credit_amount,0) = s.credit)
                  )
                LEFT JOIN journal_entries je ON je.journal_id = d.journal_id
                WHERE je.{je_date} = s.transaction_date
                GROUP BY s.source_file
                ORDER BY s.source_file
            """
        })

    # Helper to find first existing column among candidates
    def first_col(table, candidates):
        for c in candidates:
            if column_exists(cur, table, c):
                return c
        return None

    # Generic simple table comparison by date and amount columns
    def add_simple_date_amount_target(table_name):
        if not table_exists(cur, table_name):
            return
        date_col = first_col(table_name, ['transaction_date', 'date', 'entry_date', 'posted_date', 'payment_date', 'invoice_date'])
        amount_col = first_col(table_name, ['amount', 'total_amount'])
        debit_col = first_col(table_name, ['debit_amount', 'debit'])
        credit_col = first_col(table_name, ['credit_amount', 'credit'])
        if not date_col or not (amount_col or (debit_col and credit_col)):
            return
        # Unified amount expression on target side
        t_amount = None
        if amount_col:
            t_amount = f"COALESCE(t.{amount_col},0)"
        elif debit_col and credit_col:
            t_amount = f"COALESCE(t.{debit_col},0) - COALESCE(t.{credit_col},0)"
        else:
            return
        # Optional fuzzy text columns
        memo_col = first_col(table_name, ['memo', 'description', 'note', 'details'])
        account_text_col = first_col(table_name, ['account', 'account_name', 'account_code'])

        # Fuzzy: date +/-1 day and amount tolerance <= 0.01, plus optional normalized memo/account
        fuzzy_amount_expr = f"ABS({t_amount} - s.norm_amount) <= 0.01"

        fuzzy_text_expr = "TRUE"
        if memo_col or account_text_col:
            parts = []
            if memo_col:
                parts.append(
                    f"(s.norm_memo IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(t.{memo_col},'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_memo || '%')"
                )
            if account_text_col:
                parts.append(
                    f"(s.norm_account IS NOT NULL AND NULLIF(btrim(regexp_replace(lower(COALESCE(t.{account_text_col},'')), '[^a-z0-9]+', ' ', 'g')), '') LIKE '%' || s.norm_account || '%')"
                )
            fuzzy_text_expr = " OR ".join(parts) if parts else "TRUE"

        targets.append({
            'name': table_name,
            'query_strict': f"""
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(t.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN {table_name} t
                  ON t.{date_col} = s.transaction_date
                 AND ({t_amount}) = s.norm_amount
                GROUP BY s.source_file
                ORDER BY s.source_file
            """,
            'query_fuzzy': f"""
                SELECT s.source_file,
                       COUNT(*) AS staged_rows,
                       COUNT(t.*) AS matched_rows
                FROM tmp_qb_staging_compare s
                LEFT JOIN {table_name} t
                  ON t.{date_col} BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
                 AND ({fuzzy_amount_expr})
                 AND ({fuzzy_text_expr})
                GROUP BY s.source_file
                ORDER BY s.source_file
            """
        })

    # Add more simple targets
    for t in ['journal', 'payment_imports', 'payment_matches', 'payments', 'accounts_receivable']:
        add_simple_date_amount_target(t)

    # If no targets found, still return empty result
    # Execute both strict and fuzzy queries where available
    aggregated = {}
    for tgt in targets:
        # Strict
        cur.execute(tgt.get('query_strict', tgt.get('query')))
        for source_file, staged_rows, matched_rows in cur.fetchall():
            key = (tgt['name'], source_file)
            aggregated.setdefault(key, {'target': tgt['name'], 'source_file': source_file, 'staged_rows': int(staged_rows or 0), 'matched_strict': 0, 'matched_fuzzy': 0})
            aggregated[key]['matched_strict'] = int(matched_rows or 0)
        # Fuzzy
        if 'query_fuzzy' in tgt:
            cur.execute(tgt['query_fuzzy'])
            for source_file, staged_rows, matched_rows in cur.fetchall():
                key = (tgt['name'], source_file)
                aggregated.setdefault(key, {'target': tgt['name'], 'source_file': source_file, 'staged_rows': int(staged_rows or 0), 'matched_strict': 0, 'matched_fuzzy': 0})
                aggregated[key]['matched_fuzzy'] = int(matched_rows or 0)

    for (_, _), v in aggregated.items():
        v['unmatched_after_strict'] = v['staged_rows'] - v['matched_strict']
        v['unmatched_after_fuzzy'] = v['staged_rows'] - max(v['matched_strict'], v['matched_fuzzy'])
        results.append(v)

    return results


def save_report(rows):
    # Aggregate by source_file across all targets, and also output per-target details
    with open(REPORT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["target_table", "source_file", "staged_rows", "matched_strict", "matched_fuzzy", "unmatched_after_strict", "unmatched_after_fuzzy"])
        for r in rows:
            w.writerow([r['target'], r['source_file'], r['staged_rows'], r.get('matched_strict', 0), r.get('matched_fuzzy', 0), r.get('unmatched_after_strict', 0), r.get('unmatched_after_fuzzy', 0)])


def export_exceptions(cur):
    """Export unmatched staged rows (after fuzzy matching) for key targets.
    Creates CSVs: qb_unmatched_payments.csv, qb_unmatched_qb_staging.csv
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))

    # Payments unmatched (date ±1 and amount tolerance used in comparison)
    payments_file = os.path.join(base_dir, 'qb_unmatched_payments.csv')
    cur.execute(
        """
        WITH matched AS (
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
                        JOIN payments t
                            ON t.payment_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
                         AND ABS(COALESCE(t.amount,0) - s.norm_amount) <= 0.01
        )
        SELECT s.source_file, s.transaction_date, s.type, s.num, s.name, s.memo, s.account, s.debit, s.credit, s.amount
        FROM tmp_qb_staging_compare s
        WHERE s.id NOT IN (SELECT id FROM matched)
        ORDER BY s.source_file, s.transaction_date
        """
    )
    with open(payments_file, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["source_file", "transaction_date", "type", "num", "name", "memo", "account", "debit", "credit", "amount"])
        for row in cur.fetchall():
            w.writerow(row)

    # qb_transactions_staging unmatched
    qb_file = os.path.join(base_dir, 'qb_unmatched_qb_transactions_staging.csv')
    cur.execute(
        """
        WITH matched AS (
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
                        JOIN qb_transactions_staging t
                            ON t.transaction_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
             AND ABS(COALESCE(t.amount, COALESCE(t.debit_amount,0) - COALESCE(t.credit_amount,0)) - s.norm_amount) <= 0.01
        )
        SELECT s.source_file, s.transaction_date, s.type, s.num, s.name, s.memo, s.account, s.debit, s.credit, s.amount
        FROM tmp_qb_staging_compare s
        WHERE s.id NOT IN (SELECT id FROM matched)
        ORDER BY s.source_file, s.transaction_date
        """
    )
    with open(qb_file, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["source_file", "transaction_date", "type", "num", "name", "memo", "account", "debit", "credit", "amount"])
        for row in cur.fetchall():
            w.writerow(row)


def save_unmatched_by_year(cur):
    """Produce a year-based summary of unmatched staged rows after fuzzy matching against key targets.
    We'll treat a staged row as matched if it matches in any of: payments, qb_transactions_staging,
    general_ledger_lines, journal_line_items, or generic date/amount targets.
    """
    # Build a big matched set using fuzzy windows
    queries = []
    # payments
    if table_exists(cur, 'payments') and column_exists(cur, 'payments', 'payment_date') and column_exists(cur, 'payments', 'amount'):
        queries.append("""
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
            JOIN payments t
              ON t.payment_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
             AND ABS(COALESCE(t.amount,0) - s.norm_amount) <= 0.01
        """)
    # qb_transactions_staging
    if table_exists(cur, 'qb_transactions_staging'):
        queries.append("""
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
            JOIN qb_transactions_staging t
              ON t.transaction_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
             AND ABS(COALESCE(t.amount, COALESCE(t.debit_amount,0) - COALESCE(t.credit_amount,0)) - s.norm_amount) <= 0.01
        """)
    # general_ledger_lines + entries
    if table_exists(cur, 'general_ledger_lines') and table_exists(cur, 'general_ledger_entries') \
       and column_exists(cur, 'general_ledger_lines', 'header_id') \
       and column_exists(cur, 'general_ledger_entries', 'entry_date'):
        queries.append("""
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
            JOIN general_ledger_lines gl
              ON ABS(COALESCE(gl.debit_amount,0) - COALESCE(gl.credit_amount,0) - s.norm_amount) <= 0.01
            JOIN general_ledger_entries ge ON ge.entry_id = gl.header_id
            WHERE ge.entry_date BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
        """)
    # journal_line_items + general_journal
    if table_exists(cur, 'journal_line_items') and table_exists(cur, 'general_journal') \
       and column_exists(cur, 'journal_line_items', 'journal_entry_id') \
       and (column_exists(cur, 'general_journal', 'entry_date') or column_exists(cur, 'general_journal', 'transaction_date')):
        date_col = 'entry_date' if column_exists(cur, 'general_journal', 'entry_date') else 'transaction_date'
        queries.append(f"""
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
            JOIN journal_line_items jli
              ON ABS(COALESCE(jli.debit_amount,0) - COALESCE(jli.credit_amount,0) - s.norm_amount) <= 0.01
            JOIN general_journal gj ON gj.journal_entry_id = jli.journal_entry_id
            WHERE gj.{date_col} BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
        """)

    # Generic tables (date + amount or debit/credit)
    for table_name in ['journal', 'payment_imports', 'payment_matches', 'accounts_receivable']:
        if not table_exists(cur, table_name):
            continue
        # Try to find date and amount columns
        def first_col(table, candidates):
            for c in candidates:
                if column_exists(cur, table, c):
                    return c
            return None
        date_col = first_col(table_name, ['transaction_date', 'date', 'entry_date', 'posted_date', 'payment_date', 'invoice_date'])
        amount_col = first_col(table_name, ['amount', 'total_amount'])
        debit_col = first_col(table_name, ['debit_amount', 'debit'])
        credit_col = first_col(table_name, ['credit_amount', 'credit'])
        if not date_col or not (amount_col or (debit_col and credit_col)):
            continue
        if amount_col:
            t_amount = f"COALESCE(t.{amount_col},0)"
        else:
            t_amount = f"COALESCE(t.{debit_col},0) - COALESCE(t.{credit_col},0)"
        queries.append(f"""
            SELECT DISTINCT s.id
            FROM tmp_qb_staging_compare s
            JOIN {table_name} t
              ON t.{date_col} BETWEEN s.transaction_date - INTERVAL '2 day' AND s.transaction_date + INTERVAL '2 day'
             AND ABS({t_amount} - s.norm_amount) <= 0.01
        """)

    union_query = " UNION " .join(queries) if queries else "SELECT NULL::int WHERE FALSE"
    cur.execute(f"""
        WITH matched AS (
            {union_query}
        )
        SELECT EXTRACT(YEAR FROM s.transaction_date)::int AS year,
               COUNT(*) AS unmatched_count
        FROM tmp_qb_staging_compare s
        WHERE s.id NOT IN (SELECT id FROM matched)
        GROUP BY 1
        ORDER BY 1
    """)
    rows = cur.fetchall()
    with open(UNMATCHED_BY_YEAR_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["year", "unmatched_count"])
        for year, count in rows:
            w.writerow([int(year), int(count)])


def main():
    print("[COMPARE] Loading CSV files and staging rows…")
    all_rows = []
    for fp in discover_csv_files():
        rows = load_csv_rows(fp)
        print(f"  - {os.path.basename(fp)}: {len(rows)} staged rows")
        all_rows.extend(rows)

    if not all_rows:
        print("[ERROR] No rows staged from CSVs. Aborting.")
        sys.exit(1)

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            create_temp_table(cur)
            inserted = bulk_insert(cur, all_rows)
            conn.commit()
            print(f"[DB] Inserted {inserted} staged rows into temporary table")

            print("[COMPARE] Detecting target tables and computing matches…")
            results = compare_against_targets(cur)

        # Export exceptions while temp table is alive in this session
        with conn.cursor() as cur:
            try:
                export_exceptions(cur)
                conn.commit()
            except Exception as ex:
                print(f"[WARN] Failed to export exception lists: {ex}")
            try:
                save_unmatched_by_year(cur)
                conn.commit()
                print(f"[OUT] Year summary saved: {UNMATCHED_BY_YEAR_PATH}")
            except Exception as ex:
                print(f"[WARN] Failed to save unmatched-by-year: {ex}")

        save_report(results)
        print("[DONE] Comparison complete.")
        if results:
            # Print a brief summary
            for r in results:
                print(f"  {r['target']} | {r['source_file']}: staged={r['staged_rows']}, strict={r.get('matched_strict',0)}, fuzzy={r.get('matched_fuzzy',0)}, new≤strict={r.get('unmatched_after_strict',0)}, new≤fuzzy={r.get('unmatched_after_fuzzy',0)}")
        else:
            print("[WARN] No recognized accounting tables found to compare against.")
        print(f"[OUT] Report saved: {REPORT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
