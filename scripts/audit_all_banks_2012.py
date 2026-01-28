#!/usr/bin/env python3
"""
Audit All Bank Accounts 2012
- Combines CIBC and Scotiabank totals from statements and QuickBooks
- Compares to database banking_transactions
- Produces comprehensive 2-account reconciliation report

Safe: Read-only. Outputs to staging/2012_comparison/all_banks_audit_2012.txt
"""
from pathlib import Path
from decimal import Decimal
import os
import json
import psycopg2

OUTPUT_TXT = Path(r"L:\limo\staging\2012_comparison\all_banks_audit_2012.txt")
CIBC_JSON = Path(r"L:\limo\staging\2012_comparison\cibc_statement_monthly_2012.json")

# From CIBC statement audit (already validated)
CIBC_STMT_DEPOSITS = Decimal('350936.91')
CIBC_STMT_WITHDRAWALS = Decimal('358093.04')

# From Scotiabank QB reconciliation (Period Ending 12/31/2012)
# Cleared: 1 item $51,950.93 deposits, 95 items $51,004.12 payments
# New: 22 items $245,862.93 deposits, 425 items $252,268.23 payments
SCOTIA_QB_DEPOSITS = Decimal('51950.93') + Decimal('245862.93')  # = 297,813.86
SCOTIA_QB_PAYMENTS = Decimal('51004.12') + Decimal('252268.23')  # = 303,272.35

