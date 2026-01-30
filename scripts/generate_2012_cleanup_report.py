"""
Generate comprehensive report of 2012 duplicate cleanup.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print('='*70)
    print('2012 DUPLICATE CLEANUP REPORT')
    print('='*70)
    print(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()
    
    # Check backup tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%excel_duplicates_backup%'
        ORDER BY table_name DESC
    """)
    backups = cur.fetchall()
    
    print('BACKUP TABLES CREATED:')
    print('-'*70)
    for backup in backups:
        backup_name = backup[0]
        cur.execute(f"SELECT COUNT(*), SUM(gross_amount) FROM {backup_name}")
        count, total = cur.fetchone()
        print(f'  {backup_name}')
        print(f'    Receipts backed up: {count}')
        print(f'    Total amount: ${total:,.2f}' if total else '    Total amount: $0.00')
    print()
    
    # Current 2012 receipt status
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            SUM(gross_amount) as total_amount,
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    """)
    
    total, amount, earliest, latest = cur.fetchone()
    
    print('CURRENT 2012 RECEIPTS STATUS:')
    print('-'*70)
    print(f'  Total receipts: {total:,}')
    print(f'  Total amount: ${amount:,.2f}')
    print(f'  Date range: {earliest} to {latest}')
    print()
    
    # Banking coverage
    cur.execute("""
        SELECT 
            COUNT(*) as total_debits,
            SUM(debit_amount) as total_debit_amount
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        AND debit_amount > 0
    """)
    
    debits, debit_amount = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(DISTINCT bt.transaction_id)
        FROM banking_transactions bt
        JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id
        WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
        AND bt.debit_amount > 0
    """)
    
    matched_debits = cur.fetchone()[0]
    
    print('BANKING TRANSACTION COVERAGE:')
    print('-'*70)
    print(f'  Total 2012 banking debits: {debits:,}')
    print(f'  Total debit amount: ${debit_amount:,.2f}')
    print(f'  Matched to receipts: {matched_debits:,}')
    print(f'  Coverage: {matched_debits/debits*100:.1f}%')
    print()
    
    # Category breakdown
    cur.execute("""
        SELECT 
            COALESCE(category, 'uncategorized') as cat,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        GROUP BY category
        ORDER BY total DESC
    """)
    
    categories = cur.fetchall()
    
    print('RECEIPT CATEGORY BREAKDOWN:')
    print('-'*70)
    for cat, count, total in categories:
        pct = count / total * 100 if total else 0
        print(f'  {cat:25s}: {count:4d} receipts  ${total:>12,.2f}')
    print()
    
    # Cleanup impact calculation
    print('CLEANUP IMPACT:')
    print('-'*70)
    
    total_backed_up = 0
    total_backed_up_amount = 0
    for backup in backups:
        backup_name = backup[0]
        cur.execute(f"SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM {backup_name}")
        count, amount = cur.fetchone()
        total_backed_up += count
        total_backed_up_amount += amount or 0
    
    print(f'  Total duplicates removed: {total_backed_up:,}')
    print(f'  Total amount of duplicates: ${total_backed_up_amount:,.2f}')
    print(f'  Current clean receipts: {total:,}')
    print(f'  Reduction: {total_backed_up/(total+total_backed_up)*100:.1f}%')
    print()
    
    print('='*70)
    print('CLEANUP COMPLETE ✓')
    print('='*70)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
