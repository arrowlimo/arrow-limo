import psycopg2
from psycopg2.extras import RealDictCursor
import os

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

conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

total_updated = 0
total_amount = 0.0

for candidate_name, classification in CLASSIFICATIONS.items():
    # Find all banking transactions with matching candidate_name in reconciliation_notes
    sql = """
    UPDATE banking_transactions
    SET category = %s,
        reconciliation_status = %s,
        reconciliation_notes = %s,
        updated_at = NOW()
    WHERE reconciliation_notes ILIKE %s
      AND reconciliation_status IN ('DRIVER_PAY_FUZZY', 'MANUAL_REVIEW', 'TRANSFER_REVIEW')
    RETURNING transaction_id, debit_amount;
    """

    search_pattern = f"candidate_name={candidate_name}%"
    
    cur.execute(
        sql,
        (
            classification["category"],
            classification["status"],
            classification["notes"],
            search_pattern,
        ),
    )

    rows = cur.fetchall()
    count = len(rows)
    amount = sum(float(r["debit_amount"] or 0) for r in rows)

    if count > 0:
        print(f"✓ {candidate_name}: {count} rows, ${amount:,.2f} → {classification['category']}")
        total_updated += count
        total_amount += amount
    else:
        print(f"✗ {candidate_name}: No rows found (maybe different pattern?)")

conn.commit()
cur.close()
conn.close()

print(f"\n{'='*80}")
print(f"TOTAL_UPDATED: {total_updated} rows, ${total_amount:,.2f}")
print(f"{'='*80}")
