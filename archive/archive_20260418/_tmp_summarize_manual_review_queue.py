import csv
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

path = Path(r"l:\limo\data\intake\unlinked_debits_manual_review_queue.csv")
if not path.exists():
    raise FileNotFoundError(path)

with path.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    print("HEADERS")
    print("|".join(headers))

    by_action = Counter()
    by_group = Counter()
    amt_action = defaultdict(Decimal)
    amt_group = defaultdict(Decimal)

    rows = list(reader)

for r in rows:
    action = (r.get("recommended_action") or "").strip() or "<blank>"
    group = (r.get("group_name") or r.get("group") or "").strip() or "<blank>"
    amt_raw = (r.get("debit_amount") or r.get("amount") or "0").replace(",", "").strip()
    try:
        amt = Decimal(amt_raw)
    except (InvalidOperation, ValueError):
        amt = Decimal("0")

    by_action[action] += 1
    by_group[group] += 1
    amt_action[action] += amt
    amt_group[group] += amt

print(f"TOTAL_ROWS={len(rows)}")
print("ACTIONS")
for k, v in by_action.most_common(20):
    print(f"{k}|{v}|{amt_action[k]}")

print("GROUPS")
for k, v in by_group.most_common(30):
    print(f"{k}|{v}|{amt_group[k]}")
