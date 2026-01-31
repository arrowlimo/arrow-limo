import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    sslmode=os.getenv('DB_SSLMODE','require')
)
cur = conn.cursor()

print("="*80)
print("CREATING RUN TYPE DEFAULT CHARGES TABLE")
print("="*80)

# Create table to store default charges for each run type
cur.execute("""
    CREATE TABLE IF NOT EXISTS run_type_default_charges (
        id SERIAL PRIMARY KEY,
        run_type_id INTEGER REFERENCES charter_run_types(id) ON DELETE CASCADE,
        charge_description VARCHAR(255) NOT NULL,
        charge_type VARCHAR(50) DEFAULT 'other',
        amount NUMERIC(10,2),
        calc_type VARCHAR(20) DEFAULT 'Fixed',
        value NUMERIC(10,2),
        formula VARCHAR(100),
        is_taxable BOOLEAN DEFAULT true,
        sequence INTEGER DEFAULT 100,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

print("✅ Table created: run_type_default_charges")

# Add some example default charges for airport run types
print("\n" + "="*80)
print("ADDING EXAMPLE DEFAULT CHARGES")
print("="*80)

# Get run type IDs
cur.execute("SELECT id, run_type_name FROM charter_run_types WHERE run_type_name LIKE '%Airport%'")
airport_types = cur.fetchall()

for run_type_id, run_type_name in airport_types:
    # Check if charges already exist
    cur.execute("SELECT COUNT(*) FROM run_type_default_charges WHERE run_type_id = %s", (run_type_id,))
    existing = cur.fetchone()[0]
    
    if existing == 0:
        if 'Calgary' in run_type_name:
            airport_fee = 18.00
            city = "Calgary"
        elif 'Edmonton' in run_type_name:
            airport_fee = 18.00
            city = "Edmonton"
        elif 'Red Deer' in run_type_name:
            airport_fee = 25.00
            city = "Red Deer"
        else:
            airport_fee = 18.00
            city = "Unknown"
        
        # Insert airport fee charge
        cur.execute("""
            INSERT INTO run_type_default_charges 
            (run_type_id, charge_description, charge_type, amount, calc_type, value, is_taxable, sequence)
            VALUES (%s, %s, 'airport_fee', %s, 'Fixed', %s, true, 100)
        """, (run_type_id, f"{city} Airport Fee", airport_fee, airport_fee))
        
        print(f"✅ Added airport fee (${airport_fee}) for: {run_type_name}")

conn.commit()

# Show all default charges
print("\n" + "="*80)
print("ALL RUN TYPE DEFAULT CHARGES")
print("="*80)

cur.execute("""
    SELECT 
        rt.run_type_name,
        dc.charge_description,
        dc.charge_type,
        dc.amount,
        dc.calc_type,
        dc.value,
        dc.is_taxable,
        dc.sequence
    FROM run_type_default_charges dc
    JOIN charter_run_types rt ON dc.run_type_id = rt.id
    ORDER BY rt.run_type_name, dc.sequence
""")

rows = cur.fetchall()
if rows:
    print(f"\n{'Run Type':<30} {'Charge':<25} {'Type':<15} {'Amount':<10} {'Calc':<10} {'Taxable':<8}")
    print("-"*100)
    for run_type, desc, charge_type, amount, calc_type, value, taxable, seq in rows:
        amt_str = f"${float(amount):.2f}" if amount else "N/A"
        tax_str = "Yes" if taxable else "No"
        print(f"{run_type:<30} {desc:<25} {charge_type:<15} {amt_str:<10} {calc_type:<10} {tax_str:<8}")
else:
    print("No default charges configured yet")

cur.close()
conn.close()

print("\n" + "="*80)
print("COMPLETE")
print("="*80)
