"""
FINAL SOLUTION: Restore from backups and fill balances correctly.
Step 1: Restore all years to their pre-calculation state (from backups)
Step 2: Fix balances year by year
"""
import psycopg2
from decimal import Decimal
import sys

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*100)
    print("RESTORE FROM BACKUPS and RECALCULATE")
    print("="*100)
    
    # Step 1: Restore all years from backups
    years_with_backups = [2012, 2013, 2014, 2015, 2016, 2017]
    
    print("\nStep 1: Restoring from backups...")
    print("-"*100)
    
    for year in years_with_backups:
        backup_table = f"banking_transactions_1615_backup_{year}"
        
        # Check if backup exists
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = %s
        """, (backup_table,))
        
        if cur.fetchone()[0] == 0:
            print(f"⚠️ {year}: No backup table found")
            continue
        
        # Delete current year data
        cur.execute("""
            DELETE FROM banking_transactions 
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = %s
        """, (year,))
        deleted = cur.rowcount
        
        # Restore from backup
        cur.execute(f"""
            INSERT INTO banking_transactions 
            SELECT * FROM {backup_table}
        """)
        inserted = cur.rowcount
        
        print(f"✅ {year}: Deleted {deleted}, restored {inserted} from backup")
    
    conn.commit()
    print("\n" + "="*100)
    print("Step 2: Verify restored data...")
    print("="*100)
    
    for year in years_with_backups:
        cur.execute("""
            SELECT COUNT(*),
                   COUNT(CASE WHEN balance IS NULL THEN 1 END) as nulls
            FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = %s
        """, (year,))
        
        total, nulls = cur.fetchone()
        print(f"{year}: {total} txns | {nulls} NULL balances")
    
    print("\n✅ Restore complete")
    print("\nNow run: python scripts/MASTER_fix_all_1615_balances_v2.py --write")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
