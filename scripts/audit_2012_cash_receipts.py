#!/usr/bin/env python3
"""
Audit 2012 cash receipt coverage to identify missing entries.

Analyzes:
- Receipt counts by source (banking-linked, employee-linked, vehicle-linked, manual)
- Cash/withdrawal patterns in banking vs receipts entered
- Monthly coverage gaps
- Vendor patterns for cash vs card transactions
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )

def main():
    conn = connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("2012 CASH RECEIPT COVERAGE AUDIT")
    print("=" * 80)

    # Total receipts in 2012
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            SUM(gross_amount) as total_amount,
            COUNT(DISTINCT vendor_name) as unique_vendors
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
    """)
    totals = cur.fetchone()
    print(f"\n=== 2012 Receipts Overview ===")
    print(f"Total receipts: {totals['total_receipts']:,}")
    print(f"Total amount: ${totals['total_amount']:,.2f}" if totals['total_amount'] else "Total amount: $0.00")
    print(f"Unique vendors: {totals['unique_vendors']:,}")

    # Receipts by source linkage
    cur.execute("""
        SELECT 
            CASE 
                WHEN created_from_banking = true THEN 'Banking-linked'
                WHEN vehicle_id IS NOT NULL THEN 'Vehicle-linked'
                ELSE 'Manual/Unlinked'
            END as source_type,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY source_type
        ORDER BY receipt_count DESC
    """)
    print(f"\n=== Receipts by Source Type ===")
    for row in cur.fetchall():
        print(f"{row['source_type']:20s}: {row['receipt_count']:6,} receipts, ${row['total_amount']:12,.2f}" if row['total_amount'] else f"{row['source_type']:20s}: {row['receipt_count']:6,} receipts, $0.00")

    # Monthly breakdown
    cur.execute("""
        SELECT 
            TO_CHAR(receipt_date, 'YYYY-MM') as month,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount,
            COUNT(CASE WHEN created_from_banking = true THEN 1 END) as banking_linked,
            COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = false THEN 1 END) as manual_entries
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
        GROUP BY month
        ORDER BY month
    """)
    print(f"\n=== Monthly Receipt Coverage ===")
    print(f"{'Month':<10} {'Count':>7} {'Amount':>14} {'Banking':>10} {'Manual':>10}")
    print("-" * 60)
    for row in cur.fetchall():
        amt = f"${row['total_amount']:,.2f}" if row['total_amount'] else "$0.00"
        print(f"{row['month']:<10} {row['receipt_count']:>7,} {amt:>14} {row['banking_linked']:>10,} {row['manual_entries']:>10,}")

    # Banking transactions in 2012 (withdrawals/cash)
    cur.execute("""
        SELECT 
            COUNT(*) as withdrawal_count,
            SUM(debit_amount) as total_withdrawn
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND category = 'withdrawal'
    """)
    withdrawals = cur.fetchone()
    print(f"\n=== Banking Withdrawals (Cash Source) ===")
    print(f"Withdrawal transactions: {withdrawals['withdrawal_count']:,}" if withdrawals['withdrawal_count'] else "Withdrawal transactions: 0")
    print(f"Total withdrawn: ${withdrawals['total_withdrawn']:,.2f}" if withdrawals['total_withdrawn'] else "Total withdrawn: $0.00")

    # POS vs non-POS in 2012
    cur.execute("""
        SELECT 
            COUNT(*) as pos_count,
            SUM(debit_amount) as pos_total
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND category = 'pos_purchase'
    """)
    pos = cur.fetchone()
    print(f"\n=== POS Purchases (Card Transactions) ===")
    print(f"POS transactions: {pos['pos_count']:,}" if pos['pos_count'] else "POS transactions: 0")
    print(f"POS total: ${pos['pos_total']:,.2f}" if pos['pos_total'] else "POS total: $0.00")

    # Receipts with no banking link (likely cash)
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (created_from_banking IS NULL OR created_from_banking = false)
        GROUP BY category
        ORDER BY receipt_count DESC
        LIMIT 15
    """)
    print(f"\n=== Top Categories for Unlinked (Cash?) Receipts ===")
    print(f"{'Category':<30} {'Count':>7} {'Amount':>14}")
    print("-" * 60)
    for row in cur.fetchall():
        amt = f"${row['total_amount']:,.2f}" if row['total_amount'] else "$0.00"
        cat = row['category'] or '(null)'
        print(f"{cat:<30} {row['receipt_count']:>7,} {amt:>14}")

    # Sample of vendors with unlinked receipts
    cur.execute("""
        SELECT 
            vendor_name,
            COUNT(*) as receipt_count,
            SUM(gross_amount) as total_amount,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (created_from_banking IS NULL OR created_from_banking = false)
          AND vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY receipt_count DESC
        LIMIT 20
    """)
    print(f"\n=== Top Vendors with Unlinked (Cash?) Receipts ===")
    print(f"{'Vendor':<40} {'Count':>7} {'Amount':>14} {'Date Range':<20}")
    print("-" * 90)
    for row in cur.fetchall():
        amt = f"${row['total_amount']:,.2f}" if row['total_amount'] else "$0.00"
        date_range = f"{row['first_date']} to {row['last_date']}"
        vendor = (row['vendor_name'][:37] + '...') if len(row['vendor_name']) > 40 else row['vendor_name']
        print(f"{vendor:<40} {row['receipt_count']:>7,} {amt:>14} {date_range:<20}")

    # Check for patterns: liquor stores (often cash)
    cur.execute("""
        SELECT 
            COUNT(*) as liquor_receipts,
            SUM(gross_amount) as liquor_total,
            COUNT(CASE WHEN created_from_banking = true THEN 1 END) as linked,
            COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = false THEN 1 END) as unlinked
        FROM receipts
        WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (
               LOWER(vendor_name) LIKE '%liquor%'
            OR LOWER(vendor_name) LIKE '%beer%'
            OR LOWER(vendor_name) LIKE '%wine%'
          )
    """)
    liquor = cur.fetchone()
    print(f"\n=== Liquor Store Receipts (Hospitality Supplies) ===")
    print(f"Total liquor receipts: {liquor['liquor_receipts']:,}")
    print(f"Total amount: ${liquor['liquor_total']:,.2f}" if liquor['liquor_total'] else "Total amount: $0.00")
    print(f"Banking-linked: {liquor['linked']:,} ({liquor['linked']*100//liquor['liquor_receipts'] if liquor['liquor_receipts'] else 0}%)")
    print(f"Unlinked (cash?): {liquor['unlinked']:,} ({liquor['unlinked']*100//liquor['liquor_receipts'] if liquor['liquor_receipts'] else 0}%)")

    # Gap analysis: estimate missing cash receipts
    print(f"\n=== ESTIMATED MISSING CASH RECEIPTS ===")
    if withdrawals['total_withdrawn'] and totals['total_amount']:
        unlinked_receipts_amount = Decimal('0')
        cur.execute("""
            SELECT SUM(gross_amount) as unlinked_total
            FROM receipts
            WHERE receipt_date BETWEEN '2012-01-01' AND '2012-12-31'
              AND (created_from_banking IS NULL OR created_from_banking = false)
        """)
        result = cur.fetchone()
        unlinked_receipts_amount = result['unlinked_total'] or Decimal('0')
        
        print(f"Cash withdrawn from bank: ${withdrawals['total_withdrawn']:,.2f}")
        print(f"Unlinked receipts entered: ${unlinked_receipts_amount:,.2f}")
        if withdrawals['total_withdrawn'] > unlinked_receipts_amount:
            gap = withdrawals['total_withdrawn'] - unlinked_receipts_amount
            print(f"Potential missing receipts: ${gap:,.2f} ({gap*100/withdrawals['total_withdrawn']:.1f}% of withdrawals)")
        else:
            print("Note: Unlinked receipts exceed withdrawals (may include other payment methods)")

    # Check for December 2012 specifically
    cur.execute("""
        SELECT 
            COUNT(*) as dec_receipts,
            SUM(gross_amount) as dec_amount,
            COUNT(CASE WHEN created_from_banking IS NULL OR created_from_banking = false THEN 1 END) as dec_unlinked
        FROM receipts
        WHERE receipt_date BETWEEN '2012-12-01' AND '2012-12-31'
    """)
    dec = cur.fetchone()
    print(f"\n=== December 2012 Specific ===")
    print(f"Total receipts: {dec['dec_receipts']:,}")
    print(f"Total amount: ${dec['dec_amount']:,.2f}" if dec['dec_amount'] else "Total amount: $0.00")
    print(f"Unlinked (cash?): {dec['dec_unlinked']:,}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
