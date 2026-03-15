"""
Search more thoroughly for Fort Sask Rangers and Fibrenew in almsdata
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print("="*80)
print("SEARCHING FOR MISSING CLIENTS")
print("="*80)

# Search for Fort Sask
print("\nSearching for 'Fort Sask' or 'Rangers':")
cur.execute("""
    SELECT client_id, client_name, lms_customer_number, company_name
    FROM clients
    WHERE client_name ILIKE '%fort%'
       OR client_name ILIKE '%sask%'
       OR client_name ILIKE '%rangers%'
       OR company_name ILIKE '%fort%'
       OR company_name ILIKE '%sask%'
       OR company_name ILIKE '%rangers%'
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for client_id, name, lms_num, company in results:
        print(f"  ID {client_id}: {name} / {company} (LMS: {lms_num})")
else:
    print("  No matches found")

# Search for Fibrenew
print("\nSearching for 'Fibrenew':")
cur.execute("""
    SELECT client_id, client_name, lms_customer_number, company_name
    FROM clients
    WHERE client_name ILIKE '%fibr%'
       OR company_name ILIKE '%fibr%'
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for client_id, name, lms_num, company in results:
        print(f"  ID {client_id}: {name} / {company} (LMS: {lms_num})")
else:
    print("  No matches found")

# Search by LMS customer number 02199
print("\nSearching for LMS customer number '02199':")
cur.execute("""
    SELECT client_id, client_name, lms_customer_number, company_name
    FROM clients
    WHERE lms_customer_number = '02199'
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for client_id, name, lms_num, company in results:
        print(f"  ID {client_id}: {name} / {company} (LMS: {lms_num})")
else:
    print("  No matches found")

cur.close()
conn.close()

print("\n" + "="*80)
print("If these clients aren't found, they may need to be created or")
print("the charters should have client_id set to NULL (unassigned)")
print("="*80)
