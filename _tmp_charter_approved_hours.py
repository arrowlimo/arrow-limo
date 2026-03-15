"""
Charter Approved Hours + Gratuity Sync
=======================================
1. Add approved_hours column to charters (if not exists)
2. Backfill calculated_hours = dropoff_time - pickup_time (handles midnight crossing)
3. Backfill approved_hours:
   - actual_hours where > 0  (LMS-sourced, includes minimum hours rules)
   - else calculated_hours
   - else quoted_hours
4. Sync driver_gratuity from charter_charges WHERE charge_type='gratuity'
   (fixes 103 mismatches + fills 588 missing)
5. Create DB trigger on charter_charges to auto-sync driver_gratuity on every change
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine')
conn.autocommit = False
cur = conn.cursor()

print("=== Charter Approved Hours + Gratuity Sync ===")

# ------------------------------------------------------------------
# 1. Add approved_hours column
# ------------------------------------------------------------------
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name='charters' AND column_name='approved_hours'
""")
if not cur.fetchone():
    cur.execute("ALTER TABLE charters ADD COLUMN approved_hours NUMERIC(6,2)")
    print("✅ Added charters.approved_hours column")
else:
    print("   charters.approved_hours already exists")

# ------------------------------------------------------------------
# 2. Backfill calculated_hours from pickup_time / dropoff_time
# ------------------------------------------------------------------
cur.execute("""
    UPDATE charters
    SET calculated_hours = ROUND(
        CASE
            WHEN dropoff_time >= pickup_time
                THEN EXTRACT(EPOCH FROM (dropoff_time - pickup_time)) / 3600
            ELSE
                EXTRACT(EPOCH FROM (dropoff_time - pickup_time + INTERVAL '24 hours')) / 3600
        END
    ::NUMERIC, 2)
    WHERE pickup_time IS NOT NULL
      AND dropoff_time IS NOT NULL
""")
cnt = cur.rowcount
print(f"✅ Backfilled calculated_hours for {cnt} charters")

# ------------------------------------------------------------------
# 3. Backfill approved_hours = best available source
#    Priority: actual_hours (LMS) > calculated_hours > quoted_hours
# ------------------------------------------------------------------
cur.execute("""
    UPDATE charters
    SET approved_hours = COALESCE(
        CASE WHEN actual_hours > 0 THEN actual_hours ELSE NULL END,
        CASE WHEN calculated_hours > 0 THEN calculated_hours ELSE NULL END,
        CASE WHEN quoted_hours > 0 THEN quoted_hours ELSE NULL END
    )
    WHERE COALESCE(actual_hours, 0) > 0
       OR COALESCE(calculated_hours, 0) > 0
       OR COALESCE(quoted_hours, 0) > 0
""")
cnt = cur.rowcount
print(f"✅ Backfilled approved_hours for {cnt} charters")

# ------------------------------------------------------------------
# 4. Sync driver_gratuity from charter_charges
# ------------------------------------------------------------------
cur.execute("""
    UPDATE charters c
    SET driver_gratuity = COALESCE((
        SELECT SUM(cc.amount)
        FROM charter_charges cc
        WHERE cc.charter_id = c.charter_id
          AND cc.charge_type = 'gratuity'
    ), 0)
    WHERE (
        -- Mismatch
        c.driver_gratuity != COALESCE((
            SELECT SUM(cc.amount)
            FROM charter_charges cc
            WHERE cc.charter_id = c.charter_id
              AND cc.charge_type = 'gratuity'
        ), 0)
        OR
        -- Missing (has charges but 0 on charter row)
        (COALESCE(c.driver_gratuity, 0) = 0 AND EXISTS (
            SELECT 1 FROM charter_charges cc
            WHERE cc.charter_id = c.charter_id
              AND cc.charge_type = 'gratuity'
              AND cc.amount > 0
        ))
    )
""")
cnt = cur.rowcount
print(f"✅ Synced driver_gratuity for {cnt} charters (mismatches + missing)")

# ------------------------------------------------------------------
# 5. Create trigger to auto-sync driver_gratuity on charter_charges changes
# ------------------------------------------------------------------
cur.execute("DROP TRIGGER IF EXISTS trg_charter_gratuity_sync ON charter_charges")
cur.execute("""
    CREATE OR REPLACE FUNCTION trg_sync_charter_gratuity()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    DECLARE
        v_charter_id INT;
    BEGIN
        v_charter_id := COALESCE(NEW.charter_id, OLD.charter_id);
        IF v_charter_id IS NULL THEN
            RETURN COALESCE(NEW, OLD);
        END IF;

        UPDATE charters
        SET driver_gratuity = COALESCE((
            SELECT SUM(amount)
            FROM charter_charges
            WHERE charter_id = v_charter_id
              AND charge_type = 'gratuity'
        ), 0),
        updated_at = NOW()
        WHERE charter_id = v_charter_id;

        RETURN COALESCE(NEW, OLD);
    END;
    $$
""")
cur.execute("""
    CREATE TRIGGER trg_charter_gratuity_sync
    AFTER INSERT OR UPDATE OR DELETE ON charter_charges
    FOR EACH ROW
    EXECUTE FUNCTION trg_sync_charter_gratuity()
""")
print("✅ Created trigger trg_charter_gratuity_sync on charter_charges")

# ------------------------------------------------------------------
# Verify
# ------------------------------------------------------------------
cur.execute("""
    SELECT
        COUNT(*) total,
        COUNT(approved_hours) FILTER (WHERE approved_hours > 0) approved_nonzero,
        COUNT(calculated_hours) FILTER (WHERE calculated_hours > 0) calc_nonzero,
        COUNT(driver_gratuity) FILTER (WHERE driver_gratuity > 0) grat_nonzero,
        -- Remaining mismatches
        COUNT(*) FILTER (WHERE driver_gratuity != COALESCE((
            SELECT SUM(cc.amount) FROM charter_charges cc
            WHERE cc.charter_id = charters.charter_id AND cc.charge_type='gratuity'
        ), 0)) remaining_grat_mismatches
    FROM charters
""")
r = cur.fetchone()
print(f"\n=== VERIFICATION ===")
print(f"  Total charters:         {r[0]:,}")
print(f"  approved_hours > 0:     {r[1]:,}")
print(f"  calculated_hours > 0:   {r[2]:,}")
print(f"  driver_gratuity > 0:    {r[3]:,}")
print(f"  Gratuity mismatches:    {r[4]:,}  (should be 0)")

# Sample
cur.execute("""
    SELECT reserve_number, pickup_time, dropoff_time,
           calculated_hours, actual_hours, approved_hours, driver_gratuity
    FROM charters
    WHERE pickup_time IS NOT NULL AND dropoff_time IS NOT NULL
    ORDER BY charter_id DESC
    LIMIT 10
""")
print("\n=== SAMPLE (10 most recent with times) ===")
print(f"{'reserve':>10} {'pickup':>8} {'dropoff':>8} {'calc_h':>6} {'actual_h':>8} {'approved_h':>10} {'grat':>8}")
for r in cur.fetchall():
    print(f"{str(r[0]):>10} {str(r[1]):>8} {str(r[2]):>8} {str(r[3] or ''):>6} {str(r[4] or ''):>8} {str(r[5] or ''):>10} {str(r[6] or ''):>8}")

conn.commit()
print("\n✅ All changes committed.")
conn.close()
