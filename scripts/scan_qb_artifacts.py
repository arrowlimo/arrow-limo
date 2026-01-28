import psycopg2
from psycopg2 import sql

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("SCANNING FOR POSSIBLE QUICKBOOKS ARTIFACTS (text columns)")
print("="*100 + "\n")

# Identify text-like columns in public schema
cur.execute(
    """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND data_type IN ('character varying', 'text', 'character')
    ORDER BY table_name, ordinal_position
    """
)
text_cols = cur.fetchall()

patterns = [
    # QuickBooks internal IDs like 8000001E-1412270372
    ("QB-ID pattern", r"^8[0-9A-Z]{6,7}-[0-9]{6,12}$"),
    # Words/phrases linked to QuickBooks
    ("contains 'QuickBooks'", r"QuickBooks"),
    ("contains 'Quick Books'", r"Quick Books"),
    ("contains 'QBO'", r"QBO"),
    ("contains 'Intuit'", r"Intuit"),
    ("contains 'QB'", r"\bQB\b"),
]

findings = []

for table, col, dtype in text_cols:
    for label, regex in patterns:
        q = sql.SQL("SELECT count(*) FROM {tbl} WHERE {col} ~* %s").format(
            tbl=sql.Identifier(table),
            col=sql.Identifier(col),
        )
        cur.execute(q, (regex,))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            findings.append((table, col, label, cnt, regex))

print(f"Found {len(findings)} table/column hits\n")

# Show summary and a few sample values per hit
for table, col, label, cnt, regex in findings:
    print(f"[{table}.{col}] {label} | matches: {cnt}")
    # Fetch sample rows
    sample_q = sql.SQL(
        "SELECT {col} FROM {tbl} WHERE {col} ~* %s AND {col} IS NOT NULL LIMIT 5"
    ).format(tbl=sql.Identifier(table), col=sql.Identifier(col))
    cur.execute(sample_q, (regex,))
    samples = cur.fetchall()
    for s in samples:
        val = s[0]
        snippet = val if len(val) <= 80 else val[:77] + "..."
        print(f"  • {snippet}")
    print("-")

print("\n" + "="*100)
print("SCAN COMPLETE")
print("="*100 + "\n")

conn.close()
