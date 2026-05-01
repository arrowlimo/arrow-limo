import psycopg2

conn = psycopg2.connect(
    host='192.168.1.176',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

# Build cleaned display names from first_name/last_name when they are useful.
cur.execute(
    """
    UPDATE clients
    SET client_name = TRIM(BOTH ', ' FROM CONCAT_WS(', ', NULLIF(TRIM(last_name), ''), NULLIF(TRIM(first_name), ''))),
        updated_at = NOW()
    WHERE client_name LIKE '"%'
      AND (
        NULLIF(TRIM(first_name), '') IS NOT NULL
        OR NULLIF(TRIM(last_name), '') IS NOT NULL
      )
      AND NOT (
        COALESCE(TRIM(first_name), '') ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$'
        OR COALESCE(TRIM(last_name), '') ~ '^[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s*(AM|PM)$'
      )
      AND TRIM(BOTH ', ' FROM CONCAT_WS(', ', NULLIF(TRIM(last_name), ''), NULLIF(TRIM(first_name), ''))) <> ''
    """
)
print('updated_from_first_last', cur.rowcount)

# For rows still obviously junk, move client_name out of picker by blanking it.
cur.execute(
    """
    UPDATE clients
    SET client_name = NULL,
        updated_at = NOW()
    WHERE client_name LIKE '"%'
       OR client_name ~ '^[0-9]{4,}$'
       OR client_name ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
    """
)
print('blanked_remaining_junk', cur.rowcount)

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
print('remaining_junk', cur.fetchone()[0])

cur.close()
conn.close()
