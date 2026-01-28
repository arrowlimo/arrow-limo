#!/usr/bin/env python3
"""
Parse QuickBooks Reconciliation Detail and Generate Import Data
================================================================

Reads QB reconciliation text (from extract_qb_summary_pdf.py output) and produces:
1. CSV of all transactions for banking_transactions import
2. CSV of vendor expenses for receipts import (GST-included calculation)
3. Summary report of deposits, withdrawals, fees, transfers

Handles:
- Cheques/Payments (vendor expenses, fees, withdrawals)
- Deposits/Credits (revenue, journal entries)
- Bank fees, NSF charges
- Withdrawals (w/d, WD, cash)
- Transfers (TSF, transfer)
- General Journal entries

Output:
  exports/qb/2012/
    - qb_banking_transactions.csv (for banking_transactions import)
    - qb_receipts.csv (for receipts import with GST)
    - qb_summary.csv (totals by type)

Usage:
  python -X utf8 scripts/parse_qb_reconciliation.py \
    --input exports/qb/2012_qb_summary.txt \
    --year 2012 \
    --account 1000
"""
from __future__ import annotations

import os
import sys
import csv
import re
import argparse
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

# Transaction type patterns
WITHDRAWAL_PATTERNS = [r'\bw/d\b', r'\bwd\b', r'\bwithdrawal\b']
FEE_PATTERNS = [r'bank\s+charges?', r'service\s+fee', r'nsf', r'non-sufficient']
TRANSFER_PATTERNS = [r'\btsf\b', r'\btransfer\b']
JOURNAL_PATTERNS = [r'general\s+journal', r'journal\s+entry']

# Category mappings
VENDOR_CATEGORIES = {
    'insurance': ['ifs', 'jevco', 'cooperators', 'optimum west'],
    'fuel': ['shell', 'esso', 'husky', 'fas gas', 'petro', 'chevron'],
    'maintenance': ['parr', 'automotive', 'auto', 'repair', 'tire', 'choice auto'],
    'office': ['staples', 'prairie office', 'office supplies'],
    'merchant_fees': ['global merchant', 'square', 'amex', 'visa fees'],
    'utilities': ['centex', 'rogers', 'telus', 'sasktel'],
    'vehicle_registration': ['registries', 'registry'],
    'liquor': ['liquor', '67th street liquor'],
    'food': ['pizza', 'tim horton', 'taco', 'mongolian', 'ranch house'],
}


def categorize_vendor(vendor: str) -> str:
    vl = vendor.lower()
    for cat, keywords in VENDOR_CATEGORIES.items():
        if any(kw in vl for kw in keywords):
            return cat
    return 'general_expense'


def extract_gst_from_total(gross: Decimal, rate: Decimal = Decimal('0.05')) -> tuple[Decimal, Decimal]:
    """GST-included model: gst = gross * rate / (1 + rate), net = gross - gst"""
    gst = (gross * rate / (1 + rate)).quantize(Decimal('0.01'))
    net = (gross - gst).quantize(Decimal('0.01'))
    return gst, net


def parse_qb_line(line: str) -> dict | None:
    """
    Parse a QB reconciliation detail line.
    Format examples:
      Cheque 08/01/2012 dd Global Merchant Fees X -392.45 -392.45
      Bill Pmt -Cheque 08/10/2012 278 Parr's Automotive X -300.00 -2,333.83
      Deposit 08/31/2012 X 10,737.65 10,737.65
      General Journal 09/30/2012 80 Sales Sept 20... 1000 CIBC Bank 5,730.66
    """
    # Skip lines that don't look like transactions
    if not line.strip() or 'Beginning Balance' in line or 'Total' in line or 'Page ' in line:
        return None
    
    # Pattern: Type Date [Num] Name [X] Amount [Balance]
    # Very flexible regex to capture core fields
    match = re.search(
        r'(Cheque|Bill Pmt|Deposit|General Journal|Cheque Expense)\s+'
        r'(\d{2}/\d{2}/\d{4})\s+'
        r'(?:(dd|WD|w/d|Auto|TSF|\d+)\s+)?'  # optional num/type
        r'([A-Za-z0-9\s\.\'\-&]+?)\s+'  # vendor/name (non-greedy)
        r'(?:X\s+)?'  # optional cleared marker
        r'([-]?[\d,]+\.\d{2})',  # amount
        line
    )
    
    if not match:
        return None
    
    tx_type = match.group(1)
    date_str = match.group(2)
    num = (match.group(3) or '').strip()
    vendor = match.group(4).strip()
    amount_str = match.group(5).replace(',', '')
    
    try:
        tx_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        amount = Decimal(amount_str)
    except Exception:
        return None
    
    return {
        'type': tx_type,
        'date': tx_date,
        'num': num,
        'vendor': vendor,
        'amount': amount,
        'raw': line.strip()
    }