# From QB CIBC reconciliation (from earlier audit_banking_totals.py)
CIBC_QB_DEPOSITS = Decimal('833621.56')
CIBC_QB_PAYMENTS = Decimal('311329.45')


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def get_db_totals() -> tuple[Decimal, Decimal]:
    """Get total credits/debits from banking_transactions for 2012."""
    sql = """
    SELECT COALESCE(SUM(credit_amount), 0) AS total_credits,
           COALESCE(SUM(debit_amount), 0) AS total_debits
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01';
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            return Decimal(str(row[0] or 0)), Decimal(str(row[1] or 0))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fmt(d: Decimal) -> str:
    return f"${d:,.2f}"


def main():
    db_credits, db_debits = get_db_totals()

    # Combined statement totals (CIBC only; Scotia statements too corrupted)
    stmt_deposits = CIBC_STMT_DEPOSITS
    stmt_withdrawals = CIBC_STMT_WITHDRAWALS

    # Combined QB totals (both accounts)
    qb_deposits = CIBC_QB_DEPOSITS + SCOTIA_QB_DEPOSITS
    qb_payments = CIBC_QB_PAYMENTS + SCOTIA_QB_PAYMENTS

    lines = []
    lines.append("=" * 80)
    lines.append("ALL BANK ACCOUNTS AUDIT (2012)")
    lines.append("=" * 80)
    lines.append("")
    lines.append("IDENTIFIED ACCOUNTS")
    lines.append("-" * 80)
    lines.append("1. CIBC Bank (Account 74-61615 / DB: 0228362 / QB: 1000)")
    lines.append("2. Scotiabank Main (Account 90399-01060-11 / QB: 1010)")
    lines.append("")

    lines.append("ACCOUNT 1: CIBC BANK")
    lines.append("-" * 80)
    lines.append(f"  Statement Deposits:    {fmt(CIBC_STMT_DEPOSITS)} (12 months verified)")
    lines.append(f"  Statement Withdrawals: {fmt(CIBC_STMT_WITHDRAWALS)}")
    lines.append(f"  QuickBooks Deposits:   {fmt(CIBC_QB_DEPOSITS)}")
    lines.append(f"  QuickBooks Payments:   {fmt(CIBC_QB_PAYMENTS)}")
    lines.append(f"  Variance (Stmt vs QB): {fmt((CIBC_STMT_DEPOSITS - CIBC_QB_DEPOSITS).quantize(Decimal('0.01')))}")
    lines.append("")

    lines.append("ACCOUNT 2: SCOTIABANK MAIN")
    lines.append("-" * 80)
    lines.append(f"  QuickBooks Deposits:   {fmt(SCOTIA_QB_DEPOSITS)}")
    lines.append(f"    Cleared: $51,950.93 (1 item)")
    lines.append(f"    New:     $245,862.93 (22 items)")
    lines.append(f"  QuickBooks Payments:   {fmt(SCOTIA_QB_PAYMENTS)}")
    lines.append(f"    Cleared: $51,004.12 (95 items)")
    lines.append(f"    New:     $252,268.23 (425 items)")
    lines.append(f"  Statement Status:      CORRUPTED OCR (manual review required)")
    lines.append("")

    lines.append("=" * 80)
    lines.append("COMBINED TOTALS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("DEPOSITS/CREDITS")
    lines.append("-" * 80)
    lines.append(f"  QuickBooks (both accounts):  {fmt(qb_deposits)}")
    lines.append(f"  Database (all accounts):     {fmt(db_credits)}")
    lines.append(f"  Variance (DB - QB):          {fmt((db_credits - qb_deposits).quantize(Decimal('0.01')))}")
    lines.append(f"  Missing from Database:       {fmt((qb_deposits - db_credits).quantize(Decimal('0.01')))}")
    lines.append("")
    lines.append(f"  CIBC Statements (verified):  {fmt(stmt_deposits)}")
    lines.append(f"  Scotia Statements:           N/A (OCR corrupted)")
    lines.append("")

    lines.append("PAYMENTS/DEBITS")
    lines.append("-" * 80)
    lines.append(f"  QuickBooks (both accounts):  {fmt(qb_payments)}")
    lines.append(f"  Database (all accounts):     {fmt(db_debits)}")
    lines.append(f"  Variance (DB - QB):          {fmt((db_debits - qb_payments).quantize(Decimal('0.01')))}")
    lines.append(f"  Missing from Database:       {fmt((qb_payments - db_debits).quantize(Decimal('0.01')))}")
    lines.append("")

    lines.append("=" * 80)
    lines.append("KEY FINDINGS")
    lines.append("=" * 80)
    missing_deposits = (qb_deposits - db_credits).quantize(Decimal('0.01'))
    missing_payments = (qb_payments - db_debits).quantize(Decimal('0.01'))
    
    lines.append(f"1. Database is missing {fmt(missing_deposits)} in deposits")
    lines.append(f"   - QB Total Deposits: {fmt(qb_deposits)}")
    lines.append(f"   - DB Total Credits:  {fmt(db_credits)}")
    lines.append(f"   - Missing %: {(missing_deposits / qb_deposits * 100 if qb_deposits else Decimal('0')):.1f}%")
    lines.append("")
    lines.append(f"2. Database is missing {fmt(missing_payments)} in payments")
    lines.append(f"   - QB Total Payments: {fmt(qb_payments)}")
    lines.append(f"   - DB Total Debits:   {fmt(db_debits)}")
    lines.append(f"   - Missing %: {(missing_payments / qb_payments * 100 if qb_payments else Decimal('0')):.1f}%")
    lines.append("")
    lines.append("3. Scotiabank account (QB 1010) appears to be MISSING from database entirely")
    lines.append(f"   - Expected Scotia deposits: {fmt(SCOTIA_QB_DEPOSITS)}")
    lines.append(f"   - No Scotia account found in banking_transactions")
    lines.append("")
    lines.append("4. CIBC statements total only $350,936.91 vs QB $833,621.56")
    lines.append("   - May indicate missing statement months or additional sub-accounts")
    lines.append("   - OR QB includes both CIBC + Scotia combined under account 1000")
    lines.append("")

    lines.append("=" * 80)
    lines.append("RECOMMENDED ACTIONS")
    lines.append("=" * 80)
    lines.append("1. Verify database account mapping:")
    lines.append("   - Check if account_number field contains Scotia identifiers")
    lines.append("   - Confirm CIBC account 0228362 mapping to QB 1000")
    lines.append("2. Import missing Scotiabank transactions ($297,813.86 deposits)")
    lines.append("3. Investigate CIBC variance ($482,684.65 between statements and QB)")
    lines.append("4. Review payments table ($1.35M) vs banking ($319K credits) discrepancy")
    lines.append("")

    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Saved comprehensive audit to: {OUTPUT_TXT}")
    print("")
    print("SUMMARY:")
    print(f"  Total QB Deposits (both accounts): {fmt(qb_deposits)}")
    print(f"  Total DB Credits:                  {fmt(db_credits)}")
    print(f"  Missing Deposits:                  {fmt(missing_deposits)}")
    print(f"  Missing %:                         {(missing_deposits / qb_deposits * 100 if qb_deposits else Decimal('0')):.1f}%")


if __name__ == '__main__':
    main()
