import csv
import pathlib
import sys
from typing import Dict, Optional, Tuple

# Ensure we can import api.get_db_connection
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import get_db_connection  # type: ignore

MAPPINGS_DIR = ROOT / 'reports' / 'mappings'

# Input files produced by scripts/propose_mappings.py
FILES = {
    'class_to_coa': MAPPINGS_DIR / 'epson_classifications_to_coa.csv',
    'class_to_cashflow': MAPPINGS_DIR / 'epson_classifications_to_cash_flow_categories.csv',
    'payacct_to_coa': MAPPINGS_DIR / 'epson_pay_accounts_to_accounts.csv',
    'methods_to_canonical': MAPPINGS_DIR / 'epson_pay_methods_to_canonical.csv',
}


def read_csv_map(path: pathlib.Path) -> Tuple[list, list]:
    rows = []
    headers = []
    if not path.exists():
        print(f"[WARN] Missing mapping file: {path}")
        return headers, rows
    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        for r in reader:
            if not r or all((c or '').strip() == '' for c in r):
                continue
            rows.append(r)
    return headers, rows


def build_name_to_id(cur) -> Dict[str, int]:
    cur.execute("SELECT account_id, account_name FROM chart_of_accounts")
    return { (name or '').strip().lower(): aid for (aid, name) in cur.fetchall() }


def upsert_classifications(cur, name_to_id):
    h, rows = read_csv_map(FILES['class_to_coa'])
    idx_class = h.index('epson_classification') if 'epson_classification' in h else 0
    idx_name = h.index('suggested_account_name') if 'suggested_account_name' in h else 1
    idx_conf = h.index('confidence') if 'confidence' in h else None
    idx_alt = h.index('alternatives') if 'alternatives' in h else None

    # Also load cash flow suggestions
    hcf, rows_cf = read_csv_map(FILES['class_to_cashflow'])
    cf_map: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}
    if hcf:
        c_idx = hcf.index('epson_classification')
        s_idx = hcf.index('suggested_cash_flow_category') if 'suggested_cash_flow_category' in hcf else None
        conf_idx = hcf.index('confidence') if 'confidence' in hcf else None
        alt_idx = hcf.index('alternatives') if 'alternatives' in hcf else None
        for r in rows_cf:
            key = (r[c_idx] or '').strip()
            cf_map[key] = (
                (r[s_idx] if s_idx is not None else None),
                (r[conf_idx] if conf_idx is not None else None),
                (r[alt_idx] if alt_idx is not None else None),
            )

    for r in rows:
        epson_class = (r[idx_class] or '').strip()
        acct_name = (r[idx_name] or '').strip()
        conf = float(r[idx_conf]) if (idx_conf is not None and (r[idx_conf] or '').strip()) else None
        alts = (r[idx_alt] or '').strip() if idx_alt is not None else None
        acct_id = name_to_id.get(acct_name.lower()) if acct_name else None
        cf_sugg, cf_conf, cf_alts = cf_map.get(epson_class, (None, None, None))

        cur.execute(
            """
            INSERT INTO epson_classifications_map (epson_classification, mapped_account_id, mapped_account_name, mapped_cash_flow_category, confidence, alternatives, status)
            VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s >= 0.9 THEN 'approved' ELSE 'proposed' END)
            ON CONFLICT (epson_classification) DO UPDATE SET
              mapped_account_id = EXCLUDED.mapped_account_id,
              mapped_account_name = EXCLUDED.mapped_account_name,
              mapped_cash_flow_category = EXCLUDED.mapped_cash_flow_category,
              confidence = EXCLUDED.confidence,
              alternatives = EXCLUDED.alternatives,
              updated_at = NOW()
            """,
            [epson_class, acct_id, acct_name or None, cf_sugg, conf, alts or cf_alts, (conf or 0.0)]
        )


