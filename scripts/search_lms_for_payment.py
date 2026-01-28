"""
Search LMS Payment table directly for $1,604.85 payment on Jan 4, 2013
and any references to Gordon Deans or Cal Red Technical Consulting.
"""
import pyodbc
from datetime import datetime, timedelta

LMS_PATH = r'L:\New folder\lms.mdb'

def search_lms():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    print("=" * 80)
    print("SEARCHING LMS FOR: $1,604.85 payment on/near Jan 4, 2013")
    print("=" * 80)
    
    # Search for exact amount on date
    target_date = datetime(2013, 1, 4)
    start_date = target_date - timedelta(days=3)
    end_date = target_date + timedelta(days=3)
    
    cur.execute("""
        SELECT PaymentID, [Account_No], Reserve_No, Amount, LastUpdated, LastUpdatedBy
        FROM Payment
        WHERE Amount = 1604.85
        AND LastUpdated BETWEEN ? AND ?
        ORDER BY LastUpdated
    """, (start_date, end_date))
    
    exact = cur.fetchall()
    if exact:
        print(f"\n✓ Found {len(exact)} exact matches for $1,604.85 on/near {target_date.date()}:")
        for row in exact:
            print(f"  PaymentID: {row.PaymentID}, Account: {row.Account_No}, Reserve: {row.Reserve_No}")
            print(f"    Amount: ${row.Amount:,.2f}, Date: {row.LastUpdated}, By: {row.LastUpdatedBy}")
    else:
        print(f"\n✗ No exact matches for $1,604.85 on/near {target_date.date()}")
    
    # Search for amount anywhere in 2013
    cur.execute("""
        SELECT PaymentID, [Account_No], Reserve_No, Amount, LastUpdated, LastUpdatedBy
        FROM Payment
        WHERE Amount = 1604.85
        AND YEAR(LastUpdated) = 2013
        ORDER BY LastUpdated
    """)
    
    yr_matches = cur.fetchall()
    if yr_matches:
        print(f"\n✓ Found {len(yr_matches)} matches for $1,604.85 anywhere in 2013:")
        for row in yr_matches:
            print(f"  PaymentID: {row.PaymentID}, Account: {row.Account_No}, Reserve: {row.Reserve_No}")
            print(f"    Amount: ${row.Amount:,.2f}, Date: {row.LastUpdated}, By: {row.LastUpdatedBy}")
    else:
        print(f"\n✗ No matches for $1,604.85 in 2013")
    
    # Near matches
    cur.execute("""
        SELECT PaymentID, [Account_No], Reserve_No, Amount, LastUpdated, LastUpdatedBy
        FROM Payment
        WHERE Amount BETWEEN 1603.85 AND 1605.85
        AND LastUpdated BETWEEN ? AND ?
        ORDER BY ABS(Amount - 1604.85), LastUpdated
    """, (start_date, end_date))
    
    near = cur.fetchall()
    if near:
        print(f"\n~ Found {len(near)} near matches (±$1.00) on/near {target_date.date()}:")
        for row in near:
            diff = row.Amount - 1604.85
            print(f"  PaymentID: {row.PaymentID}, Account: {row.Account_No}, Reserve: {row.Reserve_No}")
            print(f"    Amount: ${row.Amount:,.2f} (diff: ${diff:+.2f}), Date: {row.LastUpdated}")
    else:
        print(f"\n✗ No near matches (±$1.00) on/near {target_date.date()}")
    
    print("\n" + "=" * 80)
    print("SEARCHING LMS RESERVE TABLE FOR: Gordon Deans")
    print("=" * 80)
    
    # Search Reserve table for Gordon Deans
    cur.execute("""
        SELECT Reserve_No, [Account_No], Name, PU_Date, Rate, Balance
        FROM Reserve
        WHERE Name LIKE '%Gordon%' AND Name LIKE '%Deans%'
        ORDER BY PU_Date DESC
    """)
    
    gordon_reserves = cur.fetchall()
    if gordon_reserves:
        print(f"\n✓ Found {len(gordon_reserves)} reserves for Gordon Deans:")
        for row in gordon_reserves:
            print(f"  Reserve: {row.Reserve_No}, Account: {row.Account_No}, Name: {row.Name}")
            print(f"    Date: {row.PU_Date}, Rate: ${row.Rate:,.2f}, Balance: ${row.Balance:,.2f}")
    else:
        print("\n✗ No reserves found for Gordon Deans")
    
    # Search for Cal Red
    cur.execute("""
        SELECT Reserve_No, [Account_No], Name, PU_Date, Rate, Balance
        FROM Reserve
        WHERE Name LIKE '%Cal%Red%'
        ORDER BY PU_Date DESC
    """)
    
    cal_reserves = cur.fetchall()
    if cal_reserves:
        print(f"\n✓ Found {len(cal_reserves)} reserves for Cal Red:")
        for row in cal_reserves:
            print(f"  Reserve: {row.Reserve_No}, Account: {row.Account_No}, Name: {row.Name}")
            print(f"    Date: {row.PU_Date}, Rate: ${row.Rate:,.2f}, Balance: ${row.Balance:,.2f}")
    else:
        print("\n✗ No reserves found for Cal Red")
    
    # Check if Gordon appears anywhere in Account_No field
    cur.execute("""
        SELECT DISTINCT [Account_No], Name
        FROM Reserve
        WHERE [Account_No] LIKE '%Gordon%'
        OR Name LIKE '%Gordon%'
        ORDER BY Name
    """)
    
    gordon_any = cur.fetchall()
    if gordon_any:
        print(f"\n✓ Found {len(gordon_any)} unique accounts/names containing 'Gordon':")
        for row in gordon_any:
            print(f"  Account: {row.Account_No}, Name: {row.Name}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    search_lms()
