"""
Update charters.client_id for all charters where client_id is NULL
but client_display_name matches exactly ONE record in the clients table.
Skips ambiguous matches (multiple clients with same name).
"""
from _db_connect import connect_db

db = connect_db()
cur = db.cursor()

# Find all candidates
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.client_display_name,
           array_agg(cl.client_id) AS matched_ids
    FROM charters c
    JOIN clients cl ON cl.client_name ILIKE c.client_display_name
    WHERE c.client_id IS NULL
      AND c.client_display_name IS NOT NULL
      AND c.client_display_name != ''
    GROUP BY c.charter_id, c.reserve_number, c.client_display_name
""")
rows = cur.fetchall()

updated = 0
skipped_ambiguous = 0

for charter_id, reserve, display, matched_ids in rows:
    if len(matched_ids) > 1:
        print(f"  SKIP (ambiguous) Charter {reserve}: '{display}' -> {len(matched_ids)} matches: {matched_ids}")
        skipped_ambiguous += 1
        continue
    client_id = matched_ids[0]
    cur.execute(
        "UPDATE charters SET client_id = %s WHERE charter_id = %s",
        (client_id, charter_id)
    )
    print(f"  FIXED Charter {reserve} (id={charter_id}): '{display}' -> client_id={client_id}")
    updated += 1

db.commit()
print(f"\nDone: {updated} charters updated, {skipped_ambiguous} skipped (ambiguous match).")
