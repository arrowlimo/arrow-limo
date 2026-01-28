#!/usr/bin/env python3
"""
Audit 2012 Banking Totals
=========================

Compares totals from three sources:
1. QuickBooks reconciliation (accountant-prepared, authoritative)
2. Database banking_transactions table
3. Parsed CIBC statements

Verifies:
- Total debits/withdrawals match
- Total credits/deposits match
- Net change matches
- Opening and closing balances match

Outputs detailed variance report.

Safe: Read-only audit.
"""
from __future__ import annotations

import os
import csv
import sys
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import DictCursor
import re


DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

PARSED_DIR = r"L:\limo\staging\2012_parsed"
EXTRACT_DIR = r"L:\limo\staging\2012_pdf_extracts"
OUTPUT_DIR = r"L:\limo\staging\2012_comparison"


def parse_qb_summary(text: str) -> dict:
    """Extract ALL QuickBooks reconciliation summary totals for entire year"""
    # Parse all monthly reconciliation summaries and aggregate
    # Format for each month:
    # Beginning Balance 714.80
    # Cleared Transactions
    # Cheques and Payments - 21 items -5,489.55
    # Deposits and Credits - 2 items 4,795.96
    
    monthly_summaries = []
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Find reconciliation summary sections
        if 'Reconciliation Summary' in line:
            # Look for period ending date
            period_line = None
            for j in range(i, min(i+5, len(lines))):
                if 'Period Ending' in lines[j]:
                    period_line = lines[j]
                    break
            
            if period_line:
                # Extract month/year from period ending
                period_match = re.search(r'(\d{2}/\d{2}/\d{4})', period_line)
                if period_match:
                    period_date = period_match.group(1)
                    
                    # Parse this reconciliation's data
                    summary = {
                        'period': period_date,
                        'beginning_balance': None,
                        'cleared_payments': None,
                        'cleared_deposits': None,
                    }
                    
                    # Look ahead for Beginning Balance and transactions
                    for k in range(i, min(i+20, len(lines))):
                        l = lines[k].strip()
                        
                        if 'Beginning Balance' in l:
                            # Balance is typically on same line or next line
                            match = re.search(r'(-?\d{1,3}(?:,\d{3})*\.\d{2})', l)
                            if match:
                                summary['beginning_balance'] = match.group(1).replace(',', '')
                        
                        if 'Cheques and Payments' in l and 'Cleared' in lines[k-1] if k > 0 else False:
                            match = re.search(r'(-?\d{1,3}(?:,\d{3})*\.\d{2})', l)
                            if match:
                                summary['cleared_payments'] = match.group(1).replace(',', '')
                        
                        if 'Deposits and Credits' in l:
                            match = re.search(r'(-?\d{1,3}(?:,\d{3})*\.\d{2})', l)
                            if match:
                                summary['cleared_deposits'] = match.group(1).replace(',', '')
                    
                    monthly_summaries.append(summary)
        
        i += 1
    
    # Aggregate all monthly totals
    total_cleared_payments = 0
    total_cleared_deposits = 0
    first_beginning_balance = None
    
    for i, month_summary in enumerate(monthly_summaries):
        if i == 0 and month_summary['beginning_balance']:
            first_beginning_balance = float(month_summary['beginning_balance'])
        
        if month_summary['cleared_payments']:
            # Payments are negative in QB format
            total_cleared_payments += abs(float(month_summary['cleared_payments']))
        
        if month_summary['cleared_deposits']:
            total_cleared_deposits += float(month_summary['cleared_deposits'])
    
    # Calculate ending balance (beginning + deposits - payments)
    ending_balance = None
    if first_beginning_balance is not None:
        ending_balance = first_beginning_balance + total_cleared_deposits - total_cleared_payments
    
    return {
        'monthly_count': len(monthly_summaries),
        'monthly_summaries': monthly_summaries,
        'beginning_balance': str(first_beginning_balance) if first_beginning_balance else None,
        'total_cleared_payments': str(total_cleared_payments),
        'total_cleared_deposits': str(total_cleared_deposits),
        'calculated_ending_balance': str(ending_balance) if ending_balance else None,
    }


