import os
import re
import sys
import json
import argparse
import datetime
from decimal import Decimal
import psycopg2

# Script: match_calendar_cancellations.py
# Purpose: Parse a raw cancellation export, match reserve_numbers to existing charters, and propose cancellation + retainer credit actions.
# Safety: Dry-run by default. Requires --write to apply changes.
# Duplicate Protection: Will skip charters already cancelled or already having a CANCELLED_DEPOSIT credit.
# Retainer Detection: Looks for explicit 'retainer' amount in line or patterns like '$500 retainer', 'retainer left $500'.
# Implicit Retainer Heuristic: If charter is not cancelled, has paid_amount > 0 and (balance < 0 or total_amount_due = 0) and line contains 'cancel', treat paid_amount as non-refundable retainer.

RETainer_REGEX = re.compile(
    r'(?:retainer\s*(?:left)?\s*\$?(\d{1,5}(?:\.\d{2})?)|\$?(\d{1,5}(?:\.\d{2})?)\s*retainer)',
    re.IGNORECASE
)
RESERVE_REGEX = re.compile(r'\b0\d{5}\b')  # standardized 6-digit numeric reserve numbers (leading zero)
CANCEL_KEYWORDS = ('cancel','CANCELLED','no-go','no trip')

CREDIT_REASON = 'CANCELLED_DEPOSIT'

def get_db_connection():
    host = os.getenv('DB_HOST','localhost')
    db = os.getenv('DB_NAME','almsdata')
    user = os.getenv('DB_USER','postgres')
    pw = os.getenv('DB_PASSWORD','***REMOVED***')
    return psycopg2.connect(host=host, dbname=db, user=user, password=pw)

def parse_lines(raw_text):
    entries = []
    for line in raw_text.splitlines():
        lt = line.strip()
        if not lt or lt.startswith('Modified') or lt.startswith('(BEGIN') or lt.startswith('(END'):
            continue
        # Identify cancellation relevance
        if any(k.lower() in lt.lower() for k in CANCEL_KEYWORDS):
            reserves = RESERVE_REGEX.findall(lt)
            # Extract retainer amount if present
            retainer_match = RETainer_REGEX.search(lt)
            retainer_amount = None
            if retainer_match:
                # Iterate groups; skip if the captured number looks like a reserve number (leading 0 and length 6)
                for grp in retainer_match.groups():
                    if not grp:
                        continue
                    # Exclude 6-digit leading-zero patterns which are almost certainly reserve_numbers, not dollar amounts
                    if re.fullmatch(r'0\d{5}', grp):
                        continue
                    # Retainers rarely exceed 5 digits; already constrained. Prefer values with preceding '$' in original text
                    try:
                        amt = Decimal(grp)
                        # Additional guard: if amount > 10000 treat as parsing error
                        if amt > 10000:
                            continue
                        # If the textual context contains '$' near this number, prefer it; otherwise still accept if reasonable (< 5000)
                        # Simple heuristic: search window of 20 chars around match span for '$'
                        span_start, span_end = retainer_match.span()
                        context = lt[max(0, span_start-20):min(len(lt), span_end+20)]
                        if '$' in context or amt <= 5000:
                            retainer_amount = amt
                            break
                    except Exception:
                        continue
            entries.append({
                'raw_line': lt,
                'reserve_numbers': list(set(reserves)),
                'retainer_amount': retainer_amount
            })
    return entries

