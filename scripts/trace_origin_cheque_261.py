#!/usr/bin/env python
import psycopg2, os, json

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

backup_path = r"l:\limo\almsdata_backup_2012_CIBC_0228362_20260118_140900.json"

def query_cheque_register():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, cheque_number, cheque_date, amount, payee, status,
               account_number, memo, banking_transaction_id, created_at
        FROM cheque_register
        WHERE cheque_number = '261'
        ORDER BY cheque_date NULLS LAST
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def search_backup_json():
    try:
        with open(backup_path, 'r') as f:
            data = json.load(f)
        hits = []
        # Try common structures
        def scan(obj):
            if isinstance(obj, dict):
                # direct match in cheque-like dict
                if str(obj.get('cheque_number')) == '261':
                    hits.append(obj)
                for v in obj.values():
                    scan(v)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)
        scan(data)
        return hits
    except Exception as e:
        return [f"Backup read error: {e}"]

if __name__ == '__main__':
    print("=== Cheque Register (DB) for cheque_number 261 ===")
    for r in query_cheque_register():
        print(r)
    print("\n=== Backup JSON search (almsdata_backup_2012_CIBC_0228362_20260118_140900.json) ===")
    for h in search_backup_json():
        print(h)
