"""List remaining payments with reserve_number not present in charters."""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

SQL = """
SELECT p.reserve_number, COUNT(*) AS cnt
FROM payments p
WHERE p.reserve_number IS NOT NULL
  AND NOT EXISTS (
        SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
  )
GROUP BY p.reserve_number
ORDER BY cnt DESC, p.reserve_number;
"""


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(SQL)
    rows = cur.fetchall()
    for rn, cnt in rows:
        print(f"{rn}\t{cnt}")
    conn.close()


if __name__ == "__main__":
    main()
