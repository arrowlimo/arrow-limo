#!/usr/bin/env python3
"""
Report receipts paid by David Richard and reimbursement status.
Criteria:
- Mentions 'David Richard' in vendor_name or description
- Show owner_personal_amount, is_personal_purchase, is_driver_reimbursement, reimbursed_via, reimbursement_date
- Show cash_box_transaction_id if present

This is read-only.
"""

import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REDACTED***")
cur = conn.cursor()

# Determine available columns to avoid errors if schema differs
cur.execute("""
  SELECT column_name FROM information_schema.columns
  WHERE table_name = 'receipts'
""")
cols = {row[0] for row in cur.fetchall()}

select_parts = [
  "receipt_id", "receipt_date", "vendor_name", "description",
  "gross_amount"
]
if 'owner_personal_amount' in cols:
  select_parts.append("owner_personal_amount")
else:
  select_parts.append("NULL AS owner_personal_amount")
if 'is_personal_purchase' in cols:
  select_parts.append("is_personal_purchase")
else:
  select_parts.append("NULL AS is_personal_purchase")
if 'is_driver_reimbursement' in cols:
  select_parts.append("is_driver_reimbursement")
else:
  select_parts.append("NULL AS is_driver_reimbursement")
if 'reimbursed_via' in cols:
  select_parts.append("reimbursed_via")
else:
  select_parts.append("NULL AS reimbursed_via")
if 'reimbursement_date' in cols:
  select_parts.append("reimbursement_date")
else:
  select_parts.append("NULL AS reimbursement_date")
if 'cash_box_transaction_id' in cols:
  select_parts.append("cash_box_transaction_id")
else:
  select_parts.append("NULL AS cash_box_transaction_id")
if 'banking_transaction_id' in cols:
  select_parts.append("banking_transaction_id")
else:
  select_parts.append("NULL AS banking_transaction_id")

select_list = ", ".join(select_parts)

cur.execute(
  f"""
  SELECT {select_list}
  FROM receipts
  WHERE vendor_name ILIKE '%David Richard%' OR description ILIKE '%David Richard%'
  ORDER BY receipt_date DESC
  LIMIT 50
  """
)
rows = cur.fetchall()

print("Recent receipts mentioning David Richard (up to 50):")
print("-"*80)
for r in rows:
  # Align indexes with select_parts order
  rid = r[0]; rdate = r[1]; vname = r[2]; desc = r[3]; gross = r[4]
  owner_amt = r[5]; is_personal = r[6]; is_reimb = r[7]; via = r[8]; reimb_date = r[9]; cash_box_id = r[10]; btid = r[11]
  print(f"#{rid} | {rdate} | ${gross:,.2f} | owner_personal=${(owner_amt or 0):,.2f} | personal={is_personal} | reimb={is_reimb} | via={via or ''} | reimb_date={reimb_date or ''} | cash_box_id={cash_box_id or ''} | btid={btid or ''}")

cur.close(); conn.close()