def classify_transaction(tx: dict) -> str:
    """Classify transaction into import type"""
    vendor_lower = tx['vendor'].lower()
    num_lower = tx['num'].lower() if tx['num'] else ''
    
    # Withdrawals
    if any(re.search(p, vendor_lower, re.I) or re.search(p, num_lower, re.I) for p in WITHDRAWAL_PATTERNS):
        return 'withdrawal'
    
    # Fees
    if any(re.search(p, vendor_lower, re.I) for p in FEE_PATTERNS):
        return 'bank_fee'
    
    # Transfers
    if any(re.search(p, vendor_lower, re.I) or re.search(p, num_lower, re.I) for p in TRANSFER_PATTERNS):
        return 'transfer'
    
    # Journal entries
    if tx['type'] == 'General Journal':
        return 'journal_entry'
    
    # Deposits
    if tx['type'] == 'Deposit':
        return 'deposit'
    
    # Everything else is vendor expense
    return 'vendor_expense'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='Extracted QB text file')
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--account', required=True, help='Account number (e.g., 1000)')
    ap.add_argument('--output-dir', default='exports/qb', help='Output directory')
    args = ap.parse_args()
    
    if not os.path.exists(args.input):
        print(f'[FAIL] Input file not found: {args.input}')
        return 1
    
    year_dir = os.path.join(args.output_dir, str(args.year))
    os.makedirs(year_dir, exist_ok=True)
    
    # Read and parse
    print(f'📄 Parsing QB reconciliation: {args.input}')
    transactions = []
    with open(args.input, 'r', encoding='utf-8') as f:
        for line in f:
            tx = parse_qb_line(line)
            if tx:
                tx['classification'] = classify_transaction(tx)
                tx['category'] = categorize_vendor(tx['vendor'])
                transactions.append(tx)
    
    print(f'   Extracted {len(transactions)} transactions')
    
    # Separate by classification
    by_class = defaultdict(list)
    for tx in transactions:
        by_class[tx['classification']].append(tx)
    
    # Write banking transactions CSV
    banking_path = os.path.join(year_dir, 'qb_banking_transactions.csv')
    with open(banking_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['transaction_date', 'account_number', 'description', 'vendor_name', 'debit_amount', 'credit_amount', 'category', 'source', 'reference_number'])
        for tx in transactions:
            debit = abs(tx['amount']) if tx['amount'] < 0 else 0
            credit = tx['amount'] if tx['amount'] > 0 else 0
            w.writerow([
                tx['date'].isoformat(),
                args.account,
                tx['raw'][:200],  # truncate
                tx['vendor'],
                f"{debit:.2f}",
                f"{credit:.2f}",
                tx['category'],
                'QB_RECONCILIATION',
                tx['num']
            ])
    print(f'[OK] Banking transactions: {banking_path}')
    
    # Write receipts CSV (vendor expenses only)
    receipts_path = os.path.join(year_dir, 'qb_receipts.csv')
    vendor_expenses = by_class['vendor_expense']
    with open(receipts_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['receipt_date', 'vendor_name', 'category', 'gross_amount', 'gst_amount', 'net_amount', 'description', 'source_system'])
        for tx in vendor_expenses:
            gross = abs(tx['amount'])
            gst, net = extract_gst_from_total(gross)
            w.writerow([
                tx['date'].isoformat(),
                tx['vendor'],
                tx['category'],
                f"{gross:.2f}",
                f"{gst:.2f}",
                f"{net:.2f}",
                tx['raw'][:200],
                'QB_RECONCILIATION'
            ])
    print(f'[OK] Receipts: {receipts_path} ({len(vendor_expenses)} vendor expenses)')
    
    # Summary
    summary_path = os.path.join(year_dir, 'qb_summary.csv')
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['classification', 'count', 'total_amount'])
        for cls in sorted(by_class.keys()):
            txs = by_class[cls]
            total = sum(tx['amount'] for tx in txs)
            w.writerow([cls, len(txs), f"{total:.2f}"])
    print(f'[OK] Summary: {summary_path}')
    
    # Console summary
    print('\n📊 Transaction Summary:')
    for cls in sorted(by_class.keys()):
        count = len(by_class[cls])
        total = sum(tx['amount'] for tx in by_class[cls])
        print(f'   {cls:20} {count:4} transactions  ${total:12,.2f}')
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
