#!/usr/bin/env python
import psycopg2

def print_not_null(table):
    conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
    cur=conn.cursor()
    cur.execute("""
    select column_name, is_nullable, column_default
    from information_schema.columns
    where table_name=%s
    order by ordinal_position
    """, (table,))
    print(f"\nTable: {table}")
    for name, nullable, default in cur.fetchall():
        if nullable=='NO':
            print(f"  NOT NULL: {name} default={default}")
    cur.close(); conn.close()

def collect_not_null(table):
    conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
    cur=conn.cursor()
    cur.execute("""
    select column_name, is_nullable, column_default
    from information_schema.columns
    where table_name=%s
    order by ordinal_position
    """, (table,))
    rows=[(name,default) for name,nullable,default in cur.fetchall() if nullable=='NO']
    cur.close(); conn.close()
    return rows

def main():
    output=[]
    for table in ['charters','charter_charges']:
        rows=collect_not_null(table)
        output.append((table, rows))

    # Write to file for reliable retrieval even if terminal output is suppressed
    out_path = r"L:\limo\reports\charter_notnull.txt"
    lines=[]
    for table, rows in output:
        lines.append(f"Table: {table}\n")
        for name, default in rows:
            lines.append(f"NOT NULL: {name} default={default}\n")
        lines.append("\n")
    with open(out_path,"w",encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Wrote {out_path}")

    # Also print to stdout
    for table, rows in output:
        print(f"\nTable: {table}")
        for name, default in rows:
            print(f"  NOT NULL: {name} default={default}")

if __name__ == '__main__':
    main()
