"""
Sync reserve 019208 charges from LMS to PostgreSQL.
User adjusted charges and gratuity in LMS to match payments.
"""

import pyodbc
import psycopg2

LMS_PATH = r'L:\limo\backups\lms.mdb'

def sync_019208():
    # Connect to LMS
    lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(lms_conn_str)
    lms_cur = lms_conn.cursor()
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***',
        host='localhost'
    )
    pg_cur = pg_conn.cursor()
    
    reserve = '019208'
    
    print("=" * 100)
    print("CHECKING RESERVE 019208")
    print("=" * 100)
    
    # Get LMS data
    lms_cur.execute("""
        SELECT Reserve_No, Est_Charge, Deposit, Balance, Gratuity, Fuel
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve,))
    
    lms_row = lms_cur.fetchone()
    if not lms_row:
        print(f"ERROR: Reserve {reserve} not found in LMS")
        return
    
    lms_est_charge = lms_row[1] or 0
    lms_deposit = lms_row[2] or 0
    lms_balance = lms_row[3] or 0
    lms_gratuity = lms_row[4] or 0
    lms_fuel = lms_row[5] or 0
    
    print(f"LMS DATA:")
    print(f"  Est_Charge: ${lms_est_charge:,.2f}")
    print(f"  Deposit (paid): ${lms_deposit:,.2f}")
    print(f"  Balance: ${lms_balance:,.2f}")
    print(f"  Gratuity: ${lms_gratuity:,.2f}")
    print(f"  Fuel: ${lms_fuel:,.2f}")
    
    # Get PostgreSQL data
    pg_cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    pg_row = pg_cur.fetchone()
    if not pg_row:
        print(f"ERROR: Reserve {reserve} not found in PostgreSQL")
        return
    
    print(f"\nPOSTGRESQL DATA (BEFORE):")
    print(f"  Total Due: ${pg_row[1]:,.2f}")
    print(f"  Paid Amount: ${pg_row[2]:,.2f}")
    print(f"  Balance: ${pg_row[3]:,.2f}")
    
    # Check charter_charges
    pg_cur.execute("""
        SELECT description, amount
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY description
    """, (reserve,))
    
    pg_charges = pg_cur.fetchall()
    pg_charges_total = sum(c[1] for c in pg_charges)
    
    print(f"\nPOSTGRESQL CHARTER_CHARGES (BEFORE):")
    if pg_charges:
        for c in pg_charges:
            print(f"  {c[0]}: ${c[1]:,.2f}")
        print(f"  TOTAL: ${pg_charges_total:,.2f}")
    else:
        print("  No charges found")
    
    # Update PostgreSQL to match LMS
    print(f"\n{'=' * 100}")
    print("UPDATING POSTGRESQL TO MATCH LMS")
    print("=" * 100)
    
    # Update charters table
    pg_cur.execute("""
        UPDATE charters
        SET total_amount_due = %s,
            paid_amount = %s,
            balance = %s
        WHERE reserve_number = %s
    """, (lms_est_charge, lms_deposit, lms_balance, reserve))
    
    print(f"✓ Updated charters table:")
    print(f"  total_amount_due = ${lms_est_charge:,.2f}")
    print(f"  paid_amount = ${lms_deposit:,.2f}")
    print(f"  balance = ${lms_balance:,.2f}")
    
    # Delete old charges
    pg_cur.execute("""
        DELETE FROM charter_charges
        WHERE reserve_number = %s
    """, (reserve,))
    deleted = pg_cur.rowcount
    print(f"\n✓ Deleted {deleted} old charge(s)")
    
    # Insert new charges based on LMS values
    charges_to_insert = []
    
    # Service Fee (base rate minus gratuity and fuel)
    service_fee = lms_est_charge - lms_gratuity - lms_fuel
    if service_fee > 0:
        charges_to_insert.append(('Service Fee', service_fee, 'Pct'))
    
    if lms_fuel > 0:
        charges_to_insert.append(('Fuel', lms_fuel, 'Pct'))
    
    if lms_gratuity > 0:
        charges_to_insert.append(('Gratuity', lms_gratuity, 'Pct'))
    
    print(f"\n✓ Inserting {len(charges_to_insert)} new charge(s):")
    for desc, amount, charge_type in charges_to_insert:
        pg_cur.execute("""
            INSERT INTO charter_charges (reserve_number, description, amount, charge_type)
            VALUES (%s, %s, %s, %s)
        """, (reserve, desc, amount, charge_type))
        print(f"  {desc}: ${amount:,.2f}")
    
    pg_conn.commit()
    
    # Verify
    print(f"\n{'=' * 100}")
    print("VERIFICATION")
    print("=" * 100)
    
    pg_cur.execute("""
        SELECT total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    pg_after = pg_cur.fetchone()
    print(f"PostgreSQL (AFTER):")
    print(f"  Total Due: ${pg_after[0]:,.2f}")
    print(f"  Paid Amount: ${pg_after[1]:,.2f}")
    print(f"  Balance: ${pg_after[2]:,.2f}")
    
    pg_cur.execute("""
        SELECT description, amount
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY description
    """, (reserve,))
    
    pg_charges_after = pg_cur.fetchall()
    pg_total_after = sum(c[1] for c in pg_charges_after)
    
    print(f"\nPostgreSQL Charges (AFTER):")
    for c in pg_charges_after:
        print(f"  {c[0]}: ${c[1]:,.2f}")
    print(f"  TOTAL: ${pg_total_after:,.2f}")
    
    if abs(pg_total_after - lms_est_charge) < 0.01:
        print(f"\n✓ SUCCESS: Charges total ${pg_total_after:,.2f} matches LMS Est_Charge ${lms_est_charge:,.2f}")
    else:
        print(f"\n⚠️  WARNING: Charges total ${pg_total_after:,.2f} does not match LMS Est_Charge ${lms_est_charge:,.2f}")
    
    lms_cur.close()
    lms_conn.close()
    pg_cur.close()
    pg_conn.close()

if __name__ == '__main__':
    sync_019208()
