"""
Clean up contaminated client records - DELETE junk clients and set charters to NULL client_id.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Junk client IDs found: 6561, 6562, 6584, 6588, 6589
junk_client_ids = [6561, 6562, 6584, 6588, 6589]

print("🧹 Cleaning up contaminated client records...\n")

# First, set charters.client_id to NULL for these clients
cur.execute("""
    UPDATE charters
    SET client_id = NULL
    WHERE client_id = ANY(%s)
""", (junk_client_ids,))

updated_charters = cur.rowcount
print(f"✅ Updated {updated_charters} charters: set client_id to NULL")

# Then delete the junk client records
cur.execute("""
    DELETE FROM clients
    WHERE client_id = ANY(%s)
""", (junk_client_ids,))

deleted_clients = cur.rowcount
print(f"✅ Deleted {deleted_clients} contaminated client records")

conn.commit()
print(f"\n✅ Database cleaned up successfully")

cur.close()
conn.close()
