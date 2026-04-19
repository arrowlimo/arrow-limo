import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

IN_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")

if not IN_CSV.exists():
    raise FileNotFoundError(IN_CSV)

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

# Map candidate_name groups to their new category, status, and notes
CLASSIFICATIONS = {
    "MIKE WOODROW": {
        "category": "RENT",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Rent e-transfers (not driver pay)",
    },
    "VANESSA THOMAS": {
        "category": "VENDOR_REPAYMENT",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Heffner secretary - NSF replacement e-transfers",
    },
    "BRITT": {
        "category": "DRIVER_PAY_REIMBURSEMENT",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Brittany Peacock (driver)",
    },
    "MUNDY DIANNE": {
        "category": "TRANSFER_SPOUSE",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Dave Mundy's wife - float/pay transfer",
    },
    "SAM RONEY": {
        "category": "2550",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Dispatcher reimbursement - non-payroll (PD7/T4 handled in driver pay management)",
    },
    "DAVE MUNDY": {
        "category": "DRIVER_PAY_REIMBURSEMENT",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Driver - confirmed driver pay",
    },
    "FEE": {
        "category": "BANK_FEE",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Bank e-transfer fees",
    },
    "KEVIN SPROULE": {
        "category": "VENDOR_PROFESSIONAL",
        "status": "MANUAL_CLASSIFIED",
        "notes": "Kevin Sproule (lawyer) - professional services",
    },
}

# Group rows by candidate_name, collect transaction_ids
groups_to_apply = {name: [] for name in CLASSIFICATIONS.keys()}

with IN_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        cand = (r.get("candidate_name") or "").strip()
        if cand in groups_to_apply:
            trans_id = (r.get("transaction_id") or "").strip()
            if trans_id:
                groups_to_apply[cand].append(int(trans_id))

# Apply updates to database
conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

total_updated = 0
total_amount = 0.0

for candidate_name, trans_ids in groups_to_apply.items():
    if not trans_ids:
        print(f"✗ {candidate_name}: No transaction_ids found in CSV")
        continue

    classification = CLASSIFICATIONS[candidate_name]

    # Update all matching transactions
    sql = """
    UPDATE banking_transactions
    SET category = %s,
        reconciliation_status = %s,
        reconciliation_notes = %s,
        updated_at = NOW()
    WHERE transaction_id = ANY(%s)
    RETURNING transaction_id, debit_amount;
    """

    cur.execute(
        sql,
        (
            classification["category"],
            classification["status"],
            classification["notes"],
            trans_ids,
        ),
    )

    rows = cur.fetchall()
    count = len(rows)
    amount = sum(float(r["debit_amount"] or 0) for r in rows)

    if count > 0:
        print(
            f"✓ {candidate_name}: {count} rows, ${amount:,.2f} → {classification['category']}"
        )
        total_updated += count
        total_amount += amount
    else:
        print(f"✗ {candidate_name}: Update failed for {len(trans_ids)} transaction IDs")

conn.commit()
cur.close()
conn.close()

print(f"\n{'='*80}")
print(f"TOTAL_UPDATED: {total_updated} rows, ${total_amount:,.2f}")
print(f"{'='*80}")
