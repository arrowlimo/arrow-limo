"""
Capture and de-duplicate pasted 2012 CIBC statement lines (July–December).

Purpose:
  You will paste raw statement lines (date, description, withdrawal, deposit, balance).
  This script parses each line, normalizes the date, extracts numeric amounts, and
  flags duplicates against:
    1. Previously captured lines (local CSV log)
    2. Existing rows in banking_transactions table (if matching date + amount + description)

Outputs:
  - data/jul_dec_2012_statement_capture.csv (appended on --write)
  - Console summary of new vs duplicate vs already in DB

Usage (PowerShell):
  # Dry-run paste (will NOT write file)
  @'
  Sep 05  ABM WITHDRAWAL  GAETZ AVE + 22ND ST 99512    160.00          207.18
  Sep 06  CREDIT MEMO 4017775 VISA                     214.50          447.81
  '@ | python -X utf8 scripts/capture_statement_lines_jul_dec_2012.py --dry-run

  # Apply (append new lines to capture file)
  @'
  Sep 05  ABM WITHDRAWAL  GAETZ AVE + 22ND ST 99512    160.00          207.18
  Sep 06  CREDIT MEMO 4017775 VISA                     214.50          447.81
  '@ | python -X utf8 scripts/capture_statement_lines_jul_dec_2012.py --write

Parameters:
  --write      Actually append new parsed entries to CSV file
  --dry-run    (default) Show what would be written without modifying files
  --file path  Read lines from a text file instead of STDIN
  --month-filter JUL, AUG, SEP, OCT, NOV, DEC (comma list) to restrict accepted months

Duplicate Logic:
  Local duplicate: same normalized date + description + withdrawal + deposit + balance
  DB duplicate: banking_transactions row where (transaction_date, amount, description) matches.

Note:
  We only have one amount column in banking_transactions (debit/credit separation). We attempt match
  by comparing either debit_amount or credit_amount to the parsed withdrawal/deposit.
"""
import sys, re, csv, argparse, hashlib, os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Tuple

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # Allow running without DB connectivity

MONTH_MAP = {
    'JUN': '06', 'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
}

CAPTURE_PATH = os.path.join('data', 'jul_dec_2012_statement_capture.csv')
os.makedirs('data', exist_ok=True)

LINE_PATTERN = re.compile(r"^(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+(?P<rest>.+)$")
OPENING_BALANCE_PATTERN = re.compile(r"^Opening\s+balance\s+[/$]\s*([-+]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", re.IGNORECASE)
# Match amounts with or without commas, and handle negative balances
AMOUNT_PATTERN = re.compile(r"([-+]?\d{1,}(?:,\d{3})*(?:\.\d{2}))")

# Attempt to locate numeric tokens near end for withdrawal/deposit/balance inference
# Heuristic: Last 3 numeric tokens = [maybe withdrawal/deposit/balance] (some lines omit deposit or withdrawal)


def parse_line(raw: str, month_context: str = 'JUL') -> Optional[Dict]:
    raw = raw.strip()
    if not raw:
        return None
    
    # Check for opening balance line
    ob_match = OPENING_BALANCE_PATTERN.match(raw)
    if ob_match:
        amount_str = ob_match.group(1).replace(',', '')
        balance = Decimal(amount_str)
        return {
            'raw': raw,
            'date': f'2012-{MONTH_MAP.get(month_context.upper(), "07")}-01',  # First day of month
            'description': 'Opening Balance',
            'withdrawal': None,
            'deposit': None,
            'balance': balance,
            'is_opening_balance': True
        }
    
    m = LINE_PATTERN.match(raw)
    if not m:
        return None
    month_txt = m.group('month').upper()
    if month_txt not in MONTH_MAP:
        return None
    day = int(m.group('day'))
    rest = m.group('rest').rstrip()
    date = f"2012-{MONTH_MAP[month_txt]}-{day:02d}"
    # Extract amounts
    amounts = AMOUNT_PATTERN.findall(rest)
    # Clean amounts -> Decimal
    clean_amounts = [Decimal(a.replace(',', '')) for a in amounts]
    withdrawal = None
    deposit = None
    balance = None
    # Heuristic assignment
    if len(clean_amounts) >= 3:
        # Try last three as w,d,b or w,b or d,b
        b = clean_amounts[-1]
        second_last = clean_amounts[-2]
        third_last = clean_amounts[-3]
        balance = b
        # Decide if pattern w,d,b or w,b
        # If second_last < 0 or appears earlier separated from rest treat as deposit
        # We'll assume: if two preceding numbers, larger goes to withdrawal if description contains WITHDRAWAL/PURCHASE/CHEQUE
        desc_upper = rest.upper()
        if 'WITHDRAW' in desc_upper or 'PURCHASE' in desc_upper or 'CHEQUE' in desc_upper or 'DEBIT MEMO' in desc_upper or 'NSF' in desc_upper or 'FEE' in desc_upper:
            withdrawal = third_last
            if 'CREDIT' in desc_upper or 'DEPOSIT' in desc_upper or 'MEMO' in desc_upper:
                deposit = second_last
            else:
                # Might be w,b pattern so second_last actually withdrawal and third_last part of description amount -> adjust
                # Fallback: treat second_last as withdrawal, ignore third_last
                withdrawal = second_last
        else:
            # Likely deposit scenario
            deposit = second_last
            if len(clean_amounts) >= 4:
                withdrawal = third_last
    elif len(clean_amounts) == 2:
        balance = clean_amounts[-1]
        # Single amount before balance -> treat as either withdrawal or deposit based on keywords
        desc_upper = rest.upper()
        amt = clean_amounts[0]
        # Withdrawals (money leaving account)
        withdrawal_keywords = ['WITHDRAW', 'PURCHASE', 'DEBIT MEMO', 'FEE', 'NSF', 'CHEQUE', 
                               'INSURANCE', 'PAYMENT', 'TRANSFER', 'PAD', 'PRE-AUTH', 'S/C',
                               'SERVICE CHARGE', 'RETURNED CHQ S/C']
        # Deposits (money coming in)
        deposit_keywords = ['DEPOSIT', 'CREDIT MEMO', 'CORRECTION', 'REFUND', 'REVERSAL']
        
        # Check for deposit keywords first (more specific)
        if any(k in desc_upper for k in deposit_keywords):
            deposit = amt
        elif any(k in desc_upper for k in withdrawal_keywords):
            withdrawal = amt
        else:
            # Default: if balance decreased, it's a withdrawal; if increased, it's a deposit
            # This requires knowing previous balance, so default to withdrawal for safety
            withdrawal = amt
    elif len(clean_amounts) == 1:
        balance = clean_amounts[0]
    description = rest
    return {
        'raw': raw,
        'date': date,
        'description': description,
        'withdrawal': withdrawal,
        'deposit': deposit,
        'balance': balance,
        'is_opening_balance': False
    }


