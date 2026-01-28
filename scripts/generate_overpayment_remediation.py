#!/usr/bin/env python3
"""Generate remediation proposal CSVs from classification_overpaid_charters.csv.

Outputs (all in current directory):
  duplicates_deletions.csv              - Reserves classified as DUPLICATE_PAYMENT
  zero_due_duplicates.csv               - Reserves classified as ZERO_DUE_DUPLICATE
  cancelled_deposit_credits.csv         - Reserves classified as CANCELLED_DEPOSIT (credit_amount = excess)
  multi_charter_prepay_credits.csv      - Reserves classified as MULTI_CHARTER_PREPAY (credit_amount = excess)
  manual_review.csv                     - Reserves needing manual assessment

Does NOT modify database.
"""
import csv
from pathlib import Path

CLASS_FILE = Path('classification_overpaid_charters.csv')

def load_rows():
    if not CLASS_FILE.exists():
        raise SystemExit('classification_overpaid_charters.csv not found. Run classify_overpaid_charters.py first.')
    rows = []
    with CLASS_FILE.open('r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows

def write_csv(name, header, rows):
    with open(name, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def main():
    rows = load_rows()
    dup_del = []
    zero_dup = []
    cancel_credit = []
    multi_credit = []
    manual = []

    for row in rows:
        cat = row['proposed_category']
        reserve = row['reserve_number']
        excess = float(row['excess'])
        client = row['client_name']
        cancelled = row['cancelled']
        if cat == 'DUPLICATE_PAYMENT':
            dup_del.append([reserve, client, f"{excess:.2f}"])
        elif cat == 'ZERO_DUE_DUPLICATE':
            zero_dup.append([reserve, client, f"{excess:.2f}"])
        elif cat == 'CANCELLED_DEPOSIT':
            cancel_credit.append([reserve, client, f"{excess:.2f}", cancelled])
        elif cat == 'MULTI_CHARTER_PREPAY':
            multi_credit.append([reserve, client, f"{excess:.2f}"])
        elif cat == 'NEED_MANUAL':
            manual.append([reserve, client, f"{excess:.2f}", cancelled])
        # MISALIGNED_TOTAL_DUE not present in this run; could be handled similarly

    write_csv('duplicates_deletions.csv', ['reserve_number','client_name','excess'], dup_del)
    write_csv('zero_due_duplicates.csv', ['reserve_number','client_name','excess'], zero_dup)
    write_csv('cancelled_deposit_credits.csv', ['reserve_number','client_name','excess','cancelled'], cancel_credit)
    write_csv('multi_charter_prepay_credits.csv', ['reserve_number','client_name','excess'], multi_credit)
    write_csv('manual_review.csv', ['reserve_number','client_name','excess','cancelled'], manual)

    print('Remediation proposal files written:')
    for fn in ['duplicates_deletions.csv','zero_due_duplicates.csv','cancelled_deposit_credits.csv','multi_charter_prepay_credits.csv','manual_review.csv']:
        count = sum(1 for _ in open(fn, 'r', encoding='utf-8')) - 1
        print(f"  {fn}: {count} rows")

if __name__ == '__main__':
    main()
