import psycopg2

DBS = {
    'local': dict(host='localhost', port=5432, database='almsdata', user='postgres', password='ArrowLimousine'),
    'cloud_remote': dict(host='192.168.1.176', port=5432, database='almsdata', user='postgres', password='ArrowLimousine'),
    'neon': dict(host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech', port=5432, database='neondb', user='neondb_owner', password='npg_rlL0yK9pvfCW', sslmode='require'),
}

TARGET_IDS = [
    1709, 6557, 6558, 6559, 6560, 6566, 6567, 6568, 6569, 6570, 6571, 6572,
    6573, 6574, 6575, 6576, 6577, 6578, 6579, 6581, 6582, 6583, 6585, 6586,
    6587, 9258, 9259, 9260,
]

PROFILE_SQL = """
SELECT
  COUNT(*) AS total_clients,
  COUNT(*) FILTER (WHERE COALESCE(TRIM(client_name), '') = '') AS blank_client_name,
  COUNT(*) FILTER (WHERE client_name LIKE '"%') AS quoted_prefix,
  COUNT(*) FILTER (WHERE client_name ~ '^[0-9]{4,}$') AS numeric_only,
  COUNT(*) FILTER (WHERE client_name ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (AM|PM)$') AS datetime_like
FROM clients
"""

IDS_SQL = """
SELECT client_id, client_name
FROM clients
WHERE client_id = ANY(%s)
ORDER BY client_id
"""

for label, cfg in DBS.items():
    conn = psycopg2.connect(**cfg)
    cur = conn.cursor()
    cur.execute(PROFILE_SQL)
    print(f"\n[{label}] profile: {cur.fetchone()}")
    cur.execute(IDS_SQL, (TARGET_IDS,))
    rows = cur.fetchall()
    print(f"[{label}] target_rows={len(rows)}")
    for r in rows:
        print(r)
    cur.close()
    conn.close()
