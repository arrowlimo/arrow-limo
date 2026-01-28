#!/usr/bin/env python3
"""
Write down 58 charters that are already fixed in LMS but still have balance in almsdata.
These are mostly "Closed" status charters where LMS balance = $0, almsdata still shows balance.
We remove/adjust charges to match LMS (zero balance).
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# List of 58 reserves to write down (from verification)
WRITEDOWN_RESERVES = [
    '013690', '015146', '013536', '009363', '008779', '013357', '006493', '001995',
    '017932', '015847', '018257', '004887', '017764', '007282', '013369', '008040',
    '013204', '008858', '010061', '016468', '014163', '010399', '006063', '013354',
    '017657', '002720', '004872', '001701', '012304', '013881', '001341', '001087',
    '001097', '001077', '001583', '001684', '003734', '001585', '001581', '008940',
    '003025', '013353', '005629', '010060', '014304', '005842', '015922', '009134',
    '007504', '004995', '018942', '016256', '016255', '017147', '016620', '016822',
    '018431', '017373'
]

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Writing down 58 charters already fixed in LMS...")
print()

total_charges_removed = 0.0
failed = []

try:
    for reserve in WRITEDOWN_RESERVES:
        try:
            # Get current charges
            cur.execute("""
                SELECT SUM(amount) FROM charter_charges 
                WHERE reserve_number = %s
            """, (reserve,))
            charges = float(cur.fetchone()[0] or 0.0)
            
            if charges > 0.01 or charges < -0.01:
                # Delete charges to zero out
                cur.execute("""
                    DELETE FROM charter_charges
                    WHERE reserve_number = %s
                """, (reserve,))
                total_charges_removed += charges
                print(f"✓ {reserve}: removed ${charges:>10.2f}")
            else:
                print(f"✓ {reserve}: already near zero (${charges:.2f})")
        
        except Exception as e:
            failed.append((reserve, str(e)))
            print(f"✗ {reserve}: ERROR - {e}")
    
    # Commit all changes
    conn.commit()
    print()
    print("=" * 70)
    print(f"Processed: {len(WRITEDOWN_RESERVES) - len(failed)} succeeded")
    print(f"Failed: {len(failed)}")
    print(f"Total charges removed: ${total_charges_removed:,.2f}")
    print("=" * 70)
    
    if failed:
        print("\nFailed reserves:")
        for reserve, error in failed:
            print(f"  {reserve}: {error}")
    
    print("\n✅ Write-down committed")

except Exception as e:
    conn.rollback()
    print(f"❌ Rollback: {e}")
finally:
    cur.close()
    conn.close()
