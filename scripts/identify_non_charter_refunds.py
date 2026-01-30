#!/usr/bin/env python3
"""
Identify and flag non-charter refunds (business expenses, not customer refunds)

These are QuickBooks transactions incorrectly imported as "refunds":
- Workers Comp payments
- Utility bills (TELUS, etc.)
- General business cheques
- Bill payments to vendors
"""
import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Identify non-charter refunds')
    parser.add_argument('--write', action='store_true', help='Create exclusion table and flag records')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("IDENTIFYING NON-CHARTER REFUNDS")
    print("="*80)
    
    # Patterns that indicate business expenses, not charter refunds
    business_expense_patterns = [
        ("Workers Comp", "WORKERS COMP|WCB"),
        ("Payroll", "PAYROLL|WAGES"),
        ("Utilities", "TELUS|SASKTEL|POWER|WATER|GAS|UTILITIES"),
        ("Insurance", "INSURANCE|AVIVA|SGI"),
        ("Vehicle Expenses", "VEHICLE|AUTO|CAR|FUEL|OIL"),
        ("Bill Payments", "BILL PAYMENT|BR BILL"),
        ("Office Expenses", "OFFICE|SUPPLIES|STATIONARY"),
        ("Bank Charges", "BANK CHARGE|SERVICE FEE|NSF"),
        ("Cheques", "^QBO Import: Cheque"),
        ("Debit Memos", "DEBIT MEMO"),
        ("Adjustments", "ADJUSTMENT OTHER"),
    ]
    
    print("\n🔍 Analyzing unlinked refunds for business expense patterns...\n")
    
    total_flagged = 0
    total_amount = 0
    
    for category, pattern in business_expense_patterns:
        cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM charter_refunds
            WHERE reserve_number IS NULL
            AND description ~* %s
        """, (pattern,))
        
        count, amount = cur.fetchone()
        if count and count > 0:
            total_flagged += count
            total_amount += (amount or 0)
            print(f"  {category}: {count:,} records = ${amount:,.2f}")
            
            # Show examples
            cur.execute("""
                SELECT id, refund_date, amount, description
                FROM charter_refunds
                WHERE reserve_number IS NULL
                AND description ~* %s
                ORDER BY amount DESC
                LIMIT 3
            """, (pattern,))
            
            for refund_id, date, amt, desc in cur.fetchall():
                desc_short = desc[:70] if desc else ""
                print(f"      #{refund_id}: ${amt:,.2f} on {date} - {desc_short}")
    
    # Check for duplicates (same date + amount from QBO import)
    print("\n🔍 Checking for duplicate QBO imports...")
    cur.execute("""
        SELECT refund_date, amount, description, COUNT(*) as dup_count
        FROM charter_refunds
        WHERE reserve_number IS NULL
        AND source_file LIKE '%QBO%'
        GROUP BY refund_date, amount, description
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, amount DESC
        LIMIT 10
    """)
    
    duplicates = cur.fetchall()
    if duplicates:
        print(f"\nFound {len(duplicates)} sets of duplicate QBO imports:")
        for date, amount, desc, dup_count in duplicates:
            desc_short = desc[:60] if desc else ""
            print(f"  {dup_count}x ${amount:,.2f} on {date} - {desc_short}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE reserve_number IS NULL")
    total_unlinked, total_unlinked_amt = cur.fetchone()
    
    print(f"\nTotal unlinked refunds: {total_unlinked:,} = ${total_unlinked_amt:,.2f}")
    print(f"Business expenses flagged: {total_flagged:,} = ${total_amount:,.2f}")
    print(f"Percentage: {total_flagged/total_unlinked*100:.1f}% of unlinked are business expenses")
    
    remaining = total_unlinked - total_flagged
    remaining_amt = total_unlinked_amt - total_amount
    print(f"\nRemaining true charter refunds: {remaining:,} = ${remaining_amt:,.2f}")
    
    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print("""
These unlinked "refunds" are actually business expenses from QuickBooks.
They should be:
1. Removed from charter_refunds table, OR
2. Moved to a separate table (business_expenses), OR  
3. Flagged with is_business_expense = TRUE column

The charter_refunds table should ONLY contain actual customer refunds.

Next steps:
1. Create business_expenses table
2. Move these records from charter_refunds to business_expenses
3. Re-run linkage analysis to see true charter refund linkage rate
""")
    
    if args.write:
        print("\n[WARN]  WRITE mode not implemented yet.")
        print("Need to decide: DELETE, MOVE, or FLAG these records?")
    else:
        print("\n[DRY RUN] Use --write once we decide how to handle these records")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
