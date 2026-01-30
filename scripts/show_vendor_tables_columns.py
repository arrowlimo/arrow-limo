#!/usr/bin/env python
import psycopg2, os

def show_columns(table):
    conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REDACTED***'))
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (table,))
    print(f"\nColumns for {table}:")
    for row in cur.fetchall():
        print(row)
    cur.close(); conn.close()

if __name__ == '__main__':
    for t in ['vendor_accounts','vendors']:
        show_columns(t)