import psycopg2

conn = psycopg2.connect(
    host='192.168.1.176',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

# Before profile
cur.execute(
    """
    SELECT
      COUNT(*) FILTER (WHERE COALESCE(TRIM(client_name), '') = '') AS blank_name,
      COUNT(*) FILTER (
        WHERE COALESCE(TRIM(client_name), '') ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
      ) AS datetime_like,
      COUNT(*) FILTER (WHERE client_name LIKE '"-%') AS quoted_dash
    FROM clients
    """
)
print('before_profile', cur.fetchone())

# 1) Fill blank names from contact-name source.
cur.execute(
    """
    UPDATE clients
    SET client_name = TRIM(name),
        updated_at = NOW()
    WHERE COALESCE(TRIM(client_name), '') = ''
      AND COALESCE(TRIM(name), '') <> ''
    """
)
print('updated_blank_from_name', cur.rowcount)

# 2) Replace datetime-like junk with contact-name source.
cur.execute(
    """
    UPDATE clients
    SET client_name = TRIM(name),
        updated_at = NOW()
    WHERE COALESCE(TRIM(client_name), '') ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
      AND COALESCE(TRIM(name), '') <> ''
    """
)
print('updated_datetime_from_name', cur.rowcount)

# 3) Replace malformed quoted-dash junk values.
cur.execute(
    """
    UPDATE clients
    SET client_name = TRIM(name),
        updated_at = NOW()
    WHERE client_name LIKE '"-%'
      AND COALESCE(TRIM(name), '') <> ''
    """
)
print('updated_quoted_dash_from_name', cur.rowcount)

conn.commit()

cur.execute(
    """
    SELECT
      COUNT(*) FILTER (WHERE COALESCE(TRIM(client_name), '') = '') AS blank_name,
      COUNT(*) FILTER (
        WHERE COALESCE(TRIM(client_name), '') ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
      ) AS datetime_like,
      COUNT(*) FILTER (WHERE client_name LIKE '"-%') AS quoted_dash
    FROM clients
    """
)
print('after_profile', cur.fetchone())

# Show a quick sample of remaining suspicious names.
cur.execute(
    """
    SELECT client_id, client_name, name
    FROM clients
    WHERE COALESCE(TRIM(client_name), '') ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$'
       OR client_name LIKE '"-%'
    ORDER BY client_id
    LIMIT 20
    """
)
rows = cur.fetchall()
print('remaining_suspicious_sample', len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
