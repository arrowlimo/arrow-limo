import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    host = os.environ.get("DB_HOST", "localhost")
    name = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "***REMOVED***")
    port = int(os.environ.get("DB_PORT", "5432"))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def main():
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Find tables with capital/credit/card keywords
        print("=== TABLES WITH CAPITAL/CREDIT/CARD KEYWORDS ===")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND (table_name ILIKE '%capital%' 
                OR table_name ILIKE '%credit%' 
                OR table_name ILIKE '%card%')
            ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cur.fetchall()]
        for t in tables:
            print(f"  {t}")
        
        if not tables:
            print("  (none found)")
        
        # 2. Search receipts for Capital One
        print("\n=== RECEIPTS - CAPITAL ONE ===")
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
            FROM receipts
            WHERE vendor_name ILIKE '%capital%one%'
               OR description ILIKE '%capital%one%'
               OR vendor_name ILIKE '%9853%'
            ORDER BY receipt_date DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  {r['receipt_date']}: {r['vendor_name']} ${r['gross_amount']} - {r.get('description', '')[:50]}")
        else:
            print("  (none found)")
        
        # 3. Search banking_transactions for Capital One
        print("\n=== BANKING TRANSACTIONS - CAPITAL ONE ===")
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE description ILIKE '%capital%one%'
               OR description ILIKE '%9853%'
            ORDER BY transaction_date DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                debit = f"${r['debit_amount']}" if r['debit_amount'] else ""
                credit = f"${r['credit_amount']}" if r['credit_amount'] else ""
                print(f"  {r['transaction_date']}: {r['description'][:60]} | Debit: {debit} Credit: {credit}")
        else:
            print("  (none found)")
        
        # 4. Check journal for Capital One
        print("\n=== JOURNAL - CAPITAL ONE ===")
        cur.execute("""
            SELECT * FROM journal
            WHERE "Account" ILIKE '%capital%one%'
               OR "Memo/Description" ILIKE '%capital%one%'
               OR "Account" ILIKE '%9853%'
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  {r.get('Date')}: {r.get('Account', '')[:50]} - {r.get('Memo/Description', '')[:50]}")
        else:
            print("  (none found)")
        
        # 5. Search for $2,653.56 or $2653.56 around Feb 2012
        print("\n=== TRANSACTIONS AROUND $2,653.56 (Feb 2012) ===")
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN '2012-01-01' AND '2012-03-31'
              AND (
                  ABS(debit_amount - 2653.56) < 1 
                  OR ABS(credit_amount - 2653.56) < 1
              )
            ORDER BY transaction_date
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                debit = f"${r['debit_amount']}" if r['debit_amount'] else ""
                credit = f"${r['credit_amount']}" if r['credit_amount'] else ""
                print(f"  {r['transaction_date']}: {r['description'][:60]} | Debit: {debit} Credit: {credit}")
        else:
            print("  (none found)")
        
        # 6. Check for Mastercard references
        print("\n=== MASTERCARD REFERENCES ===")
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE description ILIKE '%mastercard%'
              AND transaction_date BETWEEN '2012-01-01' AND '2012-03-31'
            ORDER BY transaction_date
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                debit = f"${r['debit_amount']}" if r['debit_amount'] else ""
                credit = f"${r['credit_amount']}" if r['credit_amount'] else ""
                print(f"  {r['transaction_date']}: {r['description'][:60]} | Debit: {debit} Credit: {credit}")
        else:
            print("  (none found)")
        
        cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
