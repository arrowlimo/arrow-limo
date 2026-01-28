import psycopg2
import os
from decimal import Decimal, ROUND_HALF_UP

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Adding penny rounding rules...\n")

# 1. Create rounding function
sql_function = """
    CREATE OR REPLACE FUNCTION round_to_penny(amount NUMERIC)
    RETURNS NUMERIC AS $$
    BEGIN
        RETURN ROUND(amount, 2);
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
"""

try:
    cur.execute(sql_function)
    conn.commit()
    print("✅ Created round_to_penny() function")
except Exception as e:
    print(f"⚠️  Function may already exist: {e}")
    conn.rollback()

# 2. Add constraints to charter_charges
try:
    cur.execute("""
        ALTER TABLE charter_charges
        ADD CONSTRAINT amount_rounded_penny CHECK (amount = ROUND(amount, 2))
    """)
    conn.commit()
    print("✅ Added penny rounding constraint to charter_charges.amount")
except Exception as e:
    if "already exists" in str(e) or "duplicate key" in str(e):
        print("⚠️  Constraint already exists on charter_charges")
    else:
        print(f"⚠️  Error adding constraint: {e}")
    conn.rollback()

# 3. Add constraints to payments
try:
    cur.execute("""
        ALTER TABLE payments
        ADD CONSTRAINT amount_rounded_penny CHECK (amount = ROUND(amount, 2))
    """)
    conn.commit()
    print("✅ Added penny rounding constraint to payments.amount")
except Exception as e:
    if "already exists" in str(e) or "duplicate key" in str(e):
        print("⚠️  Constraint already exists on payments")
    else:
        print(f"⚠️  Error adding constraint: {e}")
    conn.rollback()

# 4. Add constraints to charters totals
try:
    cur.execute("""
        ALTER TABLE charters
        ADD CONSTRAINT total_amount_due_rounded_penny CHECK (total_amount_due = ROUND(total_amount_due, 2))
    """)
    conn.commit()
    print("✅ Added penny rounding constraint to charters.total_amount_due")
except Exception as e:
    if "already exists" in str(e) or "duplicate key" in str(e):
        print("⚠️  Constraint already exists on charters")
    else:
        print(f"⚠️  Error adding constraint: {e}")
    conn.rollback()

# 5. Round any existing non-conforming values
print("\nRounding existing non-conforming values...")

cur.execute("""
    UPDATE charter_charges 
    SET amount = ROUND(amount, 2)
    WHERE amount != ROUND(amount, 2)
""")
updated = cur.rowcount
conn.commit()
if updated > 0:
    print(f"✅ Rounded {updated} charter_charges amounts")
else:
    print("✅ All charter_charges amounts already rounded")

cur.execute("""
    UPDATE payments 
    SET amount = ROUND(amount, 2)
    WHERE amount != ROUND(amount, 2)
""")
updated = cur.rowcount
conn.commit()
if updated > 0:
    print(f"✅ Rounded {updated} payment amounts")
else:
    print("✅ All payment amounts already rounded")

cur.execute("""
    UPDATE charters 
    SET total_amount_due = ROUND(total_amount_due, 2),
        paid_amount = ROUND(paid_amount, 2),
        balance = ROUND(balance, 2)
    WHERE total_amount_due != ROUND(total_amount_due, 2)
       OR paid_amount != ROUND(paid_amount, 2)
       OR balance != ROUND(balance, 2)
""")
updated = cur.rowcount
conn.commit()
if updated > 0:
    print(f"✅ Rounded {updated} charter amounts")
else:
    print("✅ All charter amounts already rounded")

# 6. Create a trigger to auto-round on insert/update
trigger_sql = """
    CREATE OR REPLACE FUNCTION round_amounts()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.amount := ROUND(NEW.amount, 2);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""

try:
    cur.execute(trigger_sql)
    conn.commit()
    print("\n✅ Created round_amounts() trigger function")
except Exception as e:
    print(f"⚠️  Trigger function creation issue: {e}")
    conn.rollback()

# Create trigger on charter_charges
try:
    cur.execute("""
        DROP TRIGGER IF EXISTS round_charter_charges_amount ON charter_charges;
        CREATE TRIGGER round_charter_charges_amount
        BEFORE INSERT OR UPDATE ON charter_charges
        FOR EACH ROW
        EXECUTE FUNCTION round_amounts();
    """)
    conn.commit()
    print("✅ Created rounding trigger on charter_charges")
except Exception as e:
    print(f"⚠️  Trigger creation issue: {e}")
    conn.rollback()

# Create trigger on payments
try:
    cur.execute("""
        DROP TRIGGER IF EXISTS round_payments_amount ON payments;
        CREATE TRIGGER round_payments_amount
        BEFORE INSERT OR UPDATE ON payments
        FOR EACH ROW
        EXECUTE FUNCTION round_amounts();
    """)
    conn.commit()
    print("✅ Created rounding trigger on payments")
except Exception as e:
    print(f"⚠️  Trigger creation issue: {e}")
    conn.rollback()

# Create trigger on charters
charter_trigger_sql = """
    CREATE OR REPLACE FUNCTION round_charter_amounts()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.total_amount_due := ROUND(NEW.total_amount_due, 2);
        NEW.paid_amount := ROUND(NEW.paid_amount, 2);
        NEW.balance := ROUND(NEW.balance, 2);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""

try:
    cur.execute(charter_trigger_sql)
    conn.commit()
    print("✅ Created round_charter_amounts() trigger function")
except Exception as e:
    print(f"⚠️  Charter trigger function issue: {e}")
    conn.rollback()

try:
    cur.execute("""
        DROP TRIGGER IF EXISTS round_charter_totals ON charters;
        CREATE TRIGGER round_charter_totals
        BEFORE INSERT OR UPDATE ON charters
        FOR EACH ROW
        EXECUTE FUNCTION round_charter_amounts();
    """)
    conn.commit()
    print("✅ Created rounding trigger on charters")
except Exception as e:
    print(f"⚠️  Charter trigger creation issue: {e}")
    conn.rollback()

print("\n" + "="*70)
print("✅ PENNY ROUNDING RULES ACTIVATED")
print("="*70)
print("All financial amounts will now be automatically rounded to 2 decimals")
print("on insert/update operations.")

cur.close()
conn.close()
