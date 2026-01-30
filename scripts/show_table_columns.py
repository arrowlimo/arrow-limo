#!/usr/bin/env python3
import psycopg2, sys

def main():
    table = sys.argv[1] if len(sys.argv) > 1 else 'receipts'
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    rows = cur.fetchall()
    print(f"Columns for {table}:")
    for name, dtype in rows:
        print(f"  {name}: {dtype}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
