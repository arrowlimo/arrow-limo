import os
import psycopg2
import psycopg2.extras

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    print("="*80)
    print("SCOTIA BANK DATA STATUS CHECK")
    print("="*80)

    # Check for Scotia Bank transactions by bank_id
    cur.execute("""
        SELECT bank_id, account_number, COUNT(*), 
               MIN(transaction_date), MAX(transaction_date),
               array_agg(DISTINCT source_file) as sources
        FROM banking_transactions
        WHERE bank_id = 2 OR account_number ILIKE '%903990%' OR account_number ILIKE '%scotia%'
        GROUP BY bank_id, account_number
        ORDER BY COUNT(*) DESC
    """)
    
    results = cur.fetchall()
    
    if not results:
        print("\n⚠️  NO SCOTIA BANK DATA FOUND")
        print("\nChecking all bank accounts...")
        cur.execute("""
            SELECT bank_id, account_number, COUNT(*)
            FROM banking_transactions
            GROUP BY bank_id, account_number
            ORDER BY bank_id, COUNT(*) DESC
        """)
        for bid, acc, cnt in cur.fetchall():
            print(f"  bank_id={bid}, account={acc}: {cnt:,} transactions")
        conn.close()
        return
    
    print(f"\nFound Scotia Bank data:")
    for r in results:
        print(f"\n  Bank ID: {r['bank_id']}")
        print(f"  Account: {r['account_number']}")
        print(f"  Count: {r['count']:,}")
        print(f"  Date range: {r['min']} to {r['max']}")
        print(f"  Source files: {r['sources']}")
        
        # Check yearly breakdown
        cur.execute("""
            SELECT EXTRACT(YEAR FROM transaction_date) as year, COUNT(*)
            FROM banking_transactions
            WHERE bank_id = %s AND account_number = %s
            GROUP BY year
            ORDER BY year
        """, (r['bank_id'], r['account_number']))
        
        print(f"  By Year:")
        for year, cnt in cur.fetchall():
            print(f"    {int(year)}: {cnt:,}")
    
    # Check for receipts linked to Scotia
    cur.execute("""
        SELECT COUNT(DISTINCT r.receipt_id) as receipt_count,
               SUM(r.gross_amount) as total_amount
        FROM receipts r
        WHERE r.mapped_bank_account_id = 2
           OR EXISTS (
               SELECT 1 FROM banking_transactions bt
               WHERE bt.transaction_id = r.banking_transaction_id
                 AND bt.bank_id = 2
           )
    """)
    
    r_count, r_amount = cur.fetchone()
    print(f"\n  Receipts linked to Scotia: {r_count:,} (${float(r_amount or 0):,.2f})")

    conn.close()


if __name__ == "__main__":
    main()
