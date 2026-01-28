#!/usr/bin/env python3
"""
Import and reconcile Interac e-Transfers to banking

- Imports processed e-transfer CSV into etransfers_processed
- Reconciles to banking_transactions with tunable logic
- Writes report to reports/etransfer_reconciliation_report.csv
"""

import csv
import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional

import psycopg2
from decimal import Decimal

DB = dict(
    dbname=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)


def ensure_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS etransfers_processed (
          id SERIAL PRIMARY KEY,
          etransfer_date date NOT NULL,
          amount numeric(12,2) NOT NULL,
          direction text,
          type_desc text,
          counterparty_role text,
          company text,
          reference_code text,
          gl_code text,
          category text,
          status text,
          source_email text,
          source_file text,
          source_hash text UNIQUE,
          created_at timestamp DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS etransfer_banking_reconciliation (
          id SERIAL PRIMARY KEY,
          etransfer_id integer NOT NULL REFERENCES etransfers_processed(id) ON DELETE CASCADE,
          transaction_id integer REFERENCES banking_transactions(transaction_id),
          account_number text,
          transaction_date date,
          match_type text,
          match_score integer,
          amount numeric(12,2),
          created_at timestamp DEFAULT now(),
          UNIQUE(etransfer_id)
        );
        """
    )


def etransfer_source_hash(r: Dict[str, Any], csv_basename: str) -> str:
    parts = [
        str(r.get('etransfer_date') or ''),
        f"{r.get('amount')}",
        (r.get('reference_code') or '').lower(),
        (r.get('source_email') or '').lower(),
        (r.get('direction') or '').lower(),
        csv_basename.lower(),
    ]
    return hashlib.md5("|".join(parts).encode('utf-8')).hexdigest()


def parse_row_by_header(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    def g(*names):
        for n in names:
            for key in (n, n.lower(), n.title(), n.upper()):
                if key in row and row[key] != '':
                    return row[key]
        return None

    date_s = g('date', 'etransfer_date')
    amt_s = g('amount', 'amt')
    direction = g('direction', 'type')
    type_desc = g('description', 'type_desc')
    role = g('counterparty_role', 'role') or g('payer_type', 'payee_type') or g('party')
    company = g('company', 'account', 'organization')
    ref = g('reference_code', 'ref', 'reference')
    gl = g('gl_code', 'gl')
    cat = g('category')
    status = g('status')
    email = g('source_email', 'email_file', 'email')

    if not date_s or not amt_s:
        return None
    dt = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(date_s).strip(), fmt).date()
            break
        except Exception:
            continue
    if dt is None:
        return None
    try:
        amt = float(str(amt_s).replace(',', '').strip())
    except Exception:
        return None

    return dict(
        etransfer_date=dt,
        amount=round(amt, 2),
        direction=(direction or '').strip() or None,
        type_desc=(type_desc or '').strip() or None,
        counterparty_role=(role or '').strip() or None,
        company=(company or '').strip() or None,
        reference_code=(ref or '').strip() or None,
        gl_code=(gl or '').strip() or None,
        category=(cat or '').strip() or None,
        status=(status or '').strip() or None,
        source_email=(email or '').strip() or None,
    )


def parse_row_by_position(cols: List[str]) -> Optional[Dict[str, Any]]:
    if len(cols) < 2:
        return None
    dt = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(cols[0]).strip(), fmt).date()
            break
        except Exception:
            continue
    if dt is None:
        return None
    try:
        amt = float(str(cols[1]).replace(',', ''))
    except Exception:
        return None

    return dict(
        etransfer_date=dt,
        amount=round(amt, 2),
        direction=(cols[2].strip() if len(cols) > 2 else None),
        type_desc=(cols[3].strip() if len(cols) > 3 else None),
        counterparty_role=(cols[4].strip() if len(cols) > 4 else None),
        company=(cols[5].strip() if len(cols) > 5 else None),
        reference_code=(cols[6].strip() if len(cols) > 6 else None),
        gl_code=(cols[7].strip() if len(cols) > 7 else None),
        category=(cols[8].strip() if len(cols) > 8 else None),
        status=(cols[9].strip() if len(cols) > 9 else None),
        source_email=(cols[10].strip() if len(cols) > 10 else None),
    )


def import_csv(cur, csv_path: str) -> Dict[str, Any]:
    base = os.path.basename(csv_path)
    imported = 0
    updated = 0
    first_dt = None
    last_dt = None

    with open(csv_path, newline='', encoding='utf-8') as f:
        pos = f.tell()
        sniffer = csv.Sniffer()
        sample = f.read(2048)
        f.seek(pos)
        try:
            dialect = sniffer.sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        rows = list(reader)

    if not rows:
        return dict(imported=0, updated=0, first_date=None, last_date=None)

    def looks_like_date(s: str) -> bool:
        try:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    datetime.strptime(s.strip(), fmt)
                    return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    has_header = not looks_like_date(rows[0][0])
    header = [c.strip() for c in rows[0]] if has_header else None
    data_rows = rows[1:] if has_header else rows

    for cols in data_rows:
        if header:
            row_map = {header[i]: (cols[i] if i < len(cols) else '') for i in range(len(header))}
            r = parse_row_by_header(row_map)
        else:
            r = parse_row_by_position(cols)
        if not r:
            continue

        if first_dt is None or r['etransfer_date'] < first_dt:
            first_dt = r['etransfer_date']
        if last_dt is None or r['etransfer_date'] > last_dt:
            last_dt = r['etransfer_date']

        sh = etransfer_source_hash(r, base)
        cur.execute(
            """
            INSERT INTO etransfers_processed (
              etransfer_date, amount, direction, type_desc, counterparty_role, company, reference_code,
              gl_code, category, status, source_email, source_file, source_hash
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (source_hash) DO UPDATE SET
              direction = COALESCE(EXCLUDED.direction, etransfers_processed.direction),
              type_desc = COALESCE(EXCLUDED.type_desc, etransfers_processed.type_desc),
              counterparty_role = COALESCE(EXCLUDED.counterparty_role, etransfers_processed.counterparty_role),
              company = COALESCE(EXCLUDED.company, etransfers_processed.company),
              reference_code = COALESCE(EXCLUDED.reference_code, etransfers_processed.reference_code),
              gl_code = COALESCE(EXCLUDED.gl_code, etransfers_processed.gl_code),
              category = COALESCE(EXCLUDED.category, etransfers_processed.category),
              status = COALESCE(EXCLUDED.status, etransfers_processed.status),
              source_email = COALESCE(EXCLUDED.source_email, etransfers_processed.source_email)
            RETURNING (xmax = 0) AS inserted
            """,
            (
                r['etransfer_date'], r['amount'], r.get('direction'), r.get('type_desc'), r.get('counterparty_role'),
                r.get('company'), r.get('reference_code'), r.get('gl_code'), r.get('category'), r.get('status'),
                r.get('source_email'), base, sh
            )
        )
        if cur.fetchone()[0]:
            imported += 1
        else:
            updated += 1

    return dict(imported=imported, updated=updated, first_date=first_dt, last_date=last_dt)


def reconcile_to_banking(cur) -> Dict[str, int]:
    cur.execute(
        """
        WITH pending AS (
            SELECT e.id,
                   e.etransfer_date,
                   e.amount,
                   COALESCE(e.direction,'') AS direction,
                   e.reference_code,
                   COALESCE(e.company,'') AS company,
                   COALESCE(e.category,'') AS category,
                   COALESCE(e.gl_code,'') AS gl_code
            FROM etransfers_processed e
            LEFT JOIN etransfer_banking_reconciliation r ON r.etransfer_id = e.id
            WHERE r.etransfer_id IS NULL
        ),
        bt AS (
            SELECT transaction_id, transaction_date, account_number, description,
                   debit_amount, credit_amount,
                   CASE
                       WHEN description ILIKE '%INTERAC%'
                         OR description ILIKE '%E-TRANSFER%'
                         OR description ILIKE '%E TRANSFER%'
                         OR description ILIKE '%E-TRF%'
                         OR description ILIKE '%EMT%'
                         OR description ILIKE '%PREAUTHORIZED DEBIT HEFFNER AUTO%'
                         OR description ILIKE '%EFT DEBIT REVERSAL HEFFNER AUTO%'
                       THEN 0 ELSE 1
                   END AS desc_pref
            FROM banking_transactions
        ),
        candidates AS (
            -- Primary: match by amount within ±0.50 and date within ±15 days
            SELECT p.id AS etransfer_id,
                   b.transaction_id,
                   b.account_number,
                   b.transaction_date,
                   CASE 
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 THEN 'credit'
                       WHEN ABS(COALESCE(b.debit_amount,0)  - p.amount) <= 0.50 THEN 'debit'
                       ELSE CASE WHEN p.direction ILIKE 'received' THEN 'credit' ELSE 'debit' END
                   END AS match_type,
                   ABS(EXTRACT(EPOCH FROM (b.transaction_date::timestamp - p.etransfer_date::timestamp)))::int AS date_diff_seconds,
                   p.amount,
                   b.desc_pref,
                   CASE
                       WHEN p.company <> '' AND b.description ILIKE ('%' || p.company || '%') THEN 0
                       WHEN (p.category ILIKE 'fuel%%' OR p.gl_code ILIKE '%%FUEL%%') AND (
                             b.description ILIKE '%ESSO%'
                          OR b.description ILIKE '%7-ELEVEN%'
                          OR b.description ILIKE '%7 ELEVEN%'
                          OR b.description ILIKE '%7-11%'
                          OR b.description ILIKE '%SHELL%'
                          OR b.description ILIKE '%PETRO%'
                          OR b.description ILIKE '%PETRO-CANADA%'
                          OR b.description ILIKE '%PETROCAN%'
                          OR b.description ILIKE '%PETROCANADA%'
                          OR b.description ILIKE '%HUSKY%'
                          OR b.description ILIKE '%CO-OP%'
                          OR b.description ILIKE '%COOP%'
                       ) THEN 0
                       ELSE 1
                   END AS vendor_pref,
                   CASE 
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 AND p.direction ILIKE 'received' THEN 0
                       WHEN ABS(COALESCE(b.debit_amount,0)  - p.amount) <= 0.50 AND p.direction ILIKE 'sent' THEN 0
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 OR ABS(COALESCE(b.debit_amount,0) - p.amount) <= 0.50 THEN 1
                       ELSE 2
                   END AS side_pref,
                   ABS(COALESCE(b.credit_amount, COALESCE(b.debit_amount, 0)) - p.amount) AS amount_diff
            FROM pending p
            JOIN bt b
              ON b.transaction_date BETWEEN p.etransfer_date - INTERVAL '15 day' AND p.etransfer_date + INTERVAL '15 day'
             AND (
                   ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50
                OR ABS(COALESCE(b.debit_amount,0)  - p.amount) <= 0.50
             )

            UNION ALL

            -- Reference-code: description contains the e-transfer reference code (±30 days)
            SELECT p.id AS etransfer_id,
                   b.transaction_id,
                   b.account_number,
                   b.transaction_date,
                   CASE 
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 THEN 'credit'
                       WHEN ABS(COALESCE(b.debit_amount,0)  - p.amount) <= 0.50 THEN 'debit'
                       ELSE CASE WHEN p.direction ILIKE 'received' THEN 'credit' ELSE 'debit' END
                   END AS match_type,
                   ABS(EXTRACT(EPOCH FROM (b.transaction_date::timestamp - p.etransfer_date::timestamp)))::int AS date_diff_seconds,
                   p.amount,
                   0 AS desc_pref,
                   CASE
                       WHEN p.company <> '' AND b.description ILIKE ('%' || p.company || '%') THEN 0
                       WHEN (p.category ILIKE 'fuel%%' OR p.gl_code ILIKE '%%FUEL%%') AND (
                             b.description ILIKE '%ESSO%'
                          OR b.description ILIKE '%7-ELEVEN%'
                          OR b.description ILIKE '%7 ELEVEN%'
                          OR b.description ILIKE '%7-11%'
                          OR b.description ILIKE '%SHELL%'
                          OR b.description ILIKE '%PETRO%'
                          OR b.description ILIKE '%PETRO-CANADA%'
                          OR b.description ILIKE '%PETROCAN%'
                          OR b.description ILIKE '%PETROCANADA%'
                          OR b.description ILIKE '%HUSKY%'
                          OR b.description ILIKE '%CO-OP%'
                          OR b.description ILIKE '%COOP%'
                       ) THEN 0
                       ELSE 1
                   END AS vendor_pref,
                   CASE 
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 AND p.direction ILIKE 'received' THEN 0
                       WHEN ABS(COALESCE(b.debit_amount,0)  - p.amount) <= 0.50 AND p.direction ILIKE 'sent' THEN 0
                       WHEN ABS(COALESCE(b.credit_amount,0) - p.amount) <= 0.50 OR ABS(COALESCE(b.debit_amount,0) - p.amount) <= 0.50 THEN 1
                       ELSE 2
                   END AS side_pref,
                   ABS(COALESCE(b.credit_amount, COALESCE(b.debit_amount, 0)) - p.amount) AS amount_diff
            FROM pending p
            JOIN bt b
              ON b.transaction_date BETWEEN p.etransfer_date - INTERVAL '30 day' AND p.etransfer_date + INTERVAL '30 day'
             AND p.reference_code IS NOT NULL AND p.reference_code <> ''
             AND b.description ILIKE ('%' || p.reference_code || '%')

            UNION ALL

            -- Fallback: any banking transaction within window and tolerance, no description constraints
            SELECT p.id AS etransfer_id,
                   b2.transaction_id,
                   b2.account_number,
                   b2.transaction_date,
                   CASE 
                       WHEN ABS(COALESCE(b2.credit_amount,0) - p.amount) <= 0.50 THEN 'credit'
                       WHEN ABS(COALESCE(b2.debit_amount,0)  - p.amount) <= 0.50 THEN 'debit'
                       ELSE CASE WHEN p.direction ILIKE 'received' THEN 'credit' ELSE 'debit' END
                   END AS match_type,
                   ABS(EXTRACT(EPOCH FROM (b2.transaction_date::timestamp - p.etransfer_date::timestamp)))::int AS date_diff_seconds,
                   p.amount,
                   2 AS desc_pref,
                   CASE
                       WHEN p.company <> '' AND b2.description ILIKE ('%' || p.company || '%') THEN 0
                       WHEN (p.category ILIKE 'fuel%%' OR p.gl_code ILIKE '%%FUEL%%') AND (
                             b2.description ILIKE '%ESSO%'
                          OR b2.description ILIKE '%7-ELEVEN%'
                          OR b2.description ILIKE '%7 ELEVEN%'
                          OR b2.description ILIKE '%7-11%'
                          OR b2.description ILIKE '%SHELL%'
                          OR b2.description ILIKE '%PETRO%'
                          OR b2.description ILIKE '%PETRO-CANADA%'
                          OR b2.description ILIKE '%PETROCAN%'
                          OR b2.description ILIKE '%PETROCANADA%'
                          OR b2.description ILIKE '%HUSKY%'
                          OR b2.description ILIKE '%CO-OP%'
                          OR b2.description ILIKE '%COOP%'
                       ) THEN 0
                       ELSE 1
                   END AS vendor_pref,
                   CASE 
                       WHEN ABS(COALESCE(b2.credit_amount,0) - p.amount) <= 0.50 AND p.direction ILIKE 'received' THEN 0
                       WHEN ABS(COALESCE(b2.debit_amount,0)  - p.amount) <= 0.50 AND p.direction ILIKE 'sent' THEN 0
                       WHEN ABS(COALESCE(b2.credit_amount,0) - p.amount) <= 0.50 OR ABS(COALESCE(b2.debit_amount,0) - p.amount) <= 0.50 THEN 1
                       ELSE 2
                   END AS side_pref,
                   ABS(COALESCE(b2.credit_amount, COALESCE(b2.debit_amount, 0)) - p.amount) AS amount_diff
            FROM pending p
            JOIN banking_transactions b2
              ON b2.transaction_date BETWEEN p.etransfer_date - INTERVAL '15 day' AND p.etransfer_date + INTERVAL '15 day'
             AND (
                   ABS(COALESCE(b2.credit_amount,0) - p.amount) <= 0.50
                OR ABS(COALESCE(b2.debit_amount,0)  - p.amount) <= 0.50
             )
        ),
        ranked AS (
            SELECT c.*, ROW_NUMBER() OVER (
                PARTITION BY c.etransfer_id
                ORDER BY c.side_pref ASC, c.vendor_pref ASC, c.desc_pref ASC, c.amount_diff ASC, c.date_diff_seconds ASC, c.transaction_id ASC
            ) AS rn
            FROM candidates c
        )
        INSERT INTO etransfer_banking_reconciliation(etransfer_id, transaction_id, account_number, transaction_date, match_type, match_score, amount)
        SELECT etransfer_id, transaction_id, account_number, transaction_date, match_type, date_diff_seconds, amount
        FROM ranked WHERE rn = 1
        RETURNING 1
        """
    )
    inserted = cur.rowcount or 0

    cur.execute("SELECT COUNT(*) FROM etransfers_processed")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM etransfer_banking_reconciliation")
    reconciled = cur.fetchone()[0]

    # Log unmatched + nearest candidates
    cur.execute(
        """
        SELECT e.id, e.etransfer_date, e.amount, e.direction, e.reference_code, e.company, e.source_email
        FROM etransfers_processed e
        LEFT JOIN etransfer_banking_reconciliation r ON r.etransfer_id = e.id
        WHERE r.etransfer_id IS NULL
        ORDER BY e.etransfer_date DESC
        LIMIT 15
        """
    )
    unmatched = cur.fetchall()

    os.makedirs('l:/limo/reports', exist_ok=True)
    with open('l:/limo/reports/unmatched_etransfers_candidates.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['etransfer_id','etransfer_date','amount','direction','reference_code','company','source_email','candidate_transaction_id','candidate_date','candidate_amount','candidate_desc'])
        for et_id, et_date, et_amt, et_dir, et_ref, et_comp, et_email in unmatched:
            # print closest 3 by date within ±15 days for diagnostics
            cur.execute(
                """
                SELECT transaction_id, transaction_date, COALESCE(credit_amount, debit_amount) AS amount, description
                FROM banking_transactions
                WHERE transaction_date BETWEEN (%s::date - INTERVAL '15 day') AND (%s::date + INTERVAL '15 day')
                ORDER BY ABS(EXTRACT(EPOCH FROM (transaction_date::timestamp - %s::timestamp))) ASC
                LIMIT 3
                """,
                (et_date, et_date, et_date),
            )
            for cand in cur.fetchall():
                w.writerow([et_id, et_date, et_amt, et_dir, et_ref, et_comp, et_email] + list(cand))

    return dict(new_links=inserted, total_etransfers=total, reconciled=reconciled, unmatched=max(total - reconciled, 0))


def write_report(cur, out_csv: str):
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    cur.execute(
        """
        SELECT e.id, e.etransfer_date, e.amount, e.direction, e.type_desc, e.counterparty_role, e.company, e.reference_code,
               e.category, e.status, e.source_email, e.source_file,
               r.transaction_id, r.account_number, r.transaction_date, r.match_type, r.match_score
        FROM etransfers_processed e
        LEFT JOIN etransfer_banking_reconciliation r ON r.etransfer_id = e.id
        ORDER BY e.etransfer_date, e.id
        """
    )
    rows = cur.fetchall()
    headers = [
        'etransfer_id','etransfer_date','amount','direction','type_desc','counterparty_role','company','reference_code',
        'category','status','source_email','source_file','transaction_id','account_number','transaction_date','match_type','match_score'
    ]
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Import and reconcile Interac e-Transfers')
    ap.add_argument('--csv', required=True, help='Path to etransfers-processed-*.csv')
    ap.add_argument('--json', help='Optional JSON summary for metadata validation')
    args = ap.parse_args()

    csv_path = args.csv
    json_path = args.json
    if not os.path.isfile(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")

    json_ok = False
    if json_path and os.path.isfile(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as jf:
                meta = json.load(jf)
            et_out = meta.get('etransfers', {}).get('outputFile')
            phase = meta.get('phase')
            print(f"JSON summary: phase={phase!r} outputFile={et_out!r}")
            json_ok = True
        except Exception as e:
            print(f"Warning: could not read JSON summary {json_path}: {e}")

    conn = psycopg2.connect(**DB)
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_schema(cur)
                print(f"\n📥 Importing CSV: {csv_path}")
                imp = import_csv(cur, csv_path)
                print(f"   Imported: {imp['imported']}, Updated: {imp['updated']}")
                if imp['first_date'] and imp['last_date']:
                    print(f"   Date range in CSV: {imp['first_date']} .. {imp['last_date']}")

                print("\n🔗 Reconciling to banking_transactions …")
                rec = reconcile_to_banking(cur)
                print(f"   New links created: {rec['new_links']}")
                print(f"   Reconciled total:  {rec['reconciled']} of {rec['total_etransfers']} (unmatched={rec['unmatched']})")

                out = os.path.join(os.path.dirname(os.path.dirname(csv_path)), 'reports', 'etransfer_reconciliation_report.csv')
                write_report(cur, out)
                print(f"\n📝 Report written: {out}")

                if imp['first_date'] and imp['last_date']:
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM etransfers_processed
                        WHERE etransfer_date BETWEEN %s AND %s
                        """,
                        (imp['first_date'], imp['last_date'])
                    )
                    cnt = cur.fetchone()[0]
                    print(f"\n[OK] Verification: {cnt} etransfer rows present in almsdata within the CSV date range.")

                if not json_ok and json_path:
                    print("[WARN] JSON summary not verified (read error). Proceeded with CSV only.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
