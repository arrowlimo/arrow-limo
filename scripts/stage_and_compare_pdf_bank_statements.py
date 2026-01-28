#!/usr/bin/env python3
"""
Stage transactions parsed from bank statement PDFs (CIBC & Scotia) and compare
against existing almsdata.banking_transactions to identify missing records.

- Extract transactions from OCR'd PDFs using pdfplumber
- Load into staging table staging_banking_pdf_transactions (idempotent via source_hash)
- For each staged record, check match in banking_transactions by date + amount (±$0.02)
- Emit a coverage report per file and overall summary

Supported inputs (adjust list below as needed):
- L:\\limo\\pdf\\2012cibc banking *.pdf
- L:\\limo\\pdf\\2012 scotia bank statements*.pdf

Note: This focuses on bank statements. QuickBooks and merchant PDFs are summaries
or different formats and are not staged here.
"""

import os
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

import pdfplumber
# Prefer specialized CIBC parser for higher accuracy if available
try:
    from parse_2012_cibc_pdfs import extract_transactions_from_pdf as cibc_extract
except Exception:
    cibc_extract = None
import psycopg2
from psycopg2.extras import RealDictCursor
import csv

PDF_FILES = [
    r"L:\\limo\\pdf\\2012cibc banking jan-mar_ocred.pdf",
    r"L:\\limo\\pdf\\2012cibc banking apr- may_ocred.pdf",
    r"L:\\limo\\pdf\\2012cibc banking jun-dec_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf",
    r"L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf",
]

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

# Database connection

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )


