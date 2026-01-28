"""
Automatically link unlinked refunds based on reservation numbers found in Square transaction data.
This script links the 22 refunds identified by the analysis script.
"""
import os
import psycopg2
import argparse

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

parser = argparse.ArgumentParser()
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Refunds with reservation numbers extracted from Square transaction data
LINKAGES = [
    (104, '019270', 18144),
    (1207, '019270', 18144),
    (1208, '019155', 18046),
    (105, '019155', 18046),
    (1210, '019210', 17909),
    (1209, '019272', 18146),
    (111, '019210', 17909),
    (5, '019272', 18146),
    (1211, '018782', 17656),
    (110, '018782', 17656),
    (1196, '018967', 17851),
    (112, '018967', 17851),
    (1197, '018849', 17723),
    (113, '018849', 17723),
    (115, '018745', 17620),
    (1199, '018745', 17620),
    (116, '018660', 17548),
    (1200, '018660', 17548),
    (117, '018214', 17103),
    (1201, '018214', 17103),
    (21, '018213', 17102),
    (1176, '018213', 17102),
]

print("="*80)
print("LINKING UNLINKED REFUNDS FROM SQUARE TRANSACTION DATA")
print("="*80)
print(f"\nMode: {'WRITE' if args.write else 'DRY-RUN'}")
print(f"Total refunds to link: {len(LINKAGES)}")

linked_count = 0
already_linked = 0
errors = 0

for refund_id, reserve, charter_id in LINKAGES:
    print(f"\n{'*'*60}")
    print(f"Refund #{refund_id} → Reserve {reserve}, Charter {charter_id}")
    
    # Check current state
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, square_payment_id
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    
    if not refund:
        print(f"  [FAIL] ERROR: Refund #{refund_id} not found!")
        errors += 1
        continue
    
    print(f"  Current: Date={refund[1]}, Amount=${refund[2]}")
    print(f"  Current Links: Reserve={refund[3]}, Charter={refund[4]}")
    
    if refund[3] and refund[4]:
        print(f"  ℹ️ Already linked (skipping)")
        already_linked += 1
        continue
    
    # Verify charter exists
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date
        FROM charters
        WHERE charter_id = %s AND reserve_number = %s
    """, (charter_id, reserve))
    charter = cur.fetchone()
    
    if not charter:
        print(f"  [FAIL] ERROR: Charter {charter_id} / Reserve {reserve} not found!")
        errors += 1
        continue
    
    print(f"  Target Charter: Date={charter[2]}")
    
    if args.write:
        cur.execute("""
            UPDATE charter_refunds
            SET reserve_number = %s,
                charter_id = %s
            WHERE id = %s
        """, (reserve, charter_id, refund_id))
        print(f"  [OK] UPDATED")
        linked_count += 1
    else:
        print(f"  [DRY-RUN] Would update")
        linked_count += 1

if args.write:
    conn.commit()
    print("\n" + "="*80)
    print("[OK] CHANGES COMMITTED")
    print("="*80)
else:
    conn.rollback()
    print("\n" + "="*80)
    print("DRY-RUN COMPLETE (use --write to apply changes)")
    print("="*80)

# Summary
print(f"\n📊 SUMMARY:")
print(f"  Total refunds processed: {len(LINKAGES)}")
print(f"  Successfully linked: {linked_count}")
print(f"  Already linked (skipped): {already_linked}")
print(f"  Errors: {errors}")

if args.write and linked_count > 0:
    # Calculate new linkage rate
    cur.execute("SELECT COUNT(*) FROM charter_refunds")
    total_refunds = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM charter_refunds WHERE reserve_number IS NOT NULL AND charter_id IS NOT NULL")
    total_linked = cur.fetchone()[0]
    
    linkage_rate = (total_linked / total_refunds * 100) if total_refunds > 0 else 0
    
    print(f"\n📈 NEW LINKAGE STATISTICS:")
    print(f"  Total Refunds: {total_refunds}")
    print(f"  Linked: {total_linked} ({linkage_rate:.1f}%)")
    print(f"  Unlinked: {total_refunds - total_linked} ({100-linkage_rate:.1f}%)")

# Verification of linked refunds
if args.write and linked_count > 0:
    print(f"\n{'='*80}")
    print("VERIFICATION OF NEWLY LINKED REFUNDS")
    print(f"{'='*80}")
    
    for refund_id, reserve, charter_id in LINKAGES[:5]:  # Show first 5
        cur.execute("""
            SELECT id, refund_date, amount, reserve_number, charter_id
            FROM charter_refunds
            WHERE id = %s
        """, (refund_id,))
        refund = cur.fetchone()
        
        if refund:
            status = "[OK]" if refund[3] == reserve and refund[4] == charter_id else "[FAIL]"
            print(f"{status} Refund #{refund[0]}: ${refund[2]} → Reserve {refund[3]}, Charter {refund[4]}")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("COMPLETE")
print(f"{'='*80}")
