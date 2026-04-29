import os, re, psycopg2
from pathlib import Path

conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    port=5432, database='neondb', user='neondb_owner',
    password='npg_rlL0yK9pvfCW', sslmode='require'
)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
real_tables = {r[0] for r in cur.fetchall()}
conn.close()

roots = [Path('l:/limo/desktop_app'), Path('l:/limo/modern_backend')]
exclude = re.compile(r'backup|CLEAN|_tmp|__tmp|smoke_test|\.py\.')
table_refs = {}

pat = re.compile(r'(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE)
for root in roots:
    for f in root.rglob('*.py'):
        if exclude.search(f.name): continue
        src = f.read_text(encoding='utf-8', errors='ignore')
        for m in pat.finditer(src):
            t = m.group(1).lower()
            if len(t) > 3 and not t.startswith(('pg_', 'information_', 'public')):
                table_refs.setdefault(t, set()).add(f.relative_to(Path('l:/limo')).as_posix())

missing = {t: list(files)[:3] for t, files in sorted(table_refs.items()) if t not in real_tables}
print(f'Real tables in DB: {len(real_tables)}')
print(f'Distinct table names referenced in code: {len(table_refs)}')
print(f'Referenced but NOT in DB ({len(missing)}):')
for t, files in sorted(missing.items()):
    print(f'  {t}: {files[0]}')
