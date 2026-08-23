import os
from modern_backend.app.db import get_connection

conn = get_connection()
cur = conn.cursor()
print('connected', conn)
for table in ['t2_return_metadata','t2_schedule_data','t2_deductibility_audit','t2_deductibility_audit_gl','t2_deductibility_audit_warning']:
    try:
        cur.execute("select to_regclass(%s)", (table,))
        print(table, '->', cur.fetchone()[0])
    except Exception as e:
        print(table, 'ERR', e)

cur.close()
conn.close()
