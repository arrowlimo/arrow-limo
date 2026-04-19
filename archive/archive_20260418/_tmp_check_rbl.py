import psycopg2
from collections import defaultdict

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur  = conn.cursor()
cur2 = conn.cursor()

dup_ids = [62577, 62786, 88233, 88254, 88285, 88308, 88311, 88319, 88321, 88324,
           88329, 88332, 88338, 88352, 88364, 88373, 88375, 88383, 88387, 88407,
           88420, 88426, 88435, 88437, 88442, 88446, 88454, 88468, 88470, 88471,
           88484, 88486, 88487, 88493, 88505, 88517, 88521, 88525, 88526, 88529,
           88530, 88534, 88543, 88547, 88550, 88553, 88565, 88575, 88576, 88579,
           88585, 88586, 88593, 88602, 88618, 88630, 88633, 88636, 88642, 88644,
           88649, 88653, 88658, 88670, 88673, 88677, 88682, 88684, 88690, 88696, 88699]

cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='receipt_banking_links' ORDER BY ordinal_position"
)
cols = [r[0] for r in cur.fetchall()]
print("receipt_banking_links columns:", cols)

cur.execute(
    "SELECT COUNT(*) FROM receipt_banking_links WHERE transaction_id = ANY(%s)",
    (dup_ids,)
)
cnt = cur.fetchone()[0]
print(f"Links referencing dup rows: {cnt}")

cur.execute(
    "SELECT * FROM receipt_banking_links WHERE transaction_id = ANY(%s) LIMIT 10",
    (dup_ids,)
)
for r in cur.fetchall():
    print(" ", r)

# Also check for any other FK tables
cur.execute(
    "SELECT tc.table_name, kcu.column_name "
    "FROM information_schema.table_constraints tc "
    "JOIN information_schema.key_column_usage kcu "
    "  ON tc.constraint_name = kcu.constraint_name "
    "JOIN information_schema.referential_constraints rc "
    "  ON tc.constraint_name = rc.constraint_name "
    "JOIN information_schema.key_column_usage ccu "
    "  ON ccu.constraint_name = rc.unique_constraint_name "
    "WHERE tc.constraint_type = 'FOREIGN KEY' "
    "  AND ccu.table_name = 'banking_transactions' "
    "  AND ccu.column_name = 'transaction_id'"
)
fks = cur.fetchall()
print("\nAll FK references TO banking_transactions.transaction_id:")
for r in fks:
    print(f"  {r[0]}.{r[1]}")

conn.close()
