"""
Analyze LMS payments table for refund records that could link to charter_refunds.

Checks for:
1. Payments with 'refunded' flag or status
2. E-transfer payment types with refund indicators
3. Negative payment amounts (refunds)
4. Payment records that match unlinked charter_refunds by amount/date
"""

import pyodbc
import psycopg2
from datetime import datetime, timedelta

# LMS Connection
LMS_PATH = r'L:\oldlms.mdb'  # Use root oldlms.mdb (most recent)
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

# PostgreSQL Connection
def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def analyze_lms_payments_structure():
    """Examine LMS payments table structure."""
    print("=" * 80)
    print("LMS PAYMENTS TABLE STRUCTURE")
    print("=" * 80)
    
    lms_conn = pyodbc.connect(lms_conn_str)
    cur = lms_conn.cursor()
    
    # Get column information
    print("\nColumns in payments table:")
    columns = []
    for row in cur.columns(table='Payment'):
        columns.append(row.column_name)
        print(f"  - {row.column_name} ({row.type_name})")
    
    cur.close()
    lms_conn.close()
    
    return columns

def find_lms_refund_patterns():
    """Find payment records that might be refunds."""
    print("\n" + "=" * 80)
    print("LMS PAYMENT REFUND PATTERNS")
    print("=" * 80)
    
    lms_conn = pyodbc.connect(lms_conn_str)
    cur = lms_conn.cursor()
    
    # Check for different refund indicators
    patterns = [
        ("Negative amounts", "SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Amount < 0"),
        ("E-Transfer payments", "SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Pymt_Type LIKE '%transfer%'"),
        ("Check payments", "SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Pymt_Type LIKE '%check%'"),
        ("Cash payments", "SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Pymt_Type LIKE '%cash%'"),
        ("Credit card payments", "SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Pymt_Type LIKE '%credit%'"),
    ]
    
    for pattern_name, query in patterns:
        try:
            cur.execute(query)
            result = cur.fetchone()
            if result and result[0]:
                print(f"\n{pattern_name}:")
                print(f"  Count: {result[0]}")
                print(f"  Total: ${result[1]:,.2f}" if result[1] else "  Total: $0.00")
        except Exception as e:
            print(f"\n{pattern_name}: Error - {e}")
    
    # Sample some records
    print("\n" + "=" * 80)
    print("SAMPLE PAYMENT RECORDS (Recent)")
    print("=" * 80)
    
    try:
        cur.execute("""
            SELECT TOP 20 
                PaymentID, Account_No, Reserve_No, Amount, 
                Pymt_Type, LastUpdated, [Key]
            FROM Payment 
            ORDER BY LastUpdated DESC
        """)
        
        print(f"\n{'PaymentID':<12} {'Account':<10} {'Reserve':<10} {'Amount':<12} {'Type':<15} {'Date':<12} {'Key':<10}")
        print("-" * 90)
        
        for row in cur.fetchall():
            payment_id = row[0] or 'NULL'
            account = row[1] or 'NULL'
            reserve = row[2] or 'NULL'
            amount = f"${row[3]:,.2f}" if row[3] else "$0.00"
            pymt_type = row[4] or 'NULL'
            date = row[5].strftime('%Y-%m-%d') if row[5] else 'NULL'
            key = row[6] or 'NULL'
            
            print(f"{str(payment_id):<12} {str(account):<10} {str(reserve):<10} {amount:<12} {str(pymt_type):<15} {date:<12} {str(key):<10}")
    
    except Exception as e:
        print(f"Error fetching sample records: {e}")
    
    cur.close()
    lms_conn.close()

