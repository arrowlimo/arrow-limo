import psycopg2
from psycopg2.extras import RealDictCursor

DB_PARAMS = {
    "host": "localhost",
    "port": 5432,
    "database": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}


def run_update(cur, label, sql, params):
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    rows = cur.fetchall()
    count = len(rows)
    amt = sum(float(r["debit_amount"] or 0) for r in rows)
    print(f"{label}: {count} rows, ${amt:,.2f}")
    return count, amt


conn = psycopg2.connect(**DB_PARAMS)
cur = conn.cursor(cursor_factory=RealDictCursor)

total_count = 0
total_amt = 0.0

# 1) E-TRANSFER STOP fees -> BANK_FEE
sql_stop_fee = """
UPDATE banking_transactions
SET category = 'BANK_FEE',
    reconciliation_status = 'MANUAL_CLASSIFIED',
    reconciliation_notes = 'E-TRANSFER STOP fee (scheduled payment stopped)',
    updated_at = NOW()
WHERE debit_amount > 0
  AND receipt_id IS NULL
  AND (
        description ILIKE '%E-TRANSFER STOP SC%'
        OR description ILIKE '%Branch Transaction E-TRANSFER STOP SC PER ITEM%'
      )
  AND debit_amount <= 10
  AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
RETURNING transaction_id, debit_amount;
"""

c, a = run_update(cur, "STOP_FEE_TO_BANK_FEE", sql_stop_fee, ())
total_count += c
total_amt += a

# 2) Any e-transfer to David Richard -> related-party reimbursement waterfall bucket
sql_david = """
UPDATE banking_transactions
SET category = '2550',
    reconciliation_status = 'MANUAL_CLASSIFIED',
    reconciliation_notes = 'David Richard family reimbursement (waterfall/cash-box)',
    updated_at = NOW()
WHERE debit_amount > 0
  AND receipt_id IS NULL
  AND (
        description ILIKE '%etransfer%'
        OR description ILIKE '%e-transfer%'
        OR description ILIKE '%email transfer%'
      )
  AND description ILIKE '%david richard%'
  AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
RETURNING transaction_id, debit_amount;
"""

c, a = run_update(cur, "DAVID_RICHARD_TO_2550_RELATED_PARTY", sql_david, ())
total_count += c
total_amt += a

# 3) Easy obvious vendor/service names in the remaining tail
EASY_VENDOR_PATTERNS = [
    ("TJ_S_TOWING", "%tj%towing%", "VENDOR_SERVICE", "Towing service"),
    ("TRIO_TOWING", "%trio towing%", "VENDOR_SERVICE", "Towing service"),
    ("ACTION_TOWING", "%action towing%", "VENDOR_SERVICE", "Towing service"),
    ("DRAIN_DOCTOR", "%drain doctor%", "VENDOR_SERVICE", "Drain/plumbing service"),
    ("SIERRA_SEPTIC", "%sierra septic%", "VENDOR_SERVICE", "Septic service"),
    ("FIRE_ALERT", "%fire alert%", "VENDOR_SERVICE", "Alarm/fire service"),
    ("TERRA_CANWEST", "%terra canwest%", "VENDOR_SERVICE", "Production service vendor"),
    ("BRADEN_EQUITIES", "%braden equities%", "VENDOR_SERVICE", "Contractor/vendor service"),
    ("ONE_TIME_CONTACT_VARIANT", "%one-time contact%", "VENDOR_ONE_TIME_PAYMENT", "One-time vendor payment"),
    ("ONE_TIME_CONTACT_VARIANT2", "%one time contact%", "VENDOR_ONE_TIME_PAYMENT", "One-time vendor payment"),
    ("AARON_CLEMENTS_AUDITOR", "%aaron clements%", "VENDOR_PROFESSIONAL", "Audit/professional service"),
]

sql_pattern = """
UPDATE banking_transactions
SET category = %s,
    reconciliation_status = 'MANUAL_CLASSIFIED',
    reconciliation_notes = %s,
    updated_at = NOW()
WHERE debit_amount > 0
  AND receipt_id IS NULL
  AND (
        description ILIKE '%%etransfer%%'
        OR description ILIKE '%%e-transfer%%'
        OR description ILIKE '%%email transfer%%'
      )
  AND description ILIKE %s
  AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
RETURNING transaction_id, debit_amount;
"""

for label, pattern, category, note in EASY_VENDOR_PATTERNS:
    c, a = run_update(cur, label, sql_pattern, (category, note, pattern))
    total_count += c
    total_amt += a

conn.commit()
cur.close()
conn.close()

print("=" * 80)
print(f"TOTAL_UPDATED: {total_count} rows, ${total_amt:,.2f}")
print("=" * 80)
