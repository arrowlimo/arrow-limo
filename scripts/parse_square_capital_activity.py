#!/usr/bin/env python3
"""
Parse Square Capital Activity CSV exported from Square Dashboard.

Expected file example:
  L:\limo\Square reports\P-55QV76-Square_Capital_Activity_20251108.csv

We identify:
- Loan disbursements (funding)
- Daily repayments (deductions from payouts)
- Adjustments / refunds (if any)
- Fees (if present)

Output:
- Console summary
- CSV summary: reports/square_capital_activity_summary.csv
- Detailed normalized CSV: reports/square_capital_activity_detailed.csv
- Optional DB insert (use --write to apply)

Safety: --write required to insert rows; otherwise DRY RUN.
"""
import os
import sys
import csv
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

INPUT_DEFAULT = r'L:\limo\Square reports\P-55QV76-Square_Capital_Activity_20251108.csv'
OUTPUT_DIR = r'l:\limo\reports'

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

# Heuristics for columns (Square export variations)
COLUMN_MAP_CANDIDATES = {
    'date': ['Date','date','Transaction Date','Activity Date','Payment Date','Posted Date'],
    'description': ['Description','description','Activity Description','Details','Note','Notes','Memo'],
    'amount': ['Amount','amount','Activity Amount','Loan Amount','Payment Amount','Change','Change Amount','Net Change'],
    'loan_id': ['Loan ID','loan id','Loan Number','Capital Loan ID','Loan','Capital Loan'],
    'type': ['Type','Activity Type','Entry Type','Capital Type','Event Type'],
    'balance': ['Balance','Remaining Balance','Outstanding Balance','Loan Balance','New Balance','Ending Balance']
}

NUMERIC_STRIP = ['$',',']

def normalize_amount(raw):
    if raw is None: return Decimal('0')
    s = str(raw).strip()
    if not s: return Decimal('0')
    for ch in NUMERIC_STRIP: s = s.replace(ch,'')
    # Handle parentheses for negatives
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal('0')

def detect_columns(header):
    lower = [h.lower().strip() for h in header]
    mapping = {}
    # Exact matches first
    for target, candidates in COLUMN_MAP_CANDIDATES.items():
        for cand in candidates:
            cand_l = cand.lower()
            for i,h in enumerate(lower):
                if h == cand_l:
                    mapping[target] = header[i]
                    break
            if target in mapping: break
    # Fuzzy contains fallback
    for target, candidates in COLUMN_MAP_CANDIDATES.items():
        if target in mapping: continue
        for i,h in enumerate(lower):
            if any(cand.lower() in h for cand in candidates):
                mapping[target] = header[i]
                break
    return mapping

def classify_row(desc, type_val, amount):
    d = (desc or '').lower()
    t = (type_val or '').lower()
    amt = amount
    # Funding / disbursement
    if any(k in d for k in ['disbursement','funded','advance','loan deposit','capital funding']) or 'fund' in t:
        return 'FUNDING'
    # Repayment detection
    if any(k in d for k in ['repayment','daily payment','automatic payment','payment deducted','deduction','remitted']) or 'payment' in t or 'repay' in t:
        if amt < 0:
            return 'REPAYMENT'
        # Sometimes repayment shown as positive amount with separate sign column; fallback
        return 'REPAYMENT'
    # Refunds explicitly
    if 'loan payment refund' in d or ('refund' in d and 'payment' in d):
        return 'REFUND'
    # Fees
    if 'fee' in d or 'fee' in t:
        return 'FEE'
    # Balance update lines
    if 'balance' in d and amt == 0:
        return 'BALANCE_NOTE'
    return 'OTHER'

def _sniff_reader(fpath):
    """Return (reader, header, dialect) using Sniffer, tolerant to delimiters , ; \t |"""
    fh = open(fpath,'r',encoding='utf-8-sig',newline='')
    sample = fh.read(8192)
    fh.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        class _D: delimiter=','
        dialect = _D()
    reader = csv.reader(fh, dialect)
    header = next(reader)
    return fh, reader, header, dialect

