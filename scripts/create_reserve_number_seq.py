import sys, os
# Ensure project root path is available BEFORE import
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
  sys.path.append(PROJECT_ROOT)

from modern_backend.app.db import get_connection

SQL_EXISTS = """
SELECT sequence_name FROM information_schema.sequences
WHERE sequence_name = 'reserve_number_seq'
"""

SQL_CREATE = """
CREATE SEQUENCE reserve_number_seq
  START WITH 1
  INCREMENT BY 1
  MINVALUE 1
  MAXVALUE 999999
  CACHE 1
"""

SQL_SET = """
-- Optionally set to current max + 1
SELECT COALESCE(MAX(CAST(reserve_number AS INTEGER)), 0) + 1 FROM charters WHERE reserve_number ~ '^\\d+$'
"""

SQL_ALTER_START = """
-- Set sequence to start at next value
SELECT setval('reserve_number_seq', %s, false)
"""


def main():
  conn = get_connection()
  cur = conn.cursor()
  try:
    cur.execute(SQL_EXISTS)
    row = cur.fetchone()
    if row:
      print("reserve_number_seq already exists")
    else:
      print("Creating reserve_number_seq...")
      cur.execute(SQL_CREATE)
      # Set starting value relative to current max reserve_number
      cur.execute(SQL_SET)
      next_val = cur.fetchone()[0]
      cur.execute(SQL_ALTER_START, (next_val,))
      print(f"reserve_number_seq created and set to {next_val}")
    conn.commit()
  except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    sys.exit(1)
  finally:
    cur.close()
    conn.close()
  print("DONE")
  sys.exit(0)

if __name__ == '__main__':
  main()
