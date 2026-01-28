#!/usr/bin/env python
import psycopg2

def main():
    conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
    cur=conn.cursor()
    cur.execute("""
    select column_name, is_nullable, column_default
    from information_schema.columns
    where table_name='charters'
    order by ordinal_position
    """)
    for name, nullable, default in cur.fetchall():
        if nullable == 'NO':
            print(f"NOT NULL: {name} | default={default}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