def load_existing_local() -> Dict[str, Dict]:
    existing = {}
    if not os.path.exists(CAPTURE_PATH):
        return existing
    with open(CAPTURE_PATH, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row['hash']
            existing[key] = row
    return existing


def connect_db():
    if psycopg2 is None:
        return None
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            dbname=os.environ.get('DB_NAME', 'almsdata'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '***REDACTED***')
        )
        return conn
    except Exception:
        return None


def check_db_duplicate(conn, txn: Dict) -> bool:
    if conn is None:
        return False
    if txn['withdrawal'] is None and txn['deposit'] is None:
        return False
    amount = txn['withdrawal'] or txn['deposit']
    if amount is None:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM banking_transactions
            WHERE transaction_date = %s
              AND description ILIKE %s
              AND (
                    (debit_amount = %s) OR
                    (credit_amount = %s)
                  )
            LIMIT 1
        """, (txn['date'], '%' + txn['description'][:40] + '%', amount, amount))
        row = cur.fetchone()
        cur.close()
        return row is not None
    except Exception:
        return False


def make_hash(txn: Dict) -> str:
    h = hashlib.sha256()
    parts = [txn['date'], txn['description'], str(txn['withdrawal']), str(txn['deposit']), str(txn['balance'])]
    h.update('|'.join(parts).encode('utf-8'))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='Capture and de-duplicate 2012 Jul-Dec statement lines')
    ap.add_argument('--write', action='store_true', help='Append new lines to capture CSV')
    ap.add_argument('--dry-run', action='store_true', help='Perform dry run (default if neither flag given)')
    ap.add_argument('--file', type=str, help='Input text file (if omitted, reads STDIN)')
    ap.add_argument('--month-filter', type=str, help='Comma list of months to accept (e.g., JUL,SEP,DEC)')
    ap.add_argument('--show-all', action='store_true', help='Print all parsed lines with duplicate flags')
    args = ap.parse_args()

    month_filter = None
    if args.month_filter:
        month_filter = {m.strip().upper() for m in args.month_filter.split(',') if m.strip()}

    # Read input lines
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            raw_lines = f.readlines()
    else:
        if sys.stdin.isatty():
            print('Paste lines then Ctrl-D (Linux/macOS) or Ctrl-Z Enter (Windows) to end input:')
        raw_lines = sys.stdin.read().splitlines()

    existing_local = load_existing_local()
    conn = connect_db()

    parsed: List[Dict] = []
    current_month = 'JUL'  # Default starting month
    for line in raw_lines:
        # Try to detect month from line for context
        month_match = re.match(r'^([A-Za-z]{3})', line.strip())
        if month_match and month_match.group(1).upper() in MONTH_MAP:
            current_month = month_match.group(1).upper()
        
        txn = parse_line(line, current_month)
        if not txn:
            continue
        # Month filter
        m_abbrev = line[:3].upper()
        if month_filter and m_abbrev not in month_filter and not txn.get('is_opening_balance'):
            continue
        txn_hash = make_hash(txn)
        txn['hash'] = txn_hash
        txn['local_duplicate'] = txn_hash in existing_local
        txn['db_duplicate'] = check_db_duplicate(conn, txn)
        parsed.append(txn)

    # BALANCE VALIDATION: Check running total against PDF balance
    balance_errors = []
    if parsed:
        # Find opening balance or start from first transaction
        running_balance = None
        start_index = 0
        
        if parsed[0].get('is_opening_balance'):
            running_balance = parsed[0]['balance']
            start_index = 1
        else:
            # If no opening balance, derive it from first transaction
            running_balance = parsed[0]['balance']
            if parsed[0]['withdrawal']:
                running_balance = (running_balance or Decimal('0')) + (parsed[0]['withdrawal'] or Decimal('0'))
            if parsed[0]['deposit']:
                running_balance = (running_balance or Decimal('0')) - (parsed[0]['deposit'] or Decimal('0'))
        
        for i in range(start_index, len(parsed)):
            txn = parsed[i]
            # Calculate expected balance after this transaction
            expected_balance = running_balance
            if txn['withdrawal']:
                expected_balance -= txn['withdrawal']
            if txn['deposit']:
                expected_balance += txn['deposit']
            
            # Compare with PDF balance
            if txn['balance'] is not None:
                diff = abs(expected_balance - txn['balance'])
                if diff > Decimal('0.01'):  # Allow 1 cent tolerance for rounding
                    balance_errors.append({
                        'line': i + 1,
                        'date': txn['date'],
                        'description': txn['description'],
                        'expected': expected_balance,
                        'pdf_balance': txn['balance'],
                        'difference': expected_balance - txn['balance']
                    })
                running_balance = txn['balance']  # Use PDF balance to continue (handles any adjustments)
            else:
                running_balance = expected_balance

    new_entries = [p for p in parsed if not p['local_duplicate']]
    local_dupes = [p for p in parsed if p['local_duplicate']]
    db_dupes = [p for p in parsed if p['db_duplicate']]

    print('\nCapture Summary (Jul-Dec 2012)')
    print('--------------------------------')
    print(f'Total parsed lines:        {len(parsed)}')
    print(f'New (non-local) entries:   {len(new_entries)}')
    print(f'Local duplicates skipped:  {len(local_dupes)}')
    print(f'DB duplicates flagged:     {len(db_dupes)}')
    
    # Report balance validation errors
    if balance_errors:
        print(f'\n[WARN]  BALANCE MISMATCH ERRORS: {len(balance_errors)}')
        print('='*100)
        for err in balance_errors:
            print(f"Line {err['line']}: {err['date']} | {err['description'][:50]}")
            print(f"  Expected: ${err['expected']:,.2f} | PDF shows: ${err['pdf_balance']:,.2f} | Difference: ${err['difference']:,.2f}")
        print('='*100)
        print('[FAIL] VALIDATION FAILED - Running balance does not match PDF!')
        print('   Review transaction amounts or check for missing/extra lines.')
        if args.write:
            print('   --write flag IGNORED due to balance errors.')
            return  # Don't write if validation fails
    else:
        print('[OK] Balance validation PASSED - Running total matches PDF balance')

    if new_entries:
        print('\nNew Entries Preview:')
        for p in new_entries[:15]:
            print(f"  {p['date']} | W={p['withdrawal']} D={p['deposit']} B={p['balance']} | {p['description'][:60]}")
        if len(new_entries) > 15:
            print(f'  ... ({len(new_entries)-15} more)')

    if db_dupes:
        print('\nLikely Already in DB (sample):')
        for p in db_dupes[:10]:
            print(f"  {p['date']} | Amt={(p['withdrawal'] or p['deposit'])} | {p['description'][:60]}")
    if local_dupes:
        print('\nLocal Duplicates (sample):')
        for p in local_dupes[:10]:
            print(f"  {p['date']} | W={p['withdrawal']} D={p['deposit']} B={p['balance']} | {p['description'][:60]}")

    if args.write and new_entries:
        write_header = not os.path.exists(CAPTURE_PATH)
        with open(CAPTURE_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(['date','description','withdrawal','deposit','balance','hash'])
            for p in new_entries:
                writer.writerow([p['date'], p['description'], p['withdrawal'], p['deposit'], p['balance'], p['hash']])
        print(f'\nAppended {len(new_entries)} new entries to {CAPTURE_PATH}')
    else:
        print('\nDry run (no file changes). Use --write to persist.')

    if args.show_all and parsed:
        print('\nAll Parsed Lines:')
        print('date       | withdraw   | deposit    | balance    | local_dup | db_dup | description')
        print('-'*110)
        for p in parsed:
            w = f"{p['withdrawal']:.2f}" if p['withdrawal'] is not None else ''
            d = f"{p['deposit']:.2f}" if p['deposit'] is not None else ''
            b = f"{p['balance']:.2f}" if p['balance'] is not None else ''
            print(f"{p['date']} | {w:>10} | {d:>10} | {b:>10} | {str(p['local_duplicate']):>9} | {str(p['db_duplicate']):>6} | {p['description'][:70]}")

    if conn:
        conn.close()

if __name__ == '__main__':
    main()
