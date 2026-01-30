#!/usr/bin/env python3
"""
Show cheque numbers sequence in register to identify gaps.
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()

    print('=' * 80)
    print('CHEQUE NUMBERS IN REGISTER (200-280)')
    print('=' * 80)
    print()

    cur.execute('''
        SELECT cheque_number, amount, payee
        FROM cheque_register
        WHERE cheque_number ~ '^[0-9]+$'
        AND cheque_number::int BETWEEN 200 AND 280
        ORDER BY cheque_number::int
    ''')
    
    cheques = cur.fetchall()
    existing_numbers = set(int(c[0]) for c in cheques)
    
    for row in cheques:
        print(f'{row[0]:>3}: ${row[1]:>10.2f} | {row[2] if row[2] else "UNKNOWN"}')
    
    print()
    print('=' * 80)
    print('MISSING CHEQUE NUMBERS IN SEQUENCE')
    print('=' * 80)
    print()
    
    all_numbers = set(range(200, 281))
    missing = sorted(all_numbers - existing_numbers)
    
    print(f'Total missing: {len(missing)}')
    print(f'Missing numbers: {", ".join(map(str, missing))}')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
