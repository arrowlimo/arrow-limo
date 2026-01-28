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
        
        # The statement shows:
        # Account: 5457-4994-2077-9853
        # Period: Jan 21 - Feb 20, 2012
        # New Balance: $2,653.56
        # Previous Balance: $2,532.28
        # Payments: $500
        # Transactions total: $548.41
        # Interest: $42.87
        
        print("=== CAPITAL ONE MASTERCARD 9853 (Jan-Feb 2012) ===\n")
        
        # 1. Check journal table for Capital One account 2300
        print("1. JOURNAL ENTRIES - Capital One Mastercard 9853 account:")
        cur.execute("""
            SELECT "Date", "Type", "Num", "Name", "Memo/Description", "Account", "Debit", "Credit"
            FROM journal
            WHERE "Account" ILIKE '%2300%'
               OR "Account" ILIKE '%capital%one%'
               OR "Account" ILIKE '%9853%'
            ORDER BY "Date"
            LIMIT 50
        """)
        rows = cur.fetchall()
        if rows:
            print(f"   Found {len(rows)} entries")
            for r in rows[:20]:
                dt = r.get('Date', '')
                typ = r.get('Type', '')
                name = r.get('Name', '')
                acct = r.get('Account', '')
                debit = r.get('Debit', 0) or 0
                credit = r.get('Credit', 0) or 0
                print(f"   {dt} | {typ:20} | {name:30} | Debit: ${debit:>10.2f} Credit: ${credit:>10.2f}")
        else:
            print("   (none found)")
        
        # 2. Check for specific transactions from statement
        print("\n2. SPECIFIC TRANSACTIONS FROM STATEMENT (Jan 21 - Feb 20, 2012):")
        print("   Looking for: Excalibur ($217.18), MGM Grand Hotel ($91.93 x2), Finance Charges ($42.87 + $29.00)")
        
        cur.execute("""
            SELECT "Date", "Type", "Num", "Name", "Memo/Description", "Account", "Debit", "Credit"
            FROM journal
            WHERE "Date" BETWEEN '2012-01-21' AND '2012-02-20'
              AND ("Account" ILIKE '%2300%' OR "Account" ILIKE '%capital%one%')
            ORDER BY "Date"
        """)
        rows = cur.fetchall()
        if rows:
            print(f"   Found {len(rows)} transactions:")
            for r in rows:
                dt = r.get('Date', '')
                name = r.get('Name', '')
                memo = r.get('Memo/Description', '')
                credit = r.get('Credit', 0) or 0
                print(f"   {dt} | {name:30} | ${credit:>8.2f} | {memo}")
        else:
            print("   (none found)")
        
        # 3. Check for $500 payment
        print("\n3. $500 PAYMENT AROUND FEB 8, 2012:")
        cur.execute("""
            SELECT "Date", "Type", "Num", "Name", "Memo/Description", "Account", "Debit", "Credit"
            FROM journal
            WHERE "Date" BETWEEN '2012-02-01' AND '2012-02-15'
              AND (
                  ("Name" ILIKE '%capital%one%' AND ABS(COALESCE("Credit", 0) - 500) < 1)
                  OR ("Memo/Description" ILIKE '%5457%5676%3437%4347%' AND ABS(COALESCE("Credit", 0) - 500) < 1)
              )
            ORDER BY "Date"
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                dt = r.get('Date', '')
                typ = r.get('Type', '')
                name = r.get('Name', '')
                memo = r.get('Memo/Description', '')
                acct = r.get('Account', '')
                credit = r.get('Credit', 0) or 0
                print(f"   {dt} | {typ:15} | {name:20} | ${credit:>8.2f} | {acct}")
                print(f"        Memo: {memo}")
        else:
            print("   (payment not found)")
        
        # 4. Check for balance around $2,653.56
        print("\n4. BALANCE VERIFICATION ($2,653.56 around Feb 20, 2012):")
        cur.execute("""
            SELECT "Date", "Type", "Num", "Name", "Memo/Description", "Account", "Debit", "Credit", "Balance"
            FROM journal
            WHERE "Date" BETWEEN '2012-02-15' AND '2012-02-25'
              AND ("Account" ILIKE '%2300%' OR "Account" ILIKE '%capital%one%')
              AND "Balance" IS NOT NULL
              AND ABS(COALESCE("Balance", 0) - 2653.56) < 100
            ORDER BY "Date"
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                dt = r.get('Date', '')
                bal = r.get('Balance', 0) or 0
                print(f"   {dt} | Balance: ${bal:>10.2f}")
        else:
            print("   (balance record not found - may not be tracked in journal)")
        
        # 5. Summary of all Capital One entries in Feb 2012
        print("\n5. SUMMARY - ALL CAPITAL ONE ENTRIES FEB 2012:")
        cur.execute("""
            SELECT 
                COUNT(*) as entry_count,
                SUM(COALESCE("Debit", 0)) as total_debits,
                SUM(COALESCE("Credit", 0)) as total_credits
            FROM journal
            WHERE "Date" >= '2012-02-01' AND "Date" < '2012-03-01'
              AND ("Account" ILIKE '%2300%' OR "Account" ILIKE '%capital%one%' OR "Account" ILIKE '%9853%')
        """)
        row = cur.fetchone()
        if row:
            print(f"   Total entries: {row['entry_count']}")
            print(f"   Total debits:  ${row['total_debits']:.2f}")
            print(f"   Total credits: ${row['total_credits']:.2f}")
        
        # 6. Check if PDF exists
        print("\n6. PDF FILE STATUS:")
        pdf_path = r"L:\limo\pdf\2012 merchant statement capital one 5457-4994-2077-9853_ocred.pdf"
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"   ✓ PDF EXISTS: {pdf_path}")
            print(f"     Size: {size:,} bytes")
        else:
            print(f"   ✗ PDF NOT FOUND at expected location")
        
        cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
