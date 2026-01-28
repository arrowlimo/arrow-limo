"""Export live schema (all tables/columns) for documentation cross-check."""
import os
import json
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute(
    """
    SELECT table_name, column_name, data_type, is_nullable, character_maximum_length, column_default
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
    """
)
rows = cur.fetchall()

schema = defaultdict(list)
for table, col, dtype, nullable, maxlen, default in rows:
    schema[table].append({
        "column": col,
        "type": dtype,
        "nullable": nullable,
        "max_length": maxlen,
        "default": default
    })

output_path = "reports/schema_snapshot.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=2, default=str)

print(f"Saved schema snapshot for {len(schema)} tables to {output_path}")

cur.close()
conn.close()
