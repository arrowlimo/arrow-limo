import sys
from pathlib import Path
sys.path.insert(0, r'l:\limo')
import psycopg2
from psycopg2.extras import RealDictCursor
from modern_backend.app.services.pdf_generator import generate_charter_pdf

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT *
FROM charters
WHERE reserve_number = '019883'
ORDER BY charter_id DESC
LIMIT 1
""")
row = cur.fetchone()
if not row:
    raise SystemExit('No charter found for reserve 019883')

out = Path(r'l:\limo\tmp\run_charter_v21_exemption_banner.pdf')
out.write_bytes(generate_charter_pdf(dict(row)))
print(f'WROTE:{out}')
cur.close(); conn.close()

