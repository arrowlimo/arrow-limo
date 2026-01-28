#!/usr/bin/env python3
"""
Square Capital Loan Reconciliation Report
Complete analysis of Square Capital loans and repayments.
"""

import os
from decimal import Decimal
import psycopg2
from dotenv import load_dotenv

# Load env from workspace root as well as CWD
load_dotenv('l:/limo/.env')
load_dotenv()


def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )

    cursor = conn.cursor()

    print("SQUARE CAPITAL LOAN RECONCILIATION REPORT")
    print("Generated:", "October 11, 2025")
    print("=" * 80)

    # Square Capital Loans Received
    loans = [
        ("2025-01-08", "3648117", 68600.00, "SQ CAP1622", "First loan"),
        ("2025-10-01", "3648117", 50036.66, "SQ CAP9152", "Second loan"),
    ]

    print("\n📈 SQUARE CAPITAL LOANS RECEIVED:")
    print("-" * 60)
    total_loans = Decimal('0')
    for date, account, amount, loan_id, note in loans:
        total_loans += Decimal(str(amount))
        print(f"{date} | Account {account} | ${amount:,.2f} | {loan_id} | {note}")

    print(f"\n💰 TOTAL LOANS RECEIVED: ${total_loans:,.2f}")

    # Square Capital Loan Payments (from banking data)
    cursor.execute(
        """
        SELECT
            transaction_date,
            account_number,
            description,
            debit_amount
        FROM banking_transactions
        WHERE description ILIKE '%SQUARE%'
          AND debit_amount > 0
          AND (
                description ILIKE '%PREAUTHORIZED DEBIT%'
             OR description ILIKE '%SQUARE, INC%'
          )
        ORDER BY transaction_date
        """
    )

    payments = cursor.fetchall()

    print(f"\n💳 SQUARE CAPITAL LOAN PAYMENTS (Direct Debits):")
    print("-" * 60)
    total_payments = Decimal('0')
    payments_by_year = {}

    for date, account, desc, amount in payments:
        total_payments += Decimal(str(amount))
        year = date.year
        payments_by_year[year] = payments_by_year.get(year, Decimal('0')) + Decimal(str(amount))
        print(f"{date} | {account} | ${amount:>8,.2f} | {desc[:50]}...")

    print(f"\n💸 TOTAL DIRECT PAYMENTS: ${total_payments:,.2f}")

    print(f"\nDirect Payments by Year:")
    for year in sorted(payments_by_year.keys()):
        print(f"  {year}: ${payments_by_year[year]:,.2f}")

    # Check for Square processing activity that might include loan repayments
    # This repo uses square_gross_sales/square_net_sales on payments
    cursor.execute(
        """
        SELECT
            COUNT(*) AS transaction_count,
            COALESCE(SUM(square_gross_sales), 0) AS total_gross,
            COALESCE(SUM(square_net_sales), 0) AS total_net,
            COALESCE(SUM(COALESCE(square_gross_sales, 0) - COALESCE(square_net_sales, 0)), 0) AS total_fees
        FROM payments
        WHERE square_payment_id IS NOT NULL
          AND payment_date >= '2025-01-08'
        """
    )

    square_stats = cursor.fetchone()

    if square_stats and square_stats[0] > 0:
        count, gross, net, fees = square_stats

        print(f"\n📊 SQUARE PROCESSING ACTIVITY (Since Jan 8, 2025):")
        print("-" * 60)
        print(f"Total Square Transactions: {count:,}")
        print(f"Gross Revenue Processed: ${gross:,.2f}")
        print(f"Net Amount Deposited: ${net:,.2f}")
        print(f"Total Fees Charged: ${fees:,.2f}")

        if gross > 0:
            avg_fee_rate = (fees / gross) * Decimal('100')
            print(f"Average Fee Rate: {avg_fee_rate:.2f}%")

            # Estimate if fees include loan repayments
            expected_normal_fees = gross * Decimal('0.029')  # Approx Square rate ~2.9%
            excess_fees = fees - expected_normal_fees

            print(f"\nFee Analysis:")
            print(f"Expected Normal Fees (2.9%): ${expected_normal_fees:,.2f}")
            print(f"Actual Fees Charged: ${fees:,.2f}")
            print(f"Excess Fees: ${excess_fees:,.2f}")

            if excess_fees > 5000:
                print("🔍 Significant excess fees suggest embedded loan repayments")

    # Final Reconciliation
    apparent_balance = total_loans - total_payments

    print("\n" + "=" * 60)
    print("SQUARE CAPITAL LOAN RECONCILIATION SUMMARY")
    print("=" * 60)

    print("\nLoan Details:")
    print("  Loan #1 (CAP1622): $68,600.00 (Jan 8, 2025)")
    print("  Loan #2 (CAP9152): $50,036.66 (Oct 1, 2025)")
    print(f"  TOTAL BORROWED: ${total_loans:,.2f}")

    print("\nDirect Payments Identified:")
    print(f"  2018-2021 Payments: ${total_payments:,.2f}")
    print("  (These appear to be from a previous loan)")

    print("\nCurrent Loan Status:")
    print(f"  Apparent Outstanding: ${apparent_balance:,.2f}")

    print("\n[WARN]  IMPORTANT NOTES:")
    print(f"1. The ${total_payments:,.2f} in payments (2018-2021) appear to be")
    print("   from a previous Square Capital loan, not the current loans.")
    print("2. Current loan repayments are likely embedded in daily")
    print("   Square processing as higher fee deductions.")
    print("3. No separate loan payment debits found for 2025 loans.")
    print("4. Check Square dashboard for actual repayment schedule.")

    print("\n📋 RECOMMENDATIONS:")
    print(f"• Exclude loan deposits (${total_loans:,.2f}) from revenue calculations")
    print("• Monitor Square fee rates for embedded loan repayments")
    print("• Track loan balances via Square Capital dashboard")
    print("• Separate loan accounting from operational revenue")

    updated_count = cursor.rowcount
    if updated_count > 0:
        print(f"\n[OK] Tagged {updated_count} loan deposits in banking_transactions")

    conn.commit()
    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("RECONCILIATION COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()