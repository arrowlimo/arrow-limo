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

cur.execute(
    """
    UPDATE clients
    SET client_name = TRIM(name),
        updated_at = NOW()
    WHERE COALESCE(TRIM(client_name), '') = ''
      AND COALESCE(TRIM(name), '') <> ''
    """
)
print('rows_updated', cur.rowcount)

conn.commit()

cur.execute("SELECT COUNT(*) FROM clients WHERE COALESCE(TRIM(client_name), '') = ''")
print('remaining_blank_client_name', cur.fetchone()[0])

cur.close()
conn.close()