def parse_file(path):
    if not os.path.exists(path):
        print(f'[FAIL] File not found: {path}')
        sys.exit(1)
    rows = []
    # Build reader with sniffed dialect
    fh, reader, header, dialect = _sniff_reader(path)
    print(f"\nHeader columns detected ({dialect.delimiter!r} delimited):")
    try:
        print('  ' + ' | '.join(header))
    except Exception:
        print(f'  [Header contained non-printable values: {len(header)} columns]')
    mapping = detect_columns(header)
    # Debug: show mapping
    if not mapping:
        print('⚠ No direct column mapping found. Falling back to unstructured parsing.')
    else:
        print('Mapped columns: ' + ', '.join([f"{k}->{v}" for k,v in mapping.items()]))
    # Build index map for speed
    idx = {col: header.index(src) for col,src in mapping.items()}

    def parse_date_value(val):
        if val is None:
            return None
        raw = str(val).strip()
        for fmt in [
            '%Y-%m-%d','%m/%d/%Y','%d-%m-%Y','%b %d, %Y','%d %b %Y',
            '%y-%m-%d','%y/%m/%d','%m-%d-%y','%d-%b-%y'
        ]:
            try:
                return datetime.strptime(raw, fmt).date()
            except Exception:
                continue
        return None

    import re
    money_re = re.compile(r"\(?\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\)?")
    loan_re = re.compile(r"CAP\d{4}", re.IGNORECASE)

    line_no = 0
    for line in reader:
        line_no += 1
        if not any(line):
            continue
        # Structured path if we have essential mapping
        if 'date' in mapping and 'amount' in mapping:
            data = {}
            for target,src in mapping.items():
                try:
                    data[target] = line[idx[target]].strip()
                except Exception:
                    data[target] = ''
            amount = normalize_amount(data.get('amount'))
            balance_amt = normalize_amount(data.get('balance')) if data.get('balance') else None
            parsed_date = parse_date_value(data.get('date'))
            if not parsed_date:
                # try any cell that looks like a date
                for cell in line:
                    parsed_date = parse_date_value(cell)
                    if parsed_date:
                        break
            if not parsed_date:
                continue
            category = classify_row(data.get('description'), data.get('type'), amount)
            loan_id = data.get('loan_id') or ''
            if not loan_id:
                # try regex from description
                m = loan_re.search((data.get('description') or '') + ' ' + (data.get('type') or ''))
                if m:
                    loan_id = m.group(0).upper()
            rows.append({
                'date': parsed_date,
                'loan_id': loan_id,
                'description': data.get('description') or '|'.join(line),
                'type_raw': data.get('type'),
                'category': category,
                'amount': amount,
                'balance': balance_amt,
            })
            continue

        # Unstructured fallback: scan cells
        joined = ' | '.join([c.strip() for c in line])
        # Date: first parsable
        parsed_date = None
        for cell in line:
            parsed_date = parse_date_value(cell)
            if parsed_date:
                break
        if not parsed_date:
            continue
        # Loan id
        mloan = loan_re.search(joined)
        loan_id = mloan.group(0).upper() if mloan else ''
        # Amount: prefer the right-most money token (often change amount)
        moneys = money_re.findall(joined)
        amount = Decimal('0')
        if moneys:
            amount = normalize_amount(moneys[-1])
        # Type/desc
        desc = joined
        # Category by keywords
        category = classify_row(desc, '', amount)
        rows.append({
            'date': parsed_date,
            'loan_id': loan_id,
            'description': desc,
            'type_raw': '',
            'category': category,
            'amount': amount,
            'balance': None,
        })
    fh.close()
    return rows

def summarize(rows):
    funding = [r for r in rows if r['category']=='FUNDING']
    repayments = [r for r in rows if r['category']=='REPAYMENT']
    fees = [r for r in rows if r['category']=='FEE']
    other = [r for r in rows if r['category'] not in ['FUNDING','REPAYMENT','FEE']]
    total_funded = sum(r['amount'] for r in funding)
    total_repaid = sum(abs(r['amount']) for r in repayments)  # repayments might be negative
    total_fees = sum(abs(r['amount']) for r in fees)
    # Per-loan aggregation
    per_loan = {}
    for r in rows:
        lid = r['loan_id'] or 'UNKNOWN'
        if lid not in per_loan:
            per_loan[lid] = {'funded':Decimal('0'),'repaid':Decimal('0'),'fees':Decimal('0'),'first':r['date'],'last':r['date']}
        if r['category']=='FUNDING':
            per_loan[lid]['funded'] += r['amount']
        elif r['category']=='REPAYMENT':
            per_loan[lid]['repaid'] += abs(r['amount'])
        elif r['category']=='FEE':
            per_loan[lid]['fees'] += abs(r['amount'])
        # Date span
        if r['date'] < per_loan[lid]['first']:
            per_loan[lid]['first'] = r['date']
        if r['date'] > per_loan[lid]['last']:
            per_loan[lid]['last'] = r['date']
    return {
        'funding': funding,
        'repayments': repayments,
        'fees': fees,
        'other': other,
        'total_funded': total_funded,
        'total_repaid': total_repaid,
        'total_fees': total_fees,
        'per_loan': per_loan,
        'row_count': len(rows)
    }

