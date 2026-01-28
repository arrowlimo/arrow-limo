#!/usr/bin/env python3
"""
QuickBooks Reconciliation Detail Comparison with ALMS Database

Compares individual QB reconciliation transactions (from CSV files) against
banking_transactions in the database to determine:
1. Which QB transactions are matched in the database
2. Which QB transactions are missing from the database
3. Which database transactions are not in QB reconciliation
4. Amount discrepancies and date differences

Processes all monthly reconciliation detail files for specified year(s).
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import csv
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import json
from collections import defaultdict
import re

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def normalize_description(desc):
    """Normalize description for matching."""
    if not desc:
        return ""
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    # Remove common variations
    desc = desc.replace('Point of Sale - ', '')
    desc = desc.replace('Electronic Funds Transfer ', '')
    desc = desc.replace('Branch Transaction ', '')
    return desc.strip()

def extract_amount_from_description(desc):
    """Extract dollar amounts from description for additional matching."""
    amounts = re.findall(r'\$?([\d,]+\.\d{2})', desc)
    return [float(amt.replace(',', '')) for amt in amounts]

def load_qb_reconciliation_month(recon_dir):
    """Load QB reconciliation details for a specific month."""
    recon_dir = Path(recon_dir)
    
    # Load cheques/payments (debits)
    debits = []
    cheques_file = recon_dir / f"cheques_and_payments_{recon_dir.name}.csv"
    if cheques_file.exists():
        with open(cheques_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                debits.append({
                    'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    'description': row['description'],
                    'normalized_desc': normalize_description(row['description']),
                    'amount': abs(float(row['debit'])) if row['debit'] else 0,
                    'type': 'debit',
                    'original_row': row
                })
    
    # Load deposits/credits
    credits = []
    deposits_file = recon_dir / f"deposits_and_credits_{recon_dir.name}.csv"
    if deposits_file.exists():
        with open(deposits_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                credits.append({
                    'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    'description': row['description'],
                    'normalized_desc': normalize_description(row['description']),
                    'amount': abs(float(row['credit'])) if row['credit'] else 0,
                    'type': 'credit',
                    'original_row': row
                })
    
    return debits, credits

def load_db_transactions_for_month(cur, year, month):
    """Load all banking transactions from database for a specific month."""
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            category,
            vendor_extracted
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
        ORDER BY transaction_date, transaction_id
    """, (year, month))
    
    transactions = []
    for row in cur.fetchall():
        transactions.append({
            'transaction_id': row[0],
            'date': row[1],
            'description': row[2],
            'normalized_desc': normalize_description(row[2]),
            'debit_amount': float(row[3]) if row[3] else 0,
            'credit_amount': float(row[4]) if row[4] else 0,
            'balance': float(row[5]) if row[5] else None,
            'category': row[6],
            'vendor': row[7],
            'matched': False,
            'match_type': None
        })
    
    return transactions

def match_transactions(qb_txns, db_txns, tolerance_days=3, amount_tolerance=0.01):
    """
    Match QB transactions to database transactions.
    
    Returns:
        matches: List of (qb_txn, db_txn, match_quality) tuples
        unmatched_qb: QB transactions with no match
        unmatched_db: DB transactions with no match
    """
    matches = []
    unmatched_qb = []
    
    for qb_txn in qb_txns:
        best_match = None
        best_score = 0
        
        for db_txn in db_txns:
            if db_txn['matched']:
                continue
            
            score = 0
            match_reasons = []
            
            # Check date proximity (within tolerance)
            date_diff = abs((qb_txn['date'] - db_txn['date']).days)
            if date_diff <= tolerance_days:
                score += 30 - (date_diff * 5)  # Closer dates = higher score
                match_reasons.append(f"date_diff_{date_diff}d")
            else:
                continue  # Date too far apart
            
            # Check amount match
            qb_amount = qb_txn['amount']
            db_amount = db_txn['debit_amount'] if qb_txn['type'] == 'debit' else db_txn['credit_amount']
            
            if abs(qb_amount - db_amount) <= amount_tolerance:
                score += 50  # Exact amount match is strongest signal
                match_reasons.append('exact_amount')
            else:
                continue  # Amount doesn't match
            
            # Check description similarity
            if qb_txn['normalized_desc'] == db_txn['normalized_desc']:
                score += 20
                match_reasons.append('exact_description')
            elif qb_txn['normalized_desc'] in db_txn['normalized_desc'] or db_txn['normalized_desc'] in qb_txn['normalized_desc']:
                score += 10
                match_reasons.append('partial_description')
            
            # Update best match
            if score > best_score:
                best_score = score
                best_match = (db_txn, score, match_reasons)
        
        if best_match and best_score >= 80:  # Require good confidence
            db_txn, score, reasons = best_match
            db_txn['matched'] = True
            db_txn['match_type'] = '+'.join(reasons)
            matches.append((qb_txn, db_txn, score, reasons))
        else:
            unmatched_qb.append(qb_txn)
    
    # Find unmatched database transactions
    unmatched_db = [txn for txn in db_txns if not txn['matched']]
    
    return matches, unmatched_qb, unmatched_db

