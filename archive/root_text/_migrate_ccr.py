from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()
cur.execute('ALTER TABLE clients ADD COLUMN IF NOT EXISTS contract_charter_reserve VARCHAR(20)')
conn.commit()
print('contract_charter_reserve column added (or already exists)')
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='contract_charter_reserve'")
row = cur.fetchone()
print('Column exists after migration:', row is not None)
conn.close()
