import psycopg2

TARGET_IDS = [
    1709, 6557, 6558, 6559, 6560, 6566, 6567, 6568, 6569, 6570, 6571, 6572,
    6573, 6574, 6575, 6576, 6577, 6578, 6579, 6581, 6582, 6583, 6585, 6586,
    6587, 9258, 9259, 9260,
]

conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    port=5432,
    database='neondb',
    user='neondb_owner',
    password='npg_rlL0yK9pvfCW',
    sslmode='require',
)
cur = conn.cursor()

# Bring Neon in line with local/cloud cleanup for known-bad records.
cur.execute(
    """
    UPDATE clients
    SET client_name = NULL,
        updated_at = NOW()
    WHERE client_id = ANY(%s)
    """,
    (TARGET_IDS,),
)
print('neon_rows_set_null', cur.rowcount)

conn.commit()

cur.execute(
    """
    SELECT COUNT(*)
    FROM clients
    WHERE client_name LIKE '"%'
       OR client_name ~ '^[0-9]{4,}$'
       OR client_name ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
    """
)
print('neon_remaining_junk', cur.fetchone()[0])

cur.close()
conn.close()
