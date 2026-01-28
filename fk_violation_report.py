"""Report potential FK violations for core tables before adding constraints."""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

CHECKS = [
    (
        "payments.reserve_number -> charters.reserve_number",
        "payments",
        "reserve_number",
        """
        SELECT COUNT(*)
        FROM payments p
        WHERE p.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
          );
        """,
    ),
    (
        "payments.banking_transaction_id -> banking_transactions.transaction_id",
        "payments",
        "banking_transaction_id",
        """
        SELECT COUNT(*)
        FROM payments p
        WHERE p.banking_transaction_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM banking_transactions b
                WHERE b.transaction_id = p.banking_transaction_id
          );
        """,
    ),
    (
        "receipts.reserve_number -> charters.reserve_number",
        "receipts",
        "reserve_number",
        """
        SELECT COUNT(*)
        FROM receipts r
        WHERE r.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = r.reserve_number
          );
        """,
    ),
    (
        "receipts.vehicle_id -> vehicles.vehicle_id",
        "receipts",
        "vehicle_id",
        """
        SELECT COUNT(*)
        FROM receipts r
        WHERE r.vehicle_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM vehicles v WHERE v.vehicle_id = r.vehicle_id
          );
        """,
    ),
    (
        "charter_charges.reserve_number -> charters.reserve_number",
        "charter_charges",
        "reserve_number",
        """
        SELECT COUNT(*)
        FROM charter_charges cc
        WHERE cc.reserve_number IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.reserve_number = cc.reserve_number
          );
        """,
    ),
    (
        "charter_payments.payment_id -> payments.payment_id",
        "charter_payments",
        "payment_id",
        """
        SELECT COUNT(*)
        FROM charter_payments cp
        WHERE cp.payment_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.payment_id = cp.payment_id
          );
        """,
    ),
    (
        "charter_payments.charter_id numeric -> charters.charter_id",
        "charter_payments",
        "charter_id",
        """
        SELECT COUNT(*)
        FROM charter_payments cp
        WHERE cp.reserve_number IS NOT NULL
          AND cp.charter_id ~ '^[0-9]+$'
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.charter_id = cp.charter_id::integer
          );
        """,
    ),
    (
        "charter_payments.charter_id non-numeric",
        "charter_payments",
        "charter_id",
        """
        SELECT COUNT(*)
        FROM charter_payments cp
        WHERE cp.reserve_number IS NOT NULL
          AND cp.charter_id !~ '^[0-9]+$';
        """,
    ),
]


def fetch_columns(cur):
  cur.execute(
    """
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
    """
  )
  columns = {}
  for table, column in cur.fetchall():
    columns.setdefault(table, set()).add(column)
  return columns


def main():
  conn = psycopg2.connect(**DB)
  cur = conn.cursor()
  columns = fetch_columns(cur)

  print("FK violation scan (lower is better):")
  for label, table, column, sql in CHECKS:
    if column not in columns.get(table, set()):
      print(f"- {label}: SKIPPED (missing column {table}.{column})")
      continue
    cur.execute(sql)
    count = cur.fetchone()[0]
    print(f"- {label}: {count}")
  conn.close()


if __name__ == "__main__":
    main()