def upsert_pay_accounts(cur, name_to_id):
    h, rows = read_csv_map(FILES['payacct_to_coa'])
    if not h:
        return
    idx_acc = h.index('epson_pay_account')
    idx_name = h.index('suggested_account_name')
    idx_conf = h.index('confidence') if 'confidence' in h else None
    idx_alt = h.index('alternatives') if 'alternatives' in h else None

    for r in rows:
        epson_acc = (r[idx_acc] or '').strip()
        acct_name = (r[idx_name] or '').strip()
        conf = float(r[idx_conf]) if (idx_conf is not None and (r[idx_conf] or '').strip()) else None
        alts = (r[idx_alt] or '').strip() if idx_alt is not None else None
        acct_id = name_to_id.get(acct_name.lower()) if acct_name else None

        cur.execute(
            """
            INSERT INTO epson_pay_accounts_map (epson_pay_account, mapped_account_id, mapped_account_name, confidence, alternatives, status)
            VALUES (%s, %s, %s, %s, %s, CASE WHEN %s >= 0.9 THEN 'approved' ELSE 'proposed' END)
            ON CONFLICT (epson_pay_account) DO UPDATE SET
              mapped_account_id = EXCLUDED.mapped_account_id,
              mapped_account_name = EXCLUDED.mapped_account_name,
              confidence = EXCLUDED.confidence,
              alternatives = EXCLUDED.alternatives,
              updated_at = NOW()
            """,
            [epson_acc, acct_id, acct_name or None, conf, alts, (conf or 0.0)]
        )


def upsert_pay_methods(cur):
    h, rows = read_csv_map(FILES['methods_to_canonical'])
    if not h:
        return
    idx_m = h.index('epson_pay_method')
    idx_can = h.index('suggested_method')
    idx_conf = h.index('confidence') if 'confidence' in h else None
    idx_alt = h.index('alternatives') if 'alternatives' in h else None

    for r in rows:
        epm = (r[idx_m] or '').strip()
        can = (r[idx_can] or '').strip()
        conf = float(r[idx_conf]) if (idx_conf is not None and (r[idx_conf] or '').strip()) else None
        alts = (r[idx_alt] or '').strip() if idx_alt is not None else None
        cur.execute(
            """
            INSERT INTO epson_pay_methods_map (epson_pay_method, canonical_method, confidence, alternatives, status)
            VALUES (%s, %s, %s, %s, CASE WHEN %s >= 0.9 THEN 'approved' ELSE 'proposed' END)
            ON CONFLICT (epson_pay_method) DO UPDATE SET
              canonical_method = EXCLUDED.canonical_method,
              confidence = EXCLUDED.confidence,
              alternatives = EXCLUDED.alternatives,
              updated_at = NOW()
            """,
            [epm, can or None, conf, alts, (conf or 0.0)]
        )


def main():
    conn = get_db_connection(); conn.autocommit = False
    try:
        cur = conn.cursor()
        # Ensure tables exist (in case migration not applied yet)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS epson_classifications_map (
            epson_classification TEXT PRIMARY KEY,
            mapped_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
            mapped_account_name TEXT NULL,
            mapped_cash_flow_category TEXT NULL,
            confidence NUMERIC(5,2) NULL,
            alternatives TEXT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'proposed',
            notes TEXT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS epson_pay_accounts_map (
            epson_pay_account TEXT PRIMARY KEY,
            mapped_account_id INTEGER NULL REFERENCES chart_of_accounts(account_id),
            mapped_account_name TEXT NULL,
            confidence NUMERIC(5,2) NULL,
            alternatives TEXT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'proposed',
            notes TEXT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS epson_pay_methods_map (
            epson_pay_method TEXT PRIMARY KEY,
            canonical_method TEXT NULL,
            confidence NUMERIC(5,2) NULL,
            alternatives TEXT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'proposed',
            notes TEXT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        );
        """)

        name_to_id = build_name_to_id(cur)
        upsert_classifications(cur, name_to_id)
        upsert_pay_accounts(cur, name_to_id)
        upsert_pay_methods(cur)
        conn.commit()
        print("[OK] Epson mappings loaded/updated.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
