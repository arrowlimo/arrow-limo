import psycopg2

conn = psycopg2.connect(
    host='192.168.1.176',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

junk_ids = [6557, 6574, 6578, 6579, 6582]

cur.execute(
    """
    UPDATE clients
    SET client_name = NULL,
        updated_at = NOW()
    WHERE client_id = ANY(%s)
    """,
    (junk_ids,),
)
print('nulled_known_junk_rows', cur.rowcount)

conn.commit()

cur.execute(
    """
    SELECT client_id, client_name
    FROM clients
    WHERE client_id = ANY(%s)
    ORDER BY client_id
    """,
    (junk_ids,),
)
print('post_values')
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