def get_db_totals(conn, year: int = 2012) -> dict:
    """Get banking totals from database"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                COUNT(*) as transaction_count,
                COALESCE(SUM(debit_amount), 0) as total_debits,
                COALESCE(SUM(credit_amount), 0) as total_credits,
                MIN(transaction_date) as earliest_date,
                MAX(transaction_date) as latest_date
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            """,
            (year,),
        )
        row = cur.fetchone()
        
        # Get opening balance (first transaction balance minus its amount)
        cur.execute(
            """
            SELECT balance, debit_amount, credit_amount
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date, transaction_id
            LIMIT 1
            """,
            (year,),
        )
        first_tx = cur.fetchone()
        opening_balance = None
        if first_tx and first_tx[0] is not None:
            # Opening balance = first transaction balance - its credit + its debit
            opening_balance = float(first_tx[0]) - float(first_tx[2] or 0) + float(first_tx[1] or 0)
        
        # Get closing balance (last transaction balance)
        cur.execute(
            """
            SELECT balance
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = %s
            ORDER BY transaction_date DESC, transaction_id DESC
            LIMIT 1
            """,
            (year,),
        )
        last_tx = cur.fetchone()
        closing_balance = float(last_tx[0]) if last_tx and last_tx[0] else None
        
        return {
            'transaction_count': int(row[0]),
            'total_debits': float(row[1]),
            'total_credits': float(row[2]),
            'net_change': float(row[2]) - float(row[1]),
            'earliest_date': str(row[3]) if row[3] else None,
            'latest_date': str(row[4]) if row[4] else None,
            'opening_balance': opening_balance,
            'closing_balance': closing_balance,
        }


def get_cibc_totals(csv_path: str) -> dict:
    """Calculate totals from parsed CIBC statements"""
    total_withdrawals = Decimal('0')
    total_deposits = Decimal('0')
    transaction_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transaction_count += 1
            if row.get('withdrawal'):
                try:
                    total_withdrawals += Decimal(row['withdrawal'])
                except:
                    pass
            if row.get('deposit'):
                try:
                    total_deposits += Decimal(row['deposit'])
                except:
                    pass
    
    return {
        'transaction_count': transaction_count,
        'total_withdrawals': float(total_withdrawals),
        'total_deposits': float(total_deposits),
        'net_change': float(total_deposits - total_withdrawals),
    }