def ensure_staging_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS staging_banking_pdf_transactions (
            id SERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            page INTEGER,
            line_no INTEGER,
            bank VARCHAR(50),
            account_number VARCHAR(50),
            branch VARCHAR(50),
            statement_period_start DATE,
            statement_period_end DATE,
            transaction_date DATE NOT NULL,
            description TEXT,
            debit_amount NUMERIC(12,2),
            credit_amount NUMERIC(12,2),
            balance NUMERIC(12,2),
            source_hash TEXT UNIQUE,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def parse_month_day_token(token: str, year: int = 2012):
    m = re.match(r'^([A-Za-z]{3})\s*(\d{1,2})$', token.strip())
    if not m:
        return None
    mon = MONTH_MAP.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return datetime(year, mon, int(m.group(2))).date()
    except Exception:
        return None


def clean_amount(text: Optional[str]) -> Optional[Decimal]:
    if not text:
        return None
    t = text.strip()
    if t in ('', '-', 'V', 'c'):
        return None
    t = re.sub(r'[^\d().,-]', '', t)  # keep digits, dot, comma, parens, minus
    # parens mean negative (withdrawal often displayed without minus; we treat as positive for columns)
    neg = False
    if t.startswith('(') and t.endswith(')'):
        neg = True
        t = t[1:-1]
    t = t.replace(',', '')
    try:
        val = Decimal(t)
        if neg:
            val = -val
        # We store debits/credits as positive amounts in their respective columns
        return abs(val)
    except Exception:
        return None


def extract_account_and_period(text: str):
    account = None
    branch = None
    ps = None
    pe = None
    if not text:
        return account, branch, ps, pe
    acc_m = re.search(r'Account number[:\s]+([0-9\-]{5,})', text, re.IGNORECASE)
    if acc_m:
        account = acc_m.group(1).strip()
    else:
        # Scotia variant
        acc_m = re.search(r'Account\s*#[:\s]+([0-9\-]{5,})', text, re.IGNORECASE)
        if acc_m:
            account = acc_m.group(1).strip()
    br_m = re.search(r'Branch transit number[:\s]+(\d{3,5})', text, re.IGNORECASE)
    if br_m:
        branch = br_m.group(1).strip()
    else:
        br_m = re.search(r'Transit\s*#[:\s]+(\d{3,5})', text, re.IGNORECASE)
        if br_m:
            branch = br_m.group(1).strip()
    per_m = re.search(r'For\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+to\s+([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})', text)
    if per_m:
        sm, sd, em, ed, yr = per_m.groups()
        sm_i = MONTH_MAP.get(sm.lower()); em_i = MONTH_MAP.get(em.lower())
        if sm_i and em_i:
            try:
                ps = datetime(int(yr), sm_i, int(sd)).date()
                pe = datetime(int(yr), em_i, int(ed)).date()
            except Exception:
                pass
    return account, branch, ps, pe


def parse_cibc_or_scotia_transactions(pdf_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    is_cibc = 'cibc' in os.path.basename(pdf_path).lower()
    bank = 'CIBC' if is_cibc else 'SCOTIA'
    # Use specialized CIBC parser if present
    if is_cibc and cibc_extract is not None:
        try:
            txns = cibc_extract(pdf_path)
            for t in txns:
                rows.append({
                    'bank': bank,
                    'account': None,
                    'branch': None,
                    'statement_start': None,
                    'statement_end': None,
                    'date': t['date'],
                    'description': t['description'],
                    'debit': t.get('debit'),
                    'credit': t.get('credit'),
                    'balance': t.get('balance'),
                    'page': t.get('page'),
                    'line_no': None,
                    'source_file': os.path.basename(pdf_path)
                })
            return rows
        except Exception:
            # Fallback to generic if specialized fails
            pass
    try:
        with pdfplumber.open(pdf_path) as pdf:
            account = None
            branch = None
            ps = None
            pe = None
            # Use first page to capture header info
            if pdf.pages:
                head_text = pdf.pages[0].extract_text() or ''
                account, branch, ps, pe = extract_account_and_period(head_text)
            for page_idx, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split('\n')
                current_date = None
                # Track seen keys on this page to prevent duplicates from OCR wraps
                seen_keys = set()
                for ln, line in enumerate(lines, start=1):
                    # Skip obvious headers
                    if any(h in line for h in ['Account Statement', 'Transaction details', 'Withdrawals ($)', 'Balance ($)', 'Opening balance', 'Closing balance', 'Page '] ):
                        continue
                    # Detect new transaction line starting with e.g. "Jan 3" or numeric dates like 01/03/2012 or 2012-01-03
                    m = re.match(r'^([A-Z][a-z]{2}\s+\d{1,2})\s+(.+)$', line)
                    m_num = re.match(r'^(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\s+(.+)$', line)
                    if m:
                        d_token, rest = m.groups()
                        dt = parse_month_day_token(d_token, year=2012)
                        if not dt:
                            continue
                        current_date = dt
                    elif m_num:
                        d_token, rest = m_num.groups()
                        # Try numeric date parsing
                        try:
                            if d_token.count('/'):
                                parts = d_token.split('/')
                            else:
                                parts = d_token.split('-')
                            if len(parts[0]) == 4:
                                # YYYY-MM-DD
                                dt = datetime(int(parts[0]), int(parts[1]), int(parts[2])).date()
                            else:
                                # MM/DD/YYYY (assume North American)
                                dt = datetime(int(parts[2]), int(parts[0]), int(parts[1])).date()
                        except Exception:
                            dt = None
                        if not dt or dt.year != 2012:
                            continue
                        current_date = dt
                    else:
                        d_token = None
                        rest = None
                    if current_date and rest:
                        # Extract amounts (numbers with 2 decimals)
                        nums = re.findall(r'[\d,]+\.\d{2}', rest)
                        if not nums:
                            continue
                        # Description is text up to first amount
                        desc_m = re.match(r'(.+?)\s*[\d,]+\.\d{2}', rest)
                        description = (desc_m.group(1).strip() if desc_m else rest).strip()
                        # Only keep plausible transaction lines by keyword to avoid OCR noise
                        DESC_U = description.upper()
                        KEYWORDS = (
                            'PURCHASE', 'ABM WITHDRAWAL', 'WITHDRAWAL', 'DEPOSIT', 'TRANSFER', 'CHEQUE',
                            'CREDIT MEMO', 'DEBIT MEMO', 'MISC PAYMENT', 'E-TRANSFER', 'INTERNET BILL PMT', 'BILL PMT', 'SERVICE CHARGE', 'BANK FEE'
                        )
                        if not any(k in DESC_U for k in KEYWORDS):
                            continue
                        amounts = [clean_amount(n) for n in nums]
                        amounts = [a for a in amounts if a is not None]
                        if len(amounts) >= 2:
                            # Heuristic:
                            # - If description indicates deposit/credit, treat first as credit
                            # - Else treat first as debit
                            credit_keywords = ['DEPOSIT', 'CREDIT', 'E-TRANSFER RECLAIM', 'MISC PAYMENT']
                            is_credity = any(k in description.upper() for k in credit_keywords)
                            if len(amounts) == 2:
                                debit = None
                                credit = None
                                if is_credity:
                                    credit = amounts[0]
                                    balance = amounts[1]
                                else:
                                    debit = amounts[0]
                                    balance = amounts[1]
                            else:  # 3+ amounts: assume [debit, credit, balance] or [debit, balance, ???]
                                debit = amounts[0]
                                credit = amounts[1]
                                balance = amounts[-1]
                            # De-dup key within page
                            key = (current_date, description, float(debit or 0), float(credit or 0))
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            rows.append({
                                'bank': bank,
                                'account': account,
                                'branch': branch,
                                'statement_start': ps,
                                'statement_end': pe,
                                'date': current_date,
                                'description': re.sub(r'\s+', ' ', description),
                                'debit': debit,
                                'credit': credit,
                                'balance': balance if 'balance' in locals() else None,
                                'page': page_idx,
                                'line_no': ln,
                                'source_file': os.path.basename(pdf_path)
                            })
                        continue
                    # Continuation lines that still hold amounts
                    if current_date:
                        nums = re.findall(r'[\d,]+\.\d{2}', line)
                        if nums:
                            desc_m = re.match(r'(.+?)\s*[\d,]+\.\d{2}', line)
                            description = (desc_m.group(1).strip() if desc_m else line).strip()
                            DESC_U = description.upper()
                            KEYWORDS = (
                                'PURCHASE', 'ABM WITHDRAWAL', 'WITHDRAWAL', 'DEPOSIT', 'TRANSFER', 'CHEQUE',
                                'CREDIT MEMO', 'DEBIT MEMO', 'MISC PAYMENT', 'E-TRANSFER', 'INTERNET BILL PMT', 'BILL PMT', 'SERVICE CHARGE', 'BANK FEE'
                            )
                            if not any(k in DESC_U for k in KEYWORDS):
                                continue
                            amounts = [clean_amount(n) for n in nums]
                            amounts = [a for a in amounts if a is not None]
                            if len(amounts) >= 2:
                                credit_keywords = ['DEPOSIT', 'CREDIT', 'E-TRANSFER RECLAIM', 'MISC PAYMENT']
                                is_credity = any(k in description.upper() for k in credit_keywords)
                                if len(amounts) == 2:
                                    debit = None; credit = None
                                    if is_credity:
                                        credit = amounts[0]; balance = amounts[1]
                                    else:
                                        debit = amounts[0]; balance = amounts[1]
                                else:
                                    debit = amounts[0]; credit = amounts[1]; balance = amounts[-1]
                                key = (current_date, description, float(debit or 0), float(credit or 0))
                                if key in seen_keys:
                                    continue
                                seen_keys.add(key)
                                rows.append({
                                    'bank': bank,
                                    'account': account,
                                    'branch': branch,
                                    'statement_start': ps,
                                    'statement_end': pe,
                                    'date': current_date,
                                    'description': re.sub(r'\s+', ' ', description),
                                    'debit': debit,
                                    'credit': credit,
                                    'balance': balance if 'balance' in locals() else None,
                                    'page': page_idx,
                                    'line_no': ln,
                                    'source_file': os.path.basename(pdf_path)
                                })
    except Exception as e:
        print(f"[WARN]  Error parsing {pdf_path}: {e}")
    return rows


def compute_hash(rec: Dict[str, Any]) -> str:
    key = f"{rec.get('source_file','')}|{rec.get('date')}|{rec.get('description','').lower().strip()}|{rec.get('debit') or 0:.2f}|{rec.get('credit') or 0:.2f}"
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def upsert_staging(cur, recs: List[Dict[str, Any]]):
    sql = (
        """
        INSERT INTO staging_banking_pdf_transactions (
            source_file, page, line_no, bank, account_number, branch, 
            statement_period_start, statement_period_end, transaction_date, description, 
            debit_amount, credit_amount, balance, source_hash
        ) VALUES (
            %(source_file)s, %(page)s, %(line_no)s, %(bank)s, %(account)s, %(branch)s,
            %(statement_start)s, %(statement_end)s, %(date)s, %(description)s,
            %(debit)s, %(credit)s, %(balance)s, %(source_hash)s
        )
        ON CONFLICT (source_hash) DO NOTHING
        """
    )
    for r in recs:
        r['source_hash'] = compute_hash(r)
        cur.execute(sql, r)


def compare_against_db(cur) -> Dict[str, Any]:
    # For staged 2012 rows, look for matches in banking_transactions by date + amount
    cur.execute(
        """
        SELECT id, source_file, transaction_date, description, debit_amount, credit_amount
        FROM staging_banking_pdf_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        """
    )
    staged = cur.fetchall()
    report = {
        'total_staged': len(staged),
        'matched': 0,
        'missing': 0,
        'by_file': {}
    }
    unmatched_rows = []
    for row in staged:
        date = row['transaction_date']
        debit = row['debit_amount'] or Decimal('0.00')
        credit = row['credit_amount'] or Decimal('0.00')
        cur.execute(
            """
            SELECT transaction_id
            FROM banking_transactions
            WHERE transaction_date = %s
              AND (
                    (debit_amount IS NOT NULL AND %s > 0 AND debit_amount BETWEEN %s - 0.02 AND %s + 0.02)
                 OR (credit_amount IS NOT NULL AND %s > 0 AND credit_amount BETWEEN %s - 0.02 AND %s + 0.02)
              )
            LIMIT 1
            """,
            (date, debit, debit, debit, credit, credit, credit)
        )
        match = cur.fetchone()
        file_key = row['source_file']
        if file_key not in report['by_file']:
            report['by_file'][file_key] = {'staged': 0, 'matched': 0, 'missing': 0}
        report['by_file'][file_key]['staged'] += 1
        if match:
            report['matched'] += 1
            report['by_file'][file_key]['matched'] += 1
        else:
            report['missing'] += 1
            report['by_file'][file_key]['missing'] += 1
            unmatched_rows.append(row)
    report['unmatched_rows'] = unmatched_rows
    return report


def main():
    # Parse all target PDFs
    all_rows: List[Dict[str, Any]] = []
    for path in PDF_FILES:
        if not os.path.exists(path):
            print(f"[WARN]  Missing file: {path}")
            continue
        rows = parse_cibc_or_scotia_transactions(path)
        print(f"📄 {os.path.basename(path)} -> extracted {len(rows)} transactions")
        all_rows.extend(rows)
    if not all_rows:
        print("[FAIL] No transactions extracted from provided PDFs")
        return

    # Stage into DB and compare
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    ensure_staging_table(cur)
    # Clear previous staging for the same source files to avoid stale counts
    try:
        src_names = tuple({os.path.basename(r['source_file']) for r in all_rows})
        if len(src_names) == 1:
            cur.execute("DELETE FROM staging_banking_pdf_transactions WHERE source_file = %s", (next(iter(src_names)),))
        else:
            cur.execute("DELETE FROM staging_banking_pdf_transactions WHERE source_file = ANY(%s)", (list(src_names),))
    except Exception:
        # If delete with ANY fails (older psycopg2), fall back to deleting per file
        for name in {os.path.basename(r['source_file']) for r in all_rows}:
            cur.execute("DELETE FROM staging_banking_pdf_transactions WHERE source_file = %s", (name,))
    upsert_staging(cur, all_rows)
    conn.commit()

    report = compare_against_db(cur)

    # Emit report summary
    print("\n" + "="*100)
    print("PDF BANK STATEMENTS -> STAGING vs DATABASE")
    print("="*100)
    print(f"Total staged: {report['total_staged']}")
    print(f"Matched in DB: {report['matched']}")
    print(f"Missing in DB: {report['missing']}")
    print("\nBy file:")
    for fname, stats in report['by_file'].items():
        print(f" - {fname}: staged={stats['staged']}, matched={stats['matched']}, missing={stats['missing']}")

    # Write unmatched sample to CSV for audit
    os.makedirs('reports', exist_ok=True)
    out_csv = os.path.join('reports', 'pdf_vs_db_2012_unmatched.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['source_file', 'transaction_date', 'description', 'debit_amount', 'credit_amount'])
        for r in report.get('unmatched_rows', [])[:1000]:  # cap to 1000 rows
            writer.writerow([
                r.get('source_file'), r.get('transaction_date'), r.get('description'),
                r.get('debit_amount'), r.get('credit_amount')
            ])
    print(f"\n📄 Unmatched sample written to {out_csv}")

    cur.close(); conn.close()
    print("\n[OK] Staging and comparison complete.")


if __name__ == '__main__':
    main()