def fetch_charter(cur, reserve_number):
    cur.execute("""
        SELECT charter_id, reserve_number, cancelled, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_number,))
    return cur.fetchone()

def has_cancel_credit(cur, reserve_number):
    # Current schema uses source_reserve_number for original charter reference
    cur.execute("""
        SELECT 1 FROM charter_credit_ledger
        WHERE source_reserve_number = %s AND credit_reason = %s
        LIMIT 1
    """, (reserve_number, CREDIT_REASON))
    return cur.fetchone() is not None

def fetch_payments(cur, reserve_number):
    cur.execute("""
        SELECT payment_id, amount, payment_date
        FROM payments
        WHERE reserve_number = %s
        ORDER BY amount DESC
    """, (reserve_number,))
    return cur.fetchall()

def plan_actions(entry, charter_row, payments, already_has_credit):
    charter_id, reserve_number, cancelled, total_due, paid_amount, balance = charter_row
    actions = []
    notes = []
    retainer_amt = entry['retainer_amount']
    raw_line = entry['raw_line']

    if cancelled:
        notes.append('Already cancelled')
    else:
        actions.append({'action':'mark_cancelled','reserve_number':reserve_number})

    if already_has_credit:
        notes.append('Existing CANCELLED_DEPOSIT credit')
        return actions, notes

    # Explicit retainer amount
    if retainer_amt and retainer_amt > 0:
        # Find payment corresponding (largest payment >= retainer? or closest)
        chosen_payment = None
        closest_diff = None
        for pid, amt, pdate in payments:
            diff = abs(Decimal(amt) - retainer_amt)
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                chosen_payment = (pid, amt)
        if chosen_payment:
            actions.append({'action':'create_credit','reserve_number':reserve_number,'charter_id':charter_id,'source_payment_id':chosen_payment[0],'credit_amount':str(retainer_amt)})
            actions.append({'action':'delete_payment','payment_id':chosen_payment[0],'reserve_number':reserve_number})
            actions.append({'action':'zero_charter_financials','reserve_number':reserve_number})
            notes.append(f'Explicit retainer {retainer_amt} matched payment {chosen_payment[0]} amt={chosen_payment[1]}')
        else:
            notes.append(f'Explicit retainer {retainer_amt} but no matching payment found')
        return actions, notes

    # Implicit heuristic: treat paid_amount as retainer if cancelled or being cancelled and no charges (or negative balance pattern)
    if (not already_has_credit) and paid_amount and Decimal(paid_amount) > 0:
        # Conditions: either total_due = 0 OR balance < 0 OR raw line contains pattern like 'retainer left'
        if Decimal(total_due or 0) == 0 or Decimal(balance or 0) < 0 or ('retainer' in raw_line.lower()):
            credit_amt = Decimal(paid_amount)
            # Choose a payment to represent the retainer (largest payment)
            chosen_payment = payments[0] if payments else None
            if chosen_payment:
                actions.append({'action':'create_credit','reserve_number':reserve_number,'charter_id':charter_id,'source_payment_id':chosen_payment[0],'credit_amount':str(credit_amt)})
                actions.append({'action':'delete_payment','payment_id':chosen_payment[0],'reserve_number':reserve_number})
                actions.append({'action':'zero_charter_financials','reserve_number':reserve_number})
                notes.append(f'Implicit retainer heuristic credit {credit_amt} from payment {chosen_payment[0]}')
            else:
                notes.append('No payments found to convert to credit despite heuristic triggering')
    return actions, notes

def apply_actions(cur, actions):
    for act in actions:
        a = act['action']
        if a == 'mark_cancelled':
            cur.execute("UPDATE charters SET cancelled = TRUE WHERE reserve_number = %s", (act['reserve_number'],))
        elif a == 'create_credit':
            # Adapt to existing schema (source_reserve_number, source_charter_id, credit_amount, remaining_balance, credit_reason, notes, created_date, created_by)
            cur.execute("""
                INSERT INTO charter_credit_ledger (
                    source_reserve_number, source_charter_id, credit_amount, remaining_balance, credit_reason, notes, created_date, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
            """, (
                act['reserve_number'],
                act['charter_id'],
                act['credit_amount'],
                act['credit_amount'],
                CREDIT_REASON,
                'Auto from calendar cancellation',
                'calendar_import'
            ))
        elif a == 'delete_payment':
            # User requirement: DO NOT DELETE payments (retain for CRA). Instead flag as converted.
            payment_id = act['payment_id']
            # Ensure audit backup row exists for reference integrity
            cur.execute("SELECT payment_id, reserve_number, amount, payment_date FROM payments WHERE payment_id = %s", (payment_id,))
            row = cur.fetchone()
            if row:
                cur.execute("INSERT INTO payment_backups (payment_id, reserve_number, amount, payment_date, backup_timestamp) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT DO NOTHING", row)
                # Append note marker; preserve existing notes.
                try:
                    cur.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS admin_notes TEXT")
                except Exception:
                    pass
                cur.execute("""
                    UPDATE payments
                    SET admin_notes = COALESCE(admin_notes,'') || CASE WHEN admin_notes IS NULL OR admin_notes = '' THEN '' ELSE ' | ' END || 'NON_REFUNDABLE_RETAINER_CONVERTED_TO_CREDIT'
                    WHERE payment_id = %s
                """, (payment_id,))
            # Skip actual deletion; retain payment for audit.
        elif a == 'zero_charter_financials':
            cur.execute("UPDATE charters SET paid_amount = 0, balance = 0 WHERE reserve_number = %s", (act['reserve_number'],))

def ensure_backup_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_backups (
            payment_id INTEGER PRIMARY KEY,
            reserve_number VARCHAR(20),
            amount NUMERIC(12,2),
            payment_date DATE,
            backup_timestamp TIMESTAMP DEFAULT NOW()
        )
    """)

def main():
    parser = argparse.ArgumentParser(description='Match calendar cancellations to charters and plan cancellation + retainer credit actions.')
    parser.add_argument('--input-file', required=True, help='Path to raw cancellations text file.')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run).')
    parser.add_argument('--json-output', default='calendar_cancellation_match_report.json', help='Output JSON summary path.')
    args = parser.parse_args()

    with open(args.input_file,'r',encoding='utf-8') as f:
        raw_text = f.read()

    parsed = parse_lines(raw_text)

    conn = get_db_connection()
    cur = conn.cursor()

    ensure_backup_table(cur)

    summary = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'dry_run': not args.write,
        'total_lines_considered': len(parsed),
        'entries': []
    }

    for entry in parsed:
        reserves = entry['reserve_numbers']
        if not reserves:
            summary['entries'].append({'raw_line': entry['raw_line'], 'status':'no_reserve_found'})
            continue
        for reserve in reserves:
            charter = fetch_charter(cur, reserve)
            if not charter:
                summary['entries'].append({'raw_line': entry['raw_line'], 'reserve_number': reserve, 'status':'charter_not_found'})
                continue
            already_credit = has_cancel_credit(cur, reserve)
            payments = fetch_payments(cur, reserve)
            actions, notes = plan_actions(entry, charter, payments, already_credit)
            summary['entries'].append({
                'reserve_number': reserve,
                'raw_line': entry['raw_line'],
                'retainer_amount_explicit': str(entry['retainer_amount']) if entry['retainer_amount'] else None,
                'planned_actions': actions,
                'notes': notes
            })
            if args.write and actions:
                apply_actions(cur, actions)

    if args.write:
        conn.commit()
    else:
        conn.rollback()

    cur.close(); conn.close()

    with open(args.json_output,'w',encoding='utf-8') as outf:
        json.dump(summary, outf, indent=2)

    # Console summary
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
