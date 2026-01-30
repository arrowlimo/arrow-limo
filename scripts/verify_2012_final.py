"""Verify 2012 cleanup completion"""
import os
import psycopg2

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

conn = psycopg2.connect(**DB)
cur = conn.cursor()

print("=" * 60)
print("2012 FINAL VERIFICATION")
print("=" * 60)

# 1. Negative payments (should be 0)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND amount < 0
""")
neg_count, neg_sum = cur.fetchone()
print(f"\n1. Negative payments remaining: {neg_count} (should be 0)")
if neg_count > 0:
    print(f"   [FAIL] FAILED: ${float(neg_sum):,.2f} in negative payments")
else:
    print(f"   [OK] PASSED")

# 2. Migrated receipts (should be 758: 724 + 34)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
    FROM receipts 
    WHERE description LIKE '%Migrated from payment%'
""")
mig_count, mig_sum = cur.fetchone()
print(f"\n2. Migrated receipts: {mig_count} (should be 758: 724 pass 1 + 34 pass 2)")
print(f"   Total: ${float(mig_sum or 0):,.2f}")
if mig_count == 758:
    print(f"   [OK] PASSED")
else:
    print(f"   [WARN]  WARNING: Expected 758, got {mig_count}")

# 3. Orphaned payments (should be 179 batch deposits)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND reserve_number IS NULL
      AND amount > 0
""")
orp_count, orp_sum = cur.fetchone()
print(f"\n3. Orphaned payments (batch deposits): {orp_count} (should be 179)")
print(f"   Total: ${float(orp_sum):,.2f}")
if orp_count == 179:
    print(f"   [OK] PASSED")
else:
    print(f"   [WARN]  WARNING: Expected 179, got {orp_count}")

# 4. Auto-matched payments (should be 27)
cur.execute("""
    SELECT COUNT(*), COALESCE(SUM(amount), 0)
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND reserve_number IS NOT NULL
      AND notes LIKE '%AUTO-MATCHED%'
""")
mat_count, mat_sum = cur.fetchone()
print(f"\n4. Auto-matched payments: {mat_count} (should be 27)")
print(f"   Total: ${float(mat_sum):,.2f}")
if mat_count == 27:
    print(f"   [OK] PASSED")
else:
    print(f"   [WARN]  WARNING: Expected 27, got {mat_count}")

# 5. Total 2012 payments
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN reserve_number IS NOT NULL THEN 1 ELSE 0 END) as linked,
        SUM(CASE WHEN reserve_number IS NULL AND amount > 0 THEN 1 ELSE 0 END) as orphaned,
        COALESCE(SUM(amount), 0) as total_amount
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
""")
total, linked, orphaned, total_amt = cur.fetchone()
print(f"\n5. Total 2012 payment summary:")
print(f"   Total records: {total}")
print(f"   Linked to charters: {linked} ({100*linked/total:.1f}%)")
print(f"   Batch deposits: {orphaned} ({100*orphaned/total:.1f}%)")
print(f"   Total amount: ${float(total_amt):,.2f}")
print(f"   [OK] COMPLETE")

print("\n" + "=" * 60)
if neg_count == 0 and mig_count == 758:
    print("[OK] ALL CRITICAL CHECKS PASSED")
    print("=" * 60)
    print("\n2012 is clean and ready for CRA compliance reporting.")
else:
    print("[WARN]  SOME CHECKS FAILED - REVIEW ABOVE")
    print("=" * 60)

cur.close()
conn.close()
