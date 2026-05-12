from pathlib import Path
import subprocess
import os
import urllib.parse
from dotenv import dotenv_values
import psycopg

base = Path(r'L:/limo')
neon_env = dotenv_values(base / '.env.neon')

host = neon_env.get('DB_HOST')
user = neon_env.get('DB_USER', 'neondb_owner')
password = neon_env.get('DB_PASSWORD', '')
db = neon_env.get('DB_NAME', 'neondb')
if not host or 'neon.tech' not in host:
    raise SystemExit('Invalid Neon config in .env.neon')

local_user = 'postgres'
local_pass = (
    os.environ.get('LOCAL_DB_PASSWORD')
    or os.environ.get('POSTGRES_PASSWORD')
    or os.environ.get('ALMS_DB_PASSWORD')
    or ''
)
local_db = 'almsdata'

# Keep host exactly as configured for Neon; force local sslmode=disable.
neon_uri = (
    'postgresql://' + urllib.parse.quote_plus(user) + ':' + urllib.parse.quote_plus(password)
    + '@' + host + ':5432/' + urllib.parse.quote_plus(db) + '?sslmode=require'
)
local_uri = (
    'postgresql://' + urllib.parse.quote_plus(local_user) + ':' + urllib.parse.quote_plus(local_pass)
    + '@localhost:5432/' + urllib.parse.quote_plus(local_db) + '?sslmode=disable'
)

dump_path = base / 'tmp' / 'neon_to_local_recovery.dump'
print(f'Dumping Neon to {dump_path} ...', flush=True)
subprocess.run([
    'pg_dump', '--dbname', neon_uri, '-n', 'public', '--format=custom',
    '--file', str(dump_path), '--no-owner', '--no-privileges'
], check=True)
print('Dump complete', flush=True)

print('Wiping local public schema ...', flush=True)
with psycopg.connect(host='localhost', port=5432, dbname=local_db, user=local_user, password=local_pass, sslmode='disable', autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute('DROP SCHEMA IF EXISTS public CASCADE')
        cur.execute('CREATE SCHEMA public')
        cur.execute('GRANT ALL ON SCHEMA public TO CURRENT_USER')
        cur.execute('GRANT ALL ON SCHEMA public TO public')
print('Local schema recreated', flush=True)

for section in ('pre-data', 'data', 'post-data'):
    print(f'Restoring section: {section}', flush=True)
    subprocess.run([
        'pg_restore', '--dbname', local_uri, '--no-owner', '--no-privileges',
        '--exit-on-error', f'--section={section}', str(dump_path)
    ], check=True)

print('Recovery restore complete', flush=True)
