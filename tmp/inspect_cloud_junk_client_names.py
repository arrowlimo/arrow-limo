import psycopg2

conn = psycopg2.connect(
    host='192.168.1.176',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

cur.execute(
    """
    SELECT
        client_id,
        client_name,
        COALESCE(name, '') AS name,
        COALESCE(first_name, '') AS first_name,
        COALESCE(last_name, '') AS last_name,
        COALESCE(contact_info, '') AS contact_info
    FROM clients
    WHERE client_name LIKE '"%'
       OR client_name ~ '^[0-9]{4,}$'
       OR client_name ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
    ORDER BY client_id
    LIMIT 400
    """
)
rows = cur.fetchall()
print('candidates', len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
