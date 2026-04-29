import re
from pathlib import Path
import psycopg2

conn = psycopg2.connect(
    host='ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    port=5432,
    database='neondb',
    user='neondb_owner',
    password='npg_rlL0yK9pvfCW',
    sslmode='require',
)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
real_tables = {row[0].lower() for row in cur.fetchall()}
conn.close()

roots = [Path('desktop_app'), Path('modern_backend')]
exclude = re.compile(r'backup|CLEAN|_tmp|__tmp|smoke_test|\.py\.')

string_pat = re.compile(
    r"(?is)(?:'''(.*?)'''|\"\"\"(.*?)\"\"\"|'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\")"
)
sql_hint_pat = re.compile(r'\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|JOIN|FROM|INTO)\b', re.IGNORECASE)
table_pat = re.compile(r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+([a-zA-Z_][a-zA-Z0-9_\."`\[\]-]*)', re.IGNORECASE)

stop_tokens = {
    'select', 'where', 'order', 'group', 'limit', 'values', 'set', 'and', 'or',
    'as', 'on', 'by', 'now', 'true', 'false'
}

refs = {}

for root in roots:
    if not root.exists():
        continue
    for f in root.rglob('*.py'):
        if exclude.search(f.name):
            continue
        try:
            src = f.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        for m in string_pat.finditer(src):
            s = next((g for g in m.groups() if g is not None), '')
            if not s:
                continue
            if not sql_hint_pat.search(s):
                continue

            for tm in table_pat.finditer(s):
                token = tm.group(1).strip().strip(',;()')
                token = token.replace('"', '').replace("'", '').replace('`', '')
                token = token.replace('[', '').replace(']', '')
                token = token.split('.')[-1]
                token = token.lower().strip('_')

                if not token or token in stop_tokens:
                    continue
                if not re.fullmatch(r'[a-z][a-z0-9_]*', token):
                    continue
                if not ('_' in token or (len(token) > 4 and token.isalnum())):
                    continue

                rel = f.as_posix()
                refs.setdefault(token, rel)

missing = {t: refs[t] for t in refs if t not in real_tables}

print(f"Real tables in DB: {len(real_tables)}")
print(f"Distinct table names referenced in SQL strings: {len(refs)}")
print(f"Referenced but NOT in DB: {len(missing)}")
for t in sorted(missing):
    print(f"{t}: {missing[t]}")
