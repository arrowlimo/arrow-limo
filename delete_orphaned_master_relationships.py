"""
Delete orphaned records from master_relationships.
- Removes rows pointing to non-existent charters or payments.
- Prints before/after counts.
"""

import psycopg2
from datetime import datetime

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

def count_rows(cur, table):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]

def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    print("="*80)
    print("CLEAN ORPHANED master_relationships")
    print("Started:", datetime.now())
    print("="*80)

    total_before = count_rows(cur, 'master_relationships')

    # Orphaned charter references
    cur.execute("""
        SELECT COUNT(*)
        FROM master_relationships mr
        WHERE mr.source_table = 'charters'
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.charter_id = mr.source_id
          )
    """)
    orphan_charters = cur.fetchone()[0]

    # Orphaned payment references
    cur.execute("""
        SELECT COUNT(*)
        FROM master_relationships mr
        WHERE mr.target_table = 'payments'
          AND NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.payment_id = mr.target_id
          )
    """)
    orphan_payments = cur.fetchone()[0]

    print(f"Orphaned charter refs:  {orphan_charters:,}")
    print(f"Orphaned payment refs:  {orphan_payments:,}")

    # Delete orphaned rows
    cur.execute("""
        DELETE FROM master_relationships mr
        WHERE mr.source_table = 'charters'
          AND NOT EXISTS (
                SELECT 1 FROM charters c WHERE c.charter_id = mr.source_id
          )
    """)
    deleted_charters = cur.rowcount

    cur.execute("""
        DELETE FROM master_relationships mr
        WHERE mr.target_table = 'payments'
          AND NOT EXISTS (
                SELECT 1 FROM payments p WHERE p.payment_id = mr.target_id
          )
    """)
    deleted_payments = cur.rowcount

    conn.commit()

    total_after = count_rows(cur, 'master_relationships')

    print("""
Summary:
  Deleted orphaned charter refs : {dc:,}
  Deleted orphaned payment refs : {dp:,}
  Total before                  : {tb:,}
  Total after                   : {ta:,}
  Rows removed                  : {rem:,}
""".format(dc=deleted_charters, dp=deleted_payments, tb=total_before, ta=total_after, rem=total_before-total_after))

    print("Completed:", datetime.now())
    conn.close()

if __name__ == '__main__':
    main()
