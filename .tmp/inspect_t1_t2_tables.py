import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.').resolve()))

for line in Path('.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

from modern_backend.app.db import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
all_tables = [r[0] for r in cur.fetchall()]
for name in all_tables:
    if 't1' in name.lower() or 't2' in name.lower():
        print(name)
cur.close()
conn.close()
