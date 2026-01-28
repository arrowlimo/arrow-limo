"""
Link unlinked refund duplicates to their correct charters.

Based on verification:
1. Refund #1056 ($1,452.40) -> Reserve 016478, Charter 15361
2. Refund #1061 ($699.05) -> Reserve 015400, Charter 14290  
3. Refund #1204 ($526.50) -> Reserve 019521, Charter 18394
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

LINKAGES = [
    (1056, '016478', 15361, '$1,452.40 Darryl@carstarreddeer.ca'),
    (1061, '015400', 14290, '$699.05 Richard Pfeifer & Trish'),
    (1204, '019521', 18394, '$526.50 Goodman Roofing'),
]

print("="*80)
print("LINKING UNLINKED REFUND DUPLICATES")
print("="*80)

for refund_id, reserve, charter_id, description in LINKAGES:
    print(f"\n{'*' * 60}")
    print(f"Refund #{refund_id}: {description}")
    print(f"  Reserve: {reserve}, Charter: {charter_id}")
    
    # Verify refund exists and is unlinked
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, square_payment_id
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    
    if not refund:
        print(f"  [WARN] Refund #{refund_id} not found!")
        continue
    
    print(f"  Current state: Date={refund[1]}, Amount=${refund[2]}, Reserve={refund[3]}, Charter={refund[4]}")
    
    if refund[3] and refund[4]:
        print(f"  ✓ Already linked to {refund[3]} / Charter {refund[4]}")
        continue
    
    # Verify charter exists
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, status
        FROM charters
        WHERE charter_id = %s AND reserve_number = %s
    """, (charter_id, reserve))
    charter = cur.fetchone()
    
    if not charter:
        print(f"  [WARN] Charter {charter_id} / Reserve {reserve} not found!")
        continue
    
    print(f"  Target charter: Date={charter[2]}, Status={charter[3]}")
    
    if args.write:
        cur.execute("""
            UPDATE charter_refunds
            SET reserve_number = %s,
                charter_id = %s
            WHERE id = %s
        """, (reserve, charter_id, refund_id))
        print(f"  [OK] UPDATED refund #{refund_id} -> Reserve {reserve}, Charter {charter_id}")
    else:
        print(f"  DRY-RUN: Would update refund #{refund_id} -> Reserve {reserve}, Charter {charter_id}")

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

# Verification
print("\n" + "="*80)
print("POST-LINKAGE VERIFICATION")
print("="*80)

for refund_id, reserve, charter_id, description in LINKAGES:
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    if refund:
        status = "[OK] LINKED" if refund[3] == reserve and refund[4] == charter_id else "[WARN] NOT LINKED"
        print(f"{status} Refund #{refund[0]}: ${refund[2]} -> Reserve {refund[3]}, Charter {refund[4]}")

cur.close()
conn.close()
