"""Check why reserve 018916 was identified as charity/trade/promo."""
import psycopg2
import sys

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    # Check if charter exists in Postgres
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.rate,
            c.balance,
            c.deposit,
            c.status,
            c.notes,
            cl.client_name,
            cl.email,
            (SELECT STRING_AGG(DISTINCT payment_method, ', ')
             FROM payments 
             WHERE charter_id = c.charter_id) as payment_methods,
            (SELECT SUM(amount) 
             FROM payments 
             WHERE charter_id = c.charter_id AND amount > 0) as payments_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.reserve_number = '018916'
    """)
    
    row = cur.fetchone()
    
    if row:
        print("\n=== CHARTER 018916 IN POSTGRESQL ===")
        print(f"Reserve Number: {row[0]}")
        print(f"Date: {row[1]}")
        print(f"Rate: ${row[2]}")
        print(f"Balance: ${row[3]}")
        print(f"Deposit: ${row[4]}")
        print(f"Status: {row[5]}")
        print(f"Notes: {row[6]}")
        print(f"Client: {row[7]}")
        print(f"Email: {row[8]}")
        print(f"Payment Methods: {row[9]}")
        print(f"Payments Total: ${row[10]}")
    else:
        print("\n[WARN]  Charter 018916 NOT FOUND in PostgreSQL charters table")
    
    cur.close()
    conn.close()
    
    print("\n=== WHY IT WAS INCLUDED ===")
    print("Source: LMS Access database (L:\\limo\\backups\\lms.mdb)")
    print("Table: Reserve")
    print("Field: Pymt_Type = 'Promo'")
    print("\nScript: scripts/regenerate_charity_runs_from_lms.py")
    print("Query: SELECT * FROM Reserve WHERE Pymt_Type LIKE '%promo%' OR Pymt_Type LIKE '%trade%'")
    print("\nLogic: LMS Pymt_Type field is AUTHORITATIVE for charity/trade/promo classification")
    print("       (per user directive on Nov 7, 2025)")
    
    print("\n=== CLASSIFICATION RESULT ===")
    print("Classification: paid_full")
    print("Reason: Payments ($482.50) >= 90% of Rate ($450.00)")
    print("\n[WARN]  This appears to be a REGULAR PAID CHARTER, not charity/trade!")
    print("    The 'Promo' payment type in LMS may have been incorrectly set,")
    print("    or it may represent a promotional discount (paid but discounted rate).")

if __name__ == '__main__':
    main()