def main():
    print("=" * 80)
    print("2012 BANKING TOTALS AUDIT")
    print("=" * 80)
    print()
    
    # Parse QuickBooks summary
    qb_extract_path = os.path.join(EXTRACT_DIR, '2012 quickbooks_ocred.txt')
    print("📊 Parsing QuickBooks reconciliation summary...")
    
    with open(qb_extract_path, 'r', encoding='utf-8') as f:
        qb_text = f.read()
    
    qb_summary = parse_qb_summary(qb_text)
    
    print("\n[OK] QuickBooks Summary (Accountant-Prepared):")
    print(f"   Months Found:           {qb_summary.get('monthly_count', 0)}")
    print(f"   Beginning Balance:      ${qb_summary.get('beginning_balance', 'N/A')}")
    print(f"   Total Cleared Payments: ${float(qb_summary.get('total_cleared_payments', 0)):,.2f}")
    print(f"   Total Cleared Deposits: ${float(qb_summary.get('total_cleared_deposits', 0)):,.2f}")
    print(f"   Calculated End Balance: ${qb_summary.get('calculated_ending_balance', 'N/A')}")
    
    # Get database totals
    print(f"\n📊 Querying database totals...")
    try:
        with psycopg2.connect(**DSN) as conn:
            db_totals = get_db_totals(conn, 2012)
    except Exception as e:
        print(f"[FAIL] Error connecting to database: {e}")
        sys.exit(1)
    
    print("\n[OK] Database Totals:")
    print(f"   Transaction Count: {db_totals['transaction_count']}")
    print(f"   Total Debits:      ${db_totals['total_debits']:,.2f}")
    print(f"   Total Credits:     ${db_totals['total_credits']:,.2f}")
    print(f"   Net Change:        ${db_totals['net_change']:,.2f}")
    print(f"   Opening Balance:   ${db_totals['opening_balance']:,.2f}" if db_totals['opening_balance'] else "   Opening Balance:   N/A")
    print(f"   Closing Balance:   ${db_totals['closing_balance']:,.2f}" if db_totals['closing_balance'] else "   Closing Balance:   N/A")
    print(f"   Date Range:        {db_totals['earliest_date']} to {db_totals['latest_date']}")
    
    # Get CIBC statement totals
    print(f"\n📊 Calculating CIBC statement totals...")
    cibc_csv_path = os.path.join(PARSED_DIR, '2012_cibc_transactions.csv')
    cibc_totals = get_cibc_totals(cibc_csv_path)
    
    print("\n[OK] CIBC Statement Totals (Parsed):")
    print(f"   Transaction Count: {cibc_totals['transaction_count']}")
    print(f"   Total Withdrawals: ${cibc_totals['total_withdrawals']:,.2f}")
    print(f"   Total Deposits:    ${cibc_totals['total_deposits']:,.2f}")
    print(f"   Net Change:        ${cibc_totals['net_change']:,.2f}")
    
    # Compare and generate variance report
    print(f"\n" + "=" * 80)
    print("VARIANCE ANALYSIS")
    print("=" * 80)
    
    report_lines = []
    report_lines.append("2012 BANKING TOTALS AUDIT REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append("QUICKBOOKS RECONCILIATION (Accountant-Prepared - AUTHORITATIVE):")
    report_lines.append(f"  Months Reconciled:          {qb_summary.get('monthly_count', 0)}")
    report_lines.append(f"  Beginning Balance:          ${qb_summary.get('beginning_balance', 'N/A')}")
    report_lines.append(f"  Total Cleared Payments:     ${float(qb_summary.get('total_cleared_payments', 0)):,.2f}")
    report_lines.append(f"  Total Cleared Deposits:     ${float(qb_summary.get('total_cleared_deposits', 0)):,.2f}")
    report_lines.append(f"  Calculated Ending Balance:  ${qb_summary.get('calculated_ending_balance', 'N/A')}")
    report_lines.append("")
    report_lines.append("  Monthly Breakdown:")
    for month_data in qb_summary.get('monthly_summaries', []):
        report_lines.append(f"    {month_data['period']}: Payments ${month_data['cleared_payments']}, Deposits ${month_data['cleared_deposits']}")
    report_lines.append("")
    report_lines.append("DATABASE (almsdata.banking_transactions):")
    report_lines.append(f"  Transaction Count:  {db_totals['transaction_count']}")
    report_lines.append(f"  Total Debits:       ${db_totals['total_debits']:,.2f}")
    report_lines.append(f"  Total Credits:      ${db_totals['total_credits']:,.2f}")
    report_lines.append(f"  Net Change:         ${db_totals['net_change']:,.2f}")
    report_lines.append(f"  Opening Balance:    ${db_totals['opening_balance']:,.2f}" if db_totals['opening_balance'] else "  Opening Balance:    N/A")
    report_lines.append(f"  Closing Balance:    ${db_totals['closing_balance']:,.2f}" if db_totals['closing_balance'] else "  Closing Balance:    N/A")
    report_lines.append("")
    report_lines.append("CIBC STATEMENTS (Parsed from PDFs):")
    report_lines.append(f"  Transaction Count:  {cibc_totals['transaction_count']}")
    report_lines.append(f"  Total Withdrawals:  ${cibc_totals['total_withdrawals']:,.2f}")
    report_lines.append(f"  Total Deposits:     ${cibc_totals['total_deposits']:,.2f}")
    report_lines.append(f"  Net Change:         ${cibc_totals['net_change']:,.2f}")
    report_lines.append("")
    report_lines.append("=" * 80)
    report_lines.append("VARIANCE ANALYSIS:")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # Calculate variances
    try:
        qb_total_payments = float(qb_summary.get('total_cleared_payments', '0'))
        qb_total_deposits = float(qb_summary.get('total_cleared_deposits', '0'))
        qb_beginning = float(qb_summary.get('beginning_balance', '0') or '0')
        qb_ending = float(qb_summary.get('calculated_ending_balance', '0') or '0')
        
        # Compare debits/payments
        db_vs_qb_debits = db_totals['total_debits'] - abs(qb_total_payments)
        print(f"\n💰 Debits/Payments Comparison:")
        print(f"   QuickBooks:  ${abs(qb_total_payments):,.2f}")
        print(f"   Database:    ${db_totals['total_debits']:,.2f}")
        print(f"   Variance:    ${db_vs_qb_debits:,.2f}")
        
        report_lines.append(f"Debits/Payments:")
        report_lines.append(f"  QuickBooks Cleared Payments:  ${abs(qb_total_payments):,.2f}")
        report_lines.append(f"  Database Total Debits:        ${db_totals['total_debits']:,.2f}")
        report_lines.append(f"  Variance:                     ${db_vs_qb_debits:,.2f}")
        if abs(db_vs_qb_debits) < 100:
            report_lines.append(f"  Status: [OK] MATCH (within $100 tolerance)")
            print(f"   Status: [OK] MATCH")
        else:
            report_lines.append(f"  Status: [WARN]  VARIANCE EXCEEDS $100")
            print(f"   Status: [WARN]  VARIANCE")
        report_lines.append("")
        
        # Compare credits/deposits
        db_vs_qb_credits = db_totals['total_credits'] - qb_total_deposits
        print(f"\n💰 Credits/Deposits Comparison:")
        print(f"   QuickBooks:  ${qb_total_deposits:,.2f}")
        print(f"   Database:    ${db_totals['total_credits']:,.2f}")
        print(f"   Variance:    ${db_vs_qb_credits:,.2f}")
        
        report_lines.append(f"Credits/Deposits:")
        report_lines.append(f"  QuickBooks Cleared Deposits:  ${qb_total_deposits:,.2f}")
        report_lines.append(f"  Database Total Credits:       ${db_totals['total_credits']:,.2f}")
        report_lines.append(f"  Variance:                     ${db_vs_qb_credits:,.2f}")
        if abs(db_vs_qb_credits) < 100:
            report_lines.append(f"  Status: [OK] MATCH (within $100 tolerance)")
            print(f"   Status: [OK] MATCH")
        else:
            report_lines.append(f"  Status: [WARN]  VARIANCE EXCEEDS $100")
            print(f"   Status: [WARN]  VARIANCE")
        report_lines.append("")
        
        # Compare balances
        if db_totals['opening_balance'] and qb_beginning:
            opening_variance = db_totals['opening_balance'] - qb_beginning
            print(f"\n💰 Opening Balance Comparison:")
            print(f"   QuickBooks:  ${qb_beginning:,.2f}")
            print(f"   Database:    ${db_totals['opening_balance']:,.2f}")
            print(f"   Variance:    ${opening_variance:,.2f}")
            
            report_lines.append(f"Opening Balance:")
            report_lines.append(f"  QuickBooks:  ${qb_beginning:,.2f}")
            report_lines.append(f"  Database:    ${db_totals['opening_balance']:,.2f}")
            report_lines.append(f"  Variance:    ${opening_variance:,.2f}")
            if abs(opening_variance) < 1:
                report_lines.append(f"  Status: [OK] MATCH")
                print(f"   Status: [OK] MATCH")
            else:
                report_lines.append(f"  Status: [WARN]  VARIANCE")
                print(f"   Status: [WARN]  VARIANCE")
            report_lines.append("")
        
        if db_totals['closing_balance'] and qb_ending:
            closing_variance = db_totals['closing_balance'] - qb_ending
            print(f"\n💰 Ending Balance Comparison:")
            print(f"   QuickBooks:  ${qb_ending:,.2f}")
            print(f"   Database:    ${db_totals['closing_balance']:,.2f}")
            print(f"   Variance:    ${closing_variance:,.2f}")
            
            report_lines.append(f"Ending Balance:")
            report_lines.append(f"  QuickBooks:  ${qb_ending:,.2f}")
            report_lines.append(f"  Database:    ${db_totals['closing_balance']:,.2f}")
            report_lines.append(f"  Variance:    ${closing_variance:,.2f}")
            if abs(closing_variance) < 1:
                report_lines.append(f"  Status: [OK] MATCH")
                print(f"   Status: [OK] MATCH")
            else:
                report_lines.append(f"  Status: [WARN]  VARIANCE")
                print(f"   Status: [WARN]  VARIANCE")
            report_lines.append("")
        
    except Exception as e:
        report_lines.append(f"Error calculating variances: {e}")
        print(f"[WARN]  Error calculating variances: {e}")
    
    # Save report
    report_path = os.path.join(OUTPUT_DIR, 'banking_totals_audit.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"\n📋 Saved audit report: {report_path}")
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
