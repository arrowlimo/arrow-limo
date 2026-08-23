from _db_connect import connect_db

db = connect_db()
cur = db.cursor()

cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.client_display_name,
           cl.client_id, cl.client_name
    FROM charters c
    LEFT JOIN clients cl ON cl.client_name ILIKE c.client_display_name
    WHERE c.client_id IS NULL
      AND c.client_display_name IS NOT NULL
      AND c.client_display_name != ''
    ORDER BY c.reserve_number
""")
rows = cur.fetchall()

print(f"Found {len(rows)} charters with client_id=NULL but a display name set:\n")
matched = []
unmatched = []
for r in rows:
    charter_id, reserve, display, cl_id, cl_name = r
    if cl_id:
        matched.append(r)
        print(f"  MATCH   Charter {reserve} (id={charter_id}): '{display}'  -> client_id={cl_id} ({cl_name})")
    else:
        unmatched.append(r)
        print(f"  NO MATCH Charter {reserve} (id={charter_id}): '{display}'  -> not found in clients table")

print(f"\nSummary: {len(matched)} can be auto-fixed, {len(unmatched)} have no matching client record.")