def analyze_month(recon_dir, year, month, cur):
    """Analyze a single month's reconciliation."""
    print(f"\n{'='*80}")
    print(f"ANALYZING {year}-{month:02d}")
    print(f"{'='*80}")
    
    # Load QB reconciliation data
    qb_debits, qb_credits = load_qb_reconciliation_month(recon_dir)
    qb_all = qb_debits + qb_credits
    
    print(f"\n📊 QB Reconciliation:")
    print(f"   Debits/Payments: {len(qb_debits)} transactions, ${sum(t['amount'] for t in qb_debits):,.2f}")
    print(f"   Credits/Deposits: {len(qb_credits)} transactions, ${sum(t['amount'] for t in qb_credits):,.2f}")
    print(f"   Total: {len(qb_all)} transactions")
    
    # Load database transactions
    db_txns = load_db_transactions_for_month(cur, year, month)
    
    db_debits = [t for t in db_txns if t['debit_amount'] > 0]
    db_credits = [t for t in db_txns if t['credit_amount'] > 0]
    
    print(f"\n💾 Database (banking_transactions):")
    print(f"   Debits: {len(db_debits)} transactions, ${sum(t['debit_amount'] for t in db_debits):,.2f}")
    print(f"   Credits: {len(db_credits)} transactions, ${sum(t['credit_amount'] for t in db_credits):,.2f}")
    print(f"   Total: {len(db_txns)} transactions")
    
    # Match debits
    print(f"\n🔄 Matching Debits/Payments...")
    debit_matches, unmatched_qb_debits, unmatched_db_debits = match_transactions(qb_debits, db_debits)
    
    print(f"   ✓ Matched: {len(debit_matches)}/{len(qb_debits)} QB debits")
    print(f"   ✗ Unmatched QB: {len(unmatched_qb_debits)} (${sum(t['amount'] for t in unmatched_qb_debits):,.2f})")
    print(f"   ✗ Unmatched DB: {len(unmatched_db_debits)} (${sum(t['debit_amount'] for t in unmatched_db_debits):,.2f})")
    
    # Match credits
    print(f"\n🔄 Matching Credits/Deposits...")
    credit_matches, unmatched_qb_credits, unmatched_db_credits = match_transactions(qb_credits, db_credits)
    
    print(f"   ✓ Matched: {len(credit_matches)}/{len(qb_credits)} QB credits")
    print(f"   ✗ Unmatched QB: {len(unmatched_qb_credits)} (${sum(t['amount'] for t in unmatched_qb_credits):,.2f})")
    print(f"   ✗ Unmatched DB: {len(unmatched_db_credits)} (${sum(t['credit_amount'] for t in unmatched_db_credits):,.2f})")
    
    # Calculate match rate
    total_qb = len(qb_all)
    total_matched = len(debit_matches) + len(credit_matches)
    match_rate = (total_matched / total_qb * 100) if total_qb > 0 else 0
    
    print(f"\n📈 Overall Match Rate: {match_rate:.1f}% ({total_matched}/{total_qb})")
    
    # Show sample unmatched
    if unmatched_qb_debits:
        print(f"\n[WARN] Sample Unmatched QB Debits (first 5):")
        for txn in unmatched_qb_debits[:5]:
            print(f"   {txn['date']} | ${txn['amount']:,.2f} | {txn['description'][:60]}")
    
    if unmatched_qb_credits:
        print(f"\n[WARN] Sample Unmatched QB Credits (first 5):")
        for txn in unmatched_qb_credits[:5]:
            print(f"   {txn['date']} | ${txn['amount']:,.2f} | {txn['description'][:60]}")
    
    if unmatched_db_debits:
        print(f"\n[WARN] Sample Unmatched DB Debits (first 5):")
        for txn in unmatched_db_debits[:5]:
            print(f"   {txn['date']} | ${txn['debit_amount']:,.2f} | {txn['description'][:60]}")
    
    if unmatched_db_credits:
        print(f"\n[WARN] Sample Unmatched DB Credits (first 5):")
        for txn in unmatched_db_credits[:5]:
            print(f"   {txn['date']} | ${txn['credit_amount']:,.2f} | {txn['description'][:60]}")
    
    return {
        'month': f"{year}-{month:02d}",
        'qb_total': total_qb,
        'qb_debits': len(qb_debits),
        'qb_credits': len(qb_credits),
        'db_total': len(db_txns),
        'db_debits': len(db_debits),
        'db_credits': len(db_credits),
        'matched_debits': len(debit_matches),
        'matched_credits': len(credit_matches),
        'total_matched': total_matched,
        'match_rate': match_rate,
        'unmatched_qb_debits': len(unmatched_qb_debits),
        'unmatched_qb_credits': len(unmatched_qb_credits),
        'unmatched_db_debits': len(unmatched_db_debits),
        'unmatched_db_credits': len(unmatched_db_credits),
        'matches': {
            'debits': [(
                {
                    'date': str(qb['date']),
                    'amount': qb['amount'],
                    'description': qb['description']
                },
                {
                    'transaction_id': db['transaction_id'],
                    'date': str(db['date']),
                    'amount': db['debit_amount'],
                    'description': db['description']
                },
                score,
                reasons
            ) for qb, db, score, reasons in debit_matches],
            'credits': [(
                {
                    'date': str(qb['date']),
                    'amount': qb['amount'],
                    'description': qb['description']
                },
                {
                    'transaction_id': db['transaction_id'],
                    'date': str(db['date']),
                    'amount': db['credit_amount'],
                    'description': db['description']
                },
                score,
                reasons
            ) for qb, db, score, reasons in credit_matches]
        },
        'unmatched': {
            'qb_debits': [{
                'date': str(t['date']),
                'amount': t['amount'],
                'description': t['description']
            } for t in unmatched_qb_debits],
            'qb_credits': [{
                'date': str(t['date']),
                'amount': t['amount'],
                'description': t['description']
            } for t in unmatched_qb_credits],
            'db_debits': [{
                'transaction_id': t['transaction_id'],
                'date': str(t['date']),
                'amount': t['debit_amount'],
                'description': t['description']
            } for t in unmatched_db_debits],
            'db_credits': [{
                'transaction_id': t['transaction_id'],
                'date': str(t['date']),
                'amount': t['credit_amount'],
                'description': t['description']
            } for t in unmatched_db_credits]
        }
    }

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Compare QB reconciliation details with ALMS database')
    parser.add_argument('--year', type=int, default=2012, help='Year to analyze')
    parser.add_argument('--month', type=int, help='Specific month (1-12), or all months if not specified')
    parser.add_argument('--account', default='0228362', help='Bank account number')
    parser.add_argument('--output', default='l:/limo/reports/qb_reconciliation_comparison.json', 
                        help='Output JSON file path')
    args = parser.parse_args()
    
    base_dir = Path(f"l:/limo/exports/reconciliation/{args.account}/{args.year}")
    
    if not base_dir.exists():
        print(f"[FAIL] Reconciliation directory not found: {base_dir}")
        return
    
    conn = get_conn()
    cur = conn.cursor()
    
    results = []
    
    if args.month:
        months = [args.month]
    else:
        # Find all month directories
        month_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith(f"{args.year}-")])
        months = [int(d.name.split('-')[1]) for d in month_dirs]
    
    print(f"\n{'='*80}")
    print(f"QUICKBOOKS RECONCILIATION vs ALMS DATABASE COMPARISON")
    print(f"Account: {args.account}")
    print(f"Year: {args.year}")
    print(f"Months: {months if args.month else 'All (1-12)'}")
    print(f"{'='*80}")
    
    for month in months:
        recon_dir = base_dir / f"{args.year}-{month:02d}"
        if not recon_dir.exists():
            print(f"\n[WARN] Skipping {args.year}-{month:02d}: Directory not found")
            continue
        
        try:
            month_result = analyze_month(recon_dir, args.year, month, cur)
            results.append(month_result)
        except Exception as e:
            print(f"\n[FAIL] Error analyzing {args.year}-{month:02d}: {e}")
            import traceback
            traceback.print_exc()
    
    cur.close()
    conn.close()
    
    # Summary
    print(f"\n\n{'='*80}")
    print(f"ANNUAL SUMMARY - {args.year}")
    print(f"{'='*80}")
    
    total_qb = sum(r['qb_total'] for r in results)
    total_matched = sum(r['total_matched'] for r in results)
    overall_match_rate = (total_matched / total_qb * 100) if total_qb > 0 else 0
    
    print(f"\n📊 Overall Statistics:")
    print(f"   Months Analyzed: {len(results)}")
    print(f"   Total QB Transactions: {total_qb:,}")
    print(f"   Total Matched: {total_matched:,}")
    print(f"   Overall Match Rate: {overall_match_rate:.1f}%")
    
    print(f"\n📅 Month-by-Month Summary:")
    print(f"   {'Month':<10} {'QB':>6} {'DB':>6} {'Matched':>8} {'Rate':>6}")
    print(f"   {'-'*40}")
    for r in results:
        print(f"   {r['month']:<10} {r['qb_total']:>6} {r['db_total']:>6} {r['total_matched']:>8} {r['match_rate']:>5.1f}%")
    
    # Save detailed results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'year': args.year,
        'account': args.account,
        'summary': {
            'months_analyzed': len(results),
            'total_qb_transactions': total_qb,
            'total_matched': total_matched,
            'overall_match_rate': overall_match_rate
        },
        'monthly_results': results
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✓ Detailed results saved to: {output_path}")
    print(f"\n💡 Next Steps:")
    print(f"   • Review unmatched transactions in JSON output")
    print(f"   • Investigate date/amount discrepancies")
    print(f"   • Check if unmatched QB transactions need to be imported")
    print(f"   • Verify unmatched DB transactions are legitimate")

if __name__ == '__main__':
    main()