def compare_to_unlinked_refunds():
    """Compare LMS payments to unlinked charter_refunds by amount/date."""
    print("\n" + "=" * 80)
    print("COMPARING LMS PAYMENTS TO UNLINKED CHARTER_REFUNDS")
    print("=" * 80)
    
    # Get unlinked refunds from PostgreSQL
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    pg_cur.execute("""
        SELECT id, refund_date, amount, description, source_file
        FROM charter_refunds
        WHERE reserve_number IS NULL
        ORDER BY amount DESC
    """)
    
    unlinked = pg_cur.fetchall()
    print(f"\nFound {len(unlinked)} unlinked charter_refunds")
    
    if not unlinked:
        print("All refunds are linked!")
        pg_cur.close()
        pg_conn.close()
        return
    
    # Get LMS payments
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    lms_cur.execute("""
        SELECT PaymentID, Account_No, Reserve_No, Amount, 
               Pymt_Type, LastUpdated, [Key]
        FROM Payment
        WHERE Amount IS NOT NULL
        ORDER BY LastUpdated DESC
    """)
    
    lms_payments = lms_cur.fetchall()
    print(f"Loaded {len(lms_payments)} LMS payment records")
    
    # Match by amount (within $0.01) and date (within 30 days)
    print("\n" + "=" * 80)
    print("POTENTIAL MATCHES (Amount ±$0.01, Date ±30 days)")
    print("=" * 80)
    
    matches_found = 0
    
    for refund in unlinked:
        refund_id, refund_date, refund_amount, description, source_file = refund
        
        # Skip if no amount
        if not refund_amount:
            continue
        
        matches = []
        
        for lms_payment in lms_payments:
            payment_id, account, reserve, lms_amount, pymt_type, lms_date, key = lms_payment
            
            if not lms_amount or not lms_date:
                continue
            
            # Check amount match (within $0.01)
            amount_diff = abs(float(lms_amount) - float(refund_amount))
            if amount_diff > 0.01:
                continue
            
            # Check date match (within 30 days)
            date_diff = abs((lms_date - refund_date).days)
            if date_diff > 30:
                continue
            
            matches.append({
                'payment_id': payment_id,
                'account': account,
                'reserve': reserve,
                'amount': lms_amount,
                'type': pymt_type,
                'date': lms_date,
                'key': key,
                'amount_diff': amount_diff,
                'date_diff': date_diff
            })
        
        if matches:
            matches_found += 1
            print(f"\n{'=' * 80}")
            print(f"Refund #{refund_id}: ${refund_amount:,.2f} on {refund_date}")
            print(f"Source: {source_file}")
            print(f"Description: {description[:60]}")
            print(f"\nFound {len(matches)} potential LMS payment match(es):")
            
            for i, match in enumerate(matches[:5], 1):  # Show top 5
                print(f"\n  Match {i}:")
                print(f"    Payment ID: {match['payment_id']}")
                print(f"    Reserve No: {match['reserve']}")
                print(f"    Account: {match['account']}")
                print(f"    Amount: ${match['amount']:,.2f} (diff: ${match['amount_diff']:.2f})")
                print(f"    Date: {match['date']} (diff: {match['date_diff']} days)")
                print(f"    Type: {match['type']}")
                print(f"    Key: {match['key']}")
    
    print(f"\n{'=' * 80}")
    print(f"SUMMARY: Found potential matches for {matches_found} of {len(unlinked)} unlinked refunds")
    print("=" * 80)
    
    lms_cur.close()
    lms_conn.close()
    pg_cur.close()
    pg_conn.close()

def check_etransfer_refunds():
    """Specifically check for e-transfer payments that might be refunds."""
    print("\n" + "=" * 80)
    print("E-TRANSFER PAYMENT ANALYSIS")
    print("=" * 80)
    
    lms_conn = pyodbc.connect(lms_conn_str)
    cur = lms_conn.cursor()
    
    # Get all e-transfer payments
    try:
        cur.execute("""
            SELECT PaymentID, Account_No, Reserve_No, Amount, 
                   Pymt_Type, LastUpdated, [Key]
            FROM Payment 
            WHERE Pymt_Type LIKE '%transfer%'
            ORDER BY LastUpdated DESC
        """)
        
        etransfers = cur.fetchall()
        print(f"\nFound {len(etransfers)} e-transfer payment records in LMS")
        
        if etransfers:
            print(f"\n{'PaymentID':<12} {'Account':<10} {'Reserve':<10} {'Amount':<12} {'Type':<20} {'Date':<12}")
            print("-" * 85)
            
            total_amount = 0
            for row in etransfers[:20]:  # Show first 20
                payment_id = row[0] or 'NULL'
                account = row[1] or 'NULL'
                reserve = row[2] or 'NULL'
                amount = row[3] or 0
                pymt_type = row[4] or 'NULL'
                date = row[5].strftime('%Y-%m-%d') if row[5] else 'NULL'
                
                print(f"{str(payment_id):<12} {str(account):<10} {str(reserve):<10} ${amount:>10,.2f} {str(pymt_type):<20} {date:<12}")
                total_amount += amount
            
            if len(etransfers) > 20:
                print(f"\n... and {len(etransfers) - 20} more")
            
            print(f"\nTotal e-transfer amount (all): ${sum(row[3] or 0 for row in etransfers):,.2f}")
    
    except Exception as e:
        print(f"Error fetching e-transfer payments: {e}")
    
    cur.close()
    lms_conn.close()

if __name__ == '__main__':
    print("LMS REFUND PAYMENT ANALYSIS")
    print("Checking LMS payments table for refund records...")
    print()
    
    # 1. Analyze table structure
    columns = analyze_lms_payments_structure()
    
    # 2. Find refund patterns
    find_lms_refund_patterns()
    
    # 3. Check e-transfers specifically
    check_etransfer_refunds()
    
    # 4. Compare to unlinked charter_refunds
    compare_to_unlinked_refunds()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review potential matches above")
    print("2. Create script to apply linkages based on LMS reserve numbers")
    print("3. Check if any e-transfers match unlinked refund amounts")
