import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

# Delete incorrect NSF entry
cur.execute("""
    DELETE FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND transaction_date = '2013-06-18' 
    AND debit_amount = 296351.0 
    AND description = 'RETURNED NSF CHEQUE'
""")
print(f"Deleted {cur.rowcount} incorrect NSF entry")

# Insert corrected NSF entry
import hashlib
from datetime import date

txn_date = date(2013, 6, 18)
desc = "RETURNED NSF CHEQUE"
amount = 2963.51
source_hash = hashlib.sha256(f"{txn_date.isoformat()}|{desc}|{amount:.2f}".encode("utf-8")).hexdigest()

cur.execute("""
    INSERT INTO banking_transactions (
        account_number, transaction_date, description,
        debit_amount, credit_amount, source_hash
    ) VALUES (%s, %s, %s, %s, %s, %s)
""", ('903990106011', txn_date, desc, amount, None, source_hash))

print(f"Inserted corrected NSF entry: ${amount:.2f}")

conn.commit()
conn.close()