def write_csv(rows, summary):
    detailed_path = os.path.join(OUTPUT_DIR, 'square_capital_activity_detailed.csv')
    with open(detailed_path,'w',encoding='utf-8',newline='') as f:
        w = csv.writer(f)
        w.writerow(['date','loan_id','description','type_raw','category','amount','balance'])
        for r in rows:
            w.writerow([r['date'], r['loan_id'], r['description'], r['type_raw'], r['category'], f"{r['amount']}", f"{r['balance'] if r['balance'] is not None else ''}"])
    summary_path = os.path.join(OUTPUT_DIR, 'square_capital_activity_summary.csv')
    with open(summary_path,'w',encoding='utf-8',newline='') as f:
        w = csv.writer(f)
        w.writerow(['loan_id','funded','repaid','fees','first_date','last_date','outstanding_est'])
        for lid,data in summary['per_loan'].items():
            outstanding = data['funded'] - data['repaid'] - data['fees']
            w.writerow([lid, f"{data['funded']}", f"{data['repaid']}", f"{data['fees']}", data['first'], data['last'], f"{outstanding}"])
    return detailed_path, summary_path

def insert_db(rows, summary, dry_run=True):
    conn = get_conn(); cur = conn.cursor()
    # Ensure tables exist
    cur.execute('''CREATE TABLE IF NOT EXISTS square_capital_activity (
        id SERIAL PRIMARY KEY,
        activity_date DATE NOT NULL,
        loan_id VARCHAR(50),
        description TEXT,
        category VARCHAR(30),
        raw_type TEXT,
        amount NUMERIC(14,2),
        balance NUMERIC(14,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    inserted = 0
    for r in rows:
        # Skip if duplicate (same date, description, amount)
        cur.execute("SELECT 1 FROM square_capital_activity WHERE activity_date=%s AND description=%s AND amount=%s", (r['date'], r['description'], r['amount']))
        if cur.fetchone():
            continue
        cur.execute("INSERT INTO square_capital_activity (activity_date, loan_id, description, category, raw_type, amount, balance) VALUES (%s,%s,%s,%s,%s,%s,%s)", (r['date'], r['loan_id'], r['description'], r['category'], r['type_raw'], r['amount'], r['balance']))
        inserted += 1
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    cur.close(); conn.close()
    return inserted

def main():
    ap = argparse.ArgumentParser(description='Parse Square Capital Activity CSV')
    ap.add_argument('--path', default=INPUT_DEFAULT, help='Path to Square Capital activity CSV')
    ap.add_argument('--write', action='store_true', help='Persist parsed activity to database')
    args = ap.parse_args()

    print('='*100)
    print('PARSING SQUARE CAPITAL ACTIVITY FILE')
    print('='*100)
    print(f'Input file: {args.path}')

    rows = parse_file(args.path)
    summary = summarize(rows)

    print(f"\nRows parsed: {summary['row_count']}")
    print(f"Funding rows: {len(summary['funding'])} | Total funded: ${summary['total_funded']:,}")
    print(f"Repayment rows: {len(summary['repayments'])} | Total repaid: ${summary['total_repaid']:,}")
    print(f"Fee rows: {len(summary['fees'])} | Total fees: ${summary['total_fees']:,}")

    print('\nPer-loan breakdown:')
    for lid,data in summary['per_loan'].items():
        outstanding = data['funded'] - data['repaid'] - data['fees']
        print(f"  {lid}: funded ${data['funded']:,} repaid ${data['repaid']:,} fees ${data['fees']:,} outstanding_est ${outstanding:,} period {data['first']}→{data['last']}")

    detailed_path, summary_path = write_csv(rows, summary)
    print(f"\n✓ Detailed CSV written: {detailed_path}")
    print(f"✓ Summary CSV written: {summary_path}")

    inserted = insert_db(rows, summary, dry_run=not args.write)
    if args.write:
        print(f"\n✓ Inserted {inserted} new rows into square_capital_activity")
    else:
        print(f"\nDRY RUN: Would insert {inserted} new rows. Use --write to apply.")

    print('\nDone.')

if __name__ == '__main__':
    main()
