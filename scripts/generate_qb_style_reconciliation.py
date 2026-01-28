#!/usr/bin/env python3
"""
QuickBooks-Style Reconciliation Summary Generator
================================================

Generates a reconciliation summary matching the QB printout format shown in the CIBC PDF:
- Beginning balance
- Cleared transactions (cheques/payments and deposits/credits)
- Cleared balance
- New transactions
- Ending balance

Outputs: reconciliation_summary_<account>_<year>.txt (formatted like QB printout)
"""
import os
import psycopg2
from datetime import date

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)

def format_money(val):
    return f"${abs(float(val or 0)):,.2f}" if val else "$0.00"

def generate_reconciliation_summary(account, year, month=12):
    """Generate QB-style reconciliation for a specific month-end."""
    period_end = date(year, month, 31 if month == 12 else 30)
    
    with psycopg2.connect(**DSN) as conn:
        cur = conn.cursor()
        
        # Get beginning balance (first transaction's starting point or opening balance)
        cur.execute("""
            SELECT MIN(transaction_date), MIN(balance)
            FROM banking_transactions
            WHERE account_number = %s AND EXTRACT(YEAR FROM transaction_date) = %s
        """, [account, year])
        first_date, first_balance = cur.fetchone()
        beginning_balance = float(first_balance or 0)
        
        # Get cleared transactions (assume all are cleared for now)
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE debit_amount > 0),
                COALESCE(SUM(debit_amount), 0),
                COUNT(*) FILTER (WHERE credit_amount > 0),
                COALESCE(SUM(credit_amount), 0)
            FROM banking_transactions
            WHERE account_number = %s 
              AND transaction_date BETWEEN %s AND %s
        """, [account, first_date, period_end])
        debit_count, debit_total, credit_count, credit_total = cur.fetchone()
        
        # Calculate net change
        net_cleared = float(credit_total or 0) - float(debit_total or 0)
        cleared_balance = beginning_balance + net_cleared
        
        # Get ending balance
        cur.execute("""
            SELECT balance
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date <= %s
            ORDER BY transaction_date DESC, transaction_id DESC
            LIMIT 1
        """, [account, period_end])
        row = cur.fetchone()
        ending_balance = float(row[0]) if row and row[0] is not None else cleared_balance
        
        # Format output
        output = []
        output.append("=" * 80)
        output.append(f"Arrow Limousine & Sedan Services Ltd.")
        output.append(f"Reconciliation Summary")
        output.append(f"Account {account}, Period Ending {period_end.strftime('%m/%d/%Y')}")
        output.append("=" * 80)
        output.append("")
        output.append(f"Beginning Balance                                    {format_money(beginning_balance):>15}")
        output.append("")
        output.append("  Cleared Transactions")
        output.append(f"    Cheques and Payments - {debit_count} items           {format_money(-debit_total):>15}")
        output.append(f"    Deposits and Credits - {credit_count} items            {format_money(credit_total):>15}")
        output.append(f"  Total Cleared Transactions                         {format_money(net_cleared):>15}")
        output.append("")
        output.append(f"Cleared Balance                                      {format_money(cleared_balance):>15}")
        output.append("")
        output.append(f"Register Balance as of {period_end.strftime('%m/%d/%Y')}                  {format_money(cleared_balance):>15}")
        output.append("")
        output.append(f"Ending Balance                                       {format_money(ending_balance):>15}")
        output.append("")
        output.append("=" * 80)
        output.append("")
        output.append("NOTES:")
        output.append(f"  - Data source: banking_transactions table")
        output.append(f"  - Account: {account}")
        output.append(f"  - Period: {first_date} to {period_end}")
        output.append(f"  - Total debits: {format_money(debit_total)} ({debit_count} transactions)")
        output.append(f"  - Total credits: {format_money(credit_total)} ({credit_count} transactions)")
        output.append("")
        
        return "\n".join(output)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', required=True)
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--month', type=int, default=12, help='Month-end (default: December)')
    ap.add_argument('--outdir', default='exports/reconciliation')
    args = ap.parse_args()
    
    os.makedirs(os.path.join(args.outdir, str(args.year)), exist_ok=True)
    output = generate_reconciliation_summary(args.account, args.year, args.month)
    
    outfile = os.path.join(args.outdir, str(args.year), f"reconciliation_summary_{args.account}_{args.year}.txt")
    with open(outfile, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(output)
    print(f"\n[OK] Saved to: {outfile}")

if __name__ == '__main__':
    main()
