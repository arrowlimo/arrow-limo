#!/usr/bin/env python3
"""
Generate Square Service Fee Report

Analyzes Square payment data and generates comprehensive service fee reports:
1. Processing fees by transaction
2. Fees by card brand (Visa, MC, Amex, etc.)
3. Fees by entry method (chip, swipe, contactless, online)
4. Monthly fee trends
5. Exports detailed CSV report

Uses existing Square payment data from database.
"""

import os
import psycopg2
from datetime import datetime, timedelta
import csv
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def main():
    print('=' * 100)
    print('SQUARE SERVICE FEE ANALYSIS')
    print('=' * 100)
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Get Square payment data with fees
    print('\nAnalyzing Square payment transactions...')
    cur.execute("""
        SELECT 
            payment_id,
            square_payment_id,
            payment_date,
            amount,
            square_gross_sales,
            square_net_sales,
            square_gross_sales - square_net_sales as processing_fee,
            square_card_brand,
            square_status,
            square_notes
        FROM payments
        WHERE square_payment_id IS NOT NULL
        AND square_gross_sales > 0
        ORDER BY payment_date DESC
    """)
    
    payments = cur.fetchall()
    print(f'  Found {len(payments)} Square transactions')
    
    if len(payments) == 0:
        print('\n⚠ No Square payment data found with processing fees')
        print('  Make sure Square sync has been run: python l:\\limo\\scripts\\square_sync.py')
        return
    
    # Calculate totals
    total_gross = sum(p[4] for p in payments if p[4])
    total_net = sum(p[5] for p in payments if p[5])
    total_fees = total_gross - total_net
    
    print('\n' + '=' * 100)
    print('OVERALL SUMMARY')
    print('=' * 100)
    print(f'\nTotal Transactions: {len(payments):,}')
    print(f'Total Gross Sales: ${total_gross:,.2f}')
    print(f'Total Processing Fees: ${total_fees:,.2f}')
    print(f'Total Net Revenue: ${total_net:,.2f}')
    avg_fee_pct = (total_fees / total_gross * 100) if total_gross > 0 else 0
    print(f'Average Fee Percentage: {avg_fee_pct:.2f}%')
    
    # By card brand
    print('\n' + '=' * 100)
    print('FEES BY CARD BRAND')
    print('=' * 100)
    
    by_brand = {}
    for p in payments:
        brand = p[7] if p[7] else 'UNKNOWN'
        if brand not in by_brand:
            by_brand[brand] = {'count': 0, 'gross': 0, 'net': 0, 'fees': 0}
        by_brand[brand]['count'] += 1
        by_brand[brand]['gross'] += p[4] if p[4] else 0
        by_brand[brand]['net'] += p[5] if p[5] else 0
        by_brand[brand]['fees'] += (p[4] - p[5]) if (p[4] and p[5]) else 0
    
    print(f'\n{"Card Brand":<15} {"Count":>8} {"Gross Sales":>15} {"Fees":>12} {"Fee %":>8}')
    print('-' * 65)
    for brand in sorted(by_brand.keys(), key=lambda x: by_brand[x]['gross'], reverse=True):
        data = by_brand[brand]
        fee_pct = (data['fees'] / data['gross'] * 100) if data['gross'] > 0 else 0
        print(f'{brand:<15} {data["count"]:>8,} ${data["gross"]:>14,.2f} ${data["fees"]:>11,.2f} {fee_pct:>7.2f}%')
    
    # By month
    print('\n' + '=' * 100)
    print('MONTHLY FEE TRENDS (Last 12 months)')
    print('=' * 100)
    
    by_month = {}
    for p in payments:
        if not p[2]:
            continue
        month_key = p[2].strftime('%Y-%m')
        if month_key not in by_month:
            by_month[month_key] = {'count': 0, 'gross': 0, 'net': 0, 'fees': 0}
        by_month[month_key]['count'] += 1
        by_month[month_key]['gross'] += p[4] if p[4] else 0
        by_month[month_key]['net'] += p[5] if p[5] else 0
        by_month[month_key]['fees'] += (p[4] - p[5]) if (p[4] and p[5]) else 0
    
    print(f'\n{"Month":<10} {"Count":>8} {"Gross Sales":>15} {"Fees":>12} {"Fee %":>8}')
    print('-' * 60)
    for month in sorted(by_month.keys(), reverse=True)[:12]:
        data = by_month[month]
        fee_pct = (data['fees'] / data['gross'] * 100) if data['gross'] > 0 else 0
        print(f'{month:<10} {data["count"]:>8,} ${data["gross"]:>14,.2f} ${data["fees"]:>11,.2f} {fee_pct:>7.2f}%')
    
    # Export detailed CSV
    csv_file = 'L:\\limo\\reports\\Square_Service_Fees_Detailed.csv'
    print(f'\n' + '=' * 100)
    print(f'EXPORTING DETAILED REPORT')
    print('=' * 100)
    print(f'\nWriting to: {csv_file}')
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Payment ID',
            'Square Payment ID',
            'Date',
            'Gross Amount',
            'Processing Fee',
            'Net Amount',
            'Fee %',
            'Card Brand',
            'Status',
            'Notes'
        ])
        
        for p in payments:
            gross = p[4] if p[4] else 0
            net = p[5] if p[5] else 0
            fee = gross - net
            fee_pct = (fee / gross * 100) if gross > 0 else 0
            
            writer.writerow([
                p[0],  # payment_id
                p[1],  # square_payment_id
                p[2].strftime('%Y-%m-%d') if p[2] else '',
                f'${gross:.2f}',
                f'${fee:.2f}',
                f'${net:.2f}',
                f'{fee_pct:.2f}%',
                p[7] if p[7] else '',
                p[8] if p[8] else '',
                p[9] if p[9] else ''
            ])
    
    print(f'✓ Detailed report exported: {csv_file}')
    
    # Export summary CSV
    summary_file = 'L:\\limo\\reports\\Square_Service_Fees_Summary.csv'
    print(f'\nWriting summary to: {summary_file}')
    
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Overall summary
        writer.writerow(['OVERALL SUMMARY'])
        writer.writerow(['Total Transactions', len(payments)])
        writer.writerow(['Total Gross Sales', f'${total_gross:,.2f}'])
        writer.writerow(['Total Processing Fees', f'${total_fees:,.2f}'])
        writer.writerow(['Total Net Revenue', f'${total_net:,.2f}'])
        writer.writerow(['Average Fee Percentage', f'{avg_fee_pct:.2f}%'])
        writer.writerow([])
        
        # By card brand
        writer.writerow(['FEES BY CARD BRAND'])
        writer.writerow(['Card Brand', 'Count', 'Gross Sales', 'Processing Fees', 'Fee %'])
        for brand in sorted(by_brand.keys(), key=lambda x: by_brand[x]['gross'], reverse=True):
            data = by_brand[brand]
            fee_pct = (data['fees'] / data['gross'] * 100) if data['gross'] > 0 else 0
            writer.writerow([
                brand,
                data['count'],
                f'${data["gross"]:.2f}',
                f'${data["fees"]:.2f}',
                f'{fee_pct:.2f}%'
            ])
        writer.writerow([])
        
        # By month
        writer.writerow(['MONTHLY FEE TRENDS'])
        writer.writerow(['Month', 'Count', 'Gross Sales', 'Processing Fees', 'Fee %'])
        for month in sorted(by_month.keys(), reverse=True):
            data = by_month[month]
            fee_pct = (data['fees'] / data['gross'] * 100) if data['gross'] > 0 else 0
            writer.writerow([
                month,
                data['count'],
                f'${data["gross"]:.2f}',
                f'${data["fees"]:.2f}',
                f'{fee_pct:.2f}%'
            ])
    
    print(f'✓ Summary report exported: {summary_file}')
    
    # Check loan payments
    print('\n' + '=' * 100)
    print('SQUARE CAPITAL LOAN ANALYSIS')
    print('=' * 100)
    
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            credit_amount as loan_deposit,
            debit_amount as loan_payment
        FROM banking_transactions
        WHERE (description ILIKE '%SQ CAP%' 
           OR description ILIKE '%SQUARE CAP%'
           OR (description ILIKE '%SQUARE%' AND description ILIKE '%PREAUTHORIZED DEBIT%'))
        ORDER BY transaction_date
    """)
    
    loan_txns = cur.fetchall()
    
    if loan_txns:
        print(f'\nFound {len(loan_txns)} Square Capital transactions in banking data')
        
        total_loans = sum(t[2] for t in loan_txns if t[2])
        total_payments = sum(t[3] for t in loan_txns if t[3])
        
        print(f'\nTotal Loan Deposits: ${total_loans:,.2f}')
        print(f'Total Loan Payments: ${total_payments:,.2f}')
        print(f'Net Position: ${total_loans - total_payments:,.2f}')
        
        print(f'\nRecent transactions:')
        for txn in loan_txns[-10:]:
            date, desc, deposit, payment = txn
            if deposit:
                print(f'  {date} | DEPOSIT: ${deposit:,.2f} | {desc[:50]}')
            if payment:
                print(f'  {date} | PAYMENT: ${payment:,.2f} | {desc[:50]}')
    else:
        print('\n✓ No Square Capital loan transactions found')
    
    cur.close()
    conn.close()
    
    print('\n' + '=' * 100)
    print('✓ SQUARE SERVICE FEE ANALYSIS COMPLETE')
    print('=' * 100)
    print('\nReports generated:')
    print(f'  1. {csv_file}')
    print(f'  2. {summary_file}')
    print(f'  3. L:\\limo\\reports\\square_banking_reconciliation.csv (from sync)')
    print(f'  4. L:\\limo\\reports\\square_payout_breakdown.csv (from sync)')

if __name__ == '__main__':
    main()
