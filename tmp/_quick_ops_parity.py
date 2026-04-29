import psycopg
from dotenv import dotenv_values
from pathlib import Path

base = Path(r'L:/limo')
ne = dotenv_values(base / '.env.neon')

neon = {
    'host': ne.get('DB_HOST'),
    'port': int(ne.get('DB_PORT') or 5432),
    'dbname': ne.get('DB_NAME') or 'neondb',
    'user': ne.get('DB_USER') or 'neondb_owner',
    'password': ne.get('DB_PASSWORD') or '',
    'sslmode': ne.get('DB_SSLMODE') or 'require',
}

local = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': 'ArrowLimousine',
    'sslmode': 'disable',
}

ops = ['charters','charter_payments','payments','receipts','banking_transactions','vendor_invoices','clients','vehicles','employees']

with psycopg.connect(**neon) as nconn, psycopg.connect(**local) as lconn:
    with nconn.cursor() as nc, lconn.cursor() as lc:
        for t in ops:
            nc.execute(f'SELECT COUNT(*) FROM public."{t}"')
            n = nc.fetchone()[0]
            lc.execute(f'SELECT COUNT(*) FROM public."{t}"')
            l = lc.fetchone()[0]
            print(f'{t}: local={l} neon={n} delta={l-n}')
