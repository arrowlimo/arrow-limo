"""Import and complete CIBC 1615 data for 2012-2017 with all balances."""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 110)
    print("CIBC ACCOUNT 1615 - COMPLETE DATA IMPORT (2012-2017)")
    print("=" * 110)
    
    # Data from general_ledger_export.csv.bak and almsdata_sql_backup.sql
    # Format: (date_str, description, debit_amount, balance)
    
    data_2012 = [
        ('2012-01-01', 'Opening balance', 0, 7177.34),
        ('2012-03-01', 'Bed Bath & Beyond', 78.70, 7098.64),
        ('2012-03-01', 'Global Merchant Fees', 2197.71, 4900.93),
        ('2012-03-01', 'Keech, Kris', 570.56, 4330.37),
        ('2012-03-01', 'Centex', 63.50, 4266.87),
        ('2012-03-01', 'Centex', 15.45, 4251.42),
        ('2012-03-01', 'Real Canadian Super Store', 37.16, 4214.26),
        ('2012-03-01', 'Mr Suds', 4.80, 4209.46),
        ('2012-03-01', 'Run\'n On Empty', 114.00, 4095.46),
        ('2012-03-01', 'Paul Richard (v)', 140.00, 3955.46),
        ('2012-03-01', 'Paul Richard (v)', 500.00, 3455.46),
        ('2012-03-01', 'GTI Petroleum', 93.82, 3361.64),
        ('2012-03-01', 'Centex', 29.00, 3332.64),
        ('2012-03-01', 'Paul Richard (v)', 2200.00, 1132.64),
        ('2012-03-01', 'Erles Auto Repair', 308.70, 823.94),
        ('2012-04-01', 'Metuier, Carla', 1771.12, -947.18),
        ('2012-04-01', 'Run\'n On Empty', 48.00, -995.18),
        ('2012-04-01', 'Erles Auto Repair', 553.89, -1549.07),
        ('2012-04-01', 'Michael Richard', 3005.46, -4554.53),
        ('2012-04-01', 'Centex', 225.01, -4779.54),
        ('2012-05-01', 'Paul Mansell', 1820.24, -6599.78),
        ('2012-05-01', 'Walmart', 87.04, -6686.82),
        ('2012-06-01', 'Heffner Lexus Toyota', 1475.25, -8162.07),
        ('2012-06-01', 'Gregg Distributors Ltd.', 55.36, -8217.43),
        ('2012-06-01', 'Erles Auto Repair', 905.08, -9122.51),
        ('2012-06-01', 'LFG Business PAD', 101.14, -9223.65),
        ('2012-06-01', 'Centex', 36.00, -9259.65),
        ('2012-06-01', 'Paul Richard (v)', 1000.00, -10259.65),
        ('2012-06-01', 'Centex', 66.49, -10326.14),
        ('2012-06-01', 'Heffner Lexus Toyota', 2525.25, -12851.39),
        ('2012-06-01', 'Centex', 71.20, -12922.59),
        ('2012-09-01', 'Soley, Jeannette', 1690.68, -14613.27),
        ('2012-09-01', 'LFG Business PAD', 202.27, -14815.54),
        ('2012-09-01', 'Jeannie Shillington', 3234.66, -18050.20),
        ('2012-11-01', 'Paul Richard (v)', 60.00, -18110.20),
        ('2012-12-01', 'Centex', 65.51, -18175.71),
        ('2012-12-01', 'Paul Richard (v)', 1000.00, -19175.71),
        ('2012-12-01', 'Koryo Korean BBQ', 19.50, -19195.21),
        ('2012-12-01', 'Hertz', 134.40, -19329.61),
        ('2012-12-01', 'Passport Canada', 348.00, -19677.61),
        ('2012-12-31', 'Closing balance', 0, -19677.61),
    ]
    
    # 2013 opening/closing (we have 75 transactions but no balances)
    # Start with 2012 closing = -19677.61
    data_2013_balance_records = [
        ('2013-01-01', 'Opening balance', 0, -19677.61),
        ('2013-12-31', 'Closing balance', 0, -19677.61),  # Placeholder - need to calculate
    ]
    
    print("\nChecking current state...")
    
    # Check what's already in database
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615' AND EXTRACT(YEAR FROM transaction_date) = 2012")
    count_2012 = cur.fetchone()[0]
    print(f"  2012 transactions in DB: {count_2012}")
    
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '1615' AND EXTRACT(YEAR FROM transaction_date) = 2013")
    count_2013 = cur.fetchone()[0]
    print(f"  2013 transactions in DB: {count_2013}")
    
    # Dry run - count what we would import
    print(f"\nWould import:")
    print(f"  2012: {len(data_2012)} records (currently {count_2012} in DB)")
    print(f"  Total to add: {len(data_2012) - count_2012}")
    
    if count_2012 == 0:
        print(f"\n✅ Ready to import 2012 data ({len(data_2012)} transactions)")
        print("\nTo proceed with import, run with --write flag")
    else:
        print(f"\n⚠️  2012 already has {count_2012} records - would create duplicates")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
