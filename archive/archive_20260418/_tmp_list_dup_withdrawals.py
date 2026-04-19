import psycopg2, csv, os
from collections import defaultdict

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute(
    "SELECT transaction_id, transaction_date, debit_amount, description, "
    "       category, source_file, import_batch "
    "FROM banking_transactions "
    "WHERE EXTRACT(YEAR FROM transaction_date) IN (2013, 2014) "
    "  AND debit_amount IS NOT NULL AND debit_amount > 0 "
    "  AND (description ILIKE '%withdrawal%' OR description ILIKE '%money mart%') "
    "ORDER BY transaction_date, debit_amount DESC, transaction_id"
)
all_rows = cur.fetchall()

by_key = defaultdict(list)
for r in all_rows:
    by_key[(r[1], r[2])].append(r)

def is_summary(desc):
    return (desc or "").upper() in ("BANK WITHDRAWAL", "MONEY MART WITHDRAWAL")

dup_ids = []
for key, group in by_key.items():
    if len(group) > 1:
        has_detail = any(not is_summary(r[3]) for r in group)
        if has_detail:
            for r in group:
                if is_summary(r[3]):
                    dup_ids.append(r)

dup_ids.sort(key=lambda r: (r[1], r[2]))

print(f"Confirmed-duplicate BANK WITHDRAWAL rows to delete: {len(dup_ids)}")
header = f"{'Txn ID':<10} {'Date':<12} {'Amount':>11}  {'Description':<28} {'Category':<22} {'Source'}"
print(header)
print("-" * 115)
for r in dup_ids:
    print(f"{r[0]:<10} {str(r[1]):<12} ${float(r[2]):>10.2f}  {str(r[3])[:27]:<28} {str(r[4] or '')[:21]:<22} {str(r[5] or '')}")

print()
total = sum(float(r[2]) for r in dup_ids)
print(f"Total amount represented by duplicate rows: ${total:,.2f}")
print()

# Also show what the PAIRED detail rows look like (the ones we KEEP)
print("Sample pair check — detail rows KEPT alongside each duplicate:")
print("-" * 80)
shown = 0
for key, group in sorted(by_key.items(), key=lambda kv: -float(kv[0][1])):
    if len(group) > 1:
        has_detail = any(not is_summary(r[3]) for r in group)
        if has_detail:
            dup_in_group = [r for r in group if is_summary(r[3])]
            det_in_group = [r for r in group if not is_summary(r[3])]
            if dup_in_group and det_in_group:
                print(f"  Date={key[0]}  Amount=${float(key[1]):.2f}")
                for r in det_in_group:
                    print(f"    KEEP  {r[0]:<10} [{r[3][:55]}]  src={r[5] or 'NULL'}")
                for r in dup_in_group:
                    print(f"    DEL   {r[0]:<10} [{r[3][:55]}]  src={r[5] or 'NULL'}")
                shown += 1
                if shown >= 15:
                    print("  ... (showing first 15 pairs)")
                    break

# Write CSV
path = r"l:\limo\reports\cash_box_2013_2014_confirmed_dup_ids_to_delete.csv"
with open(path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["transaction_id","date","amount","description","category","source_file","import_batch"])
    for r in dup_ids:
        w.writerow(r)
print(f"\nCSV written: {path}")
conn.close()
