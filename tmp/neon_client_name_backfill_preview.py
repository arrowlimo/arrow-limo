import psycopg2

conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    port=5432,
    database='neondb',
    user='neondb_owner',
    password='npg_rlL0yK9pvfCW',
    sslmode='require',
)
cur = conn.cursor()

cur.execute("""
SELECT
  COUNT(*) FILTER (WHERE COALESCE(TRIM(client_name), '') = '') AS blank_client_name,
  COUNT(*) FILTER (WHERE COALESCE(TRIM(name), '') <> '') AS has_name,
  COUNT(*) FILTER (WHERE COALESCE(TRIM(contact_info), '') <> '') AS has_contact_info,
  COUNT(*) FILTER (WHERE COALESCE(TRIM(first_name), '') <> '' OR COALESCE(TRIM(last_name), '') <> '') AS has_first_last
FROM clients
""")
print('profile_counts', cur.fetchone())

cur.execute("""
SELECT client_id, client_name, name, contact_info, first_name, last_name
FROM clients
WHERE COALESCE(TRIM(client_name), '') = ''
  AND (
    COALESCE(TRIM(name), '') <> '' OR
    COALESCE(TRIM(contact_info), '') <> '' OR
    COALESCE(TRIM(first_name), '') <> '' OR
    COALESCE(TRIM(last_name), '') <> ''
  )
ORDER BY client_id
LIMIT 25
""")
rows = cur.fetchall()
print('sample_candidates', len(rows))
for r in rows:
    print(r)

# Preview exact update count using requested rule: copy Contact Name -> client_name.
# In this schema, contact name source is `name` (fallback first/last only if name blank).
cur.execute("""
SELECT COUNT(*)
FROM clients
WHERE COALESCE(TRIM(client_name), '') = ''
  AND COALESCE(TRIM(name), '') <> ''
""")
print('will_update_from_name_only', cur.fetchone()[0])

cur.close()
conn.close()
