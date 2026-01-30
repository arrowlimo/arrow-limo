import psycopg2, os
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database=os.getenv('DB_NAME','almsdata'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD','***REDACTED***'))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    expected_map = {
        12202: '013305', 16078: '017186', 18550: '019572', 18606: '019627', 18608: '019628',
        18607: '019629', 18614: '019634', 18609: '019635', 18610: '019636', 18613: '019637',
        18611: '019640', 18612: '019642', 18624: '019646', 18622: '019647', 18616: '019648',
        18615: '019649', 18617: '019650', 18623: '019653', 18620: '019654', 18625: '019656',
        18618: '019659', 18626: '019661', 18621: '019662', 18619: '019663', 18605: '019667',
        18627: '019668'
    }
    print('='*100) ; print('CURRENT RESERVE NUMBER STATE (26 CHARTERS)') ; print('='*100)
    print(f"{'CharterID':<9} {'Stored':<12} {'Expected':<12} {'Match':<6} {'Total_Due':>12}")
    print('-'*60)
    mismatches=[]
    for cid, exp in expected_map.items():
        cur.execute('SELECT charter_id,reserve_number,total_amount_due FROM charters WHERE charter_id=%s',(cid,))
        row=cur.fetchone()
        if not row:
            print(f"{cid:<9} {'(missing)':<12} {exp:<12} {'-':<6} {'-':>12}")
            continue
        stored=row['reserve_number'] or ''
        match = 'OK' if stored==exp else 'DIFF'
        total=row['total_amount_due'] if row['total_amount_due'] is not None else 0
        print(f"{cid:<9} {stored:<12} {exp:<12} {match:<6} {total:12.2f}")
        if match=='DIFF':
            mismatches.append((cid,stored,exp))
    print('-'*60)
    print(f"Mismatches: {len(mismatches)}")
    conflicts=[]
    for cid, stored, exp in mismatches:
        cur.execute('SELECT charter_id FROM charters WHERE reserve_number=%s AND charter_id<>%s',(exp,cid))
        conflict=cur.fetchone()
        if conflict:
            conflicts.append((cid,exp,conflict['charter_id']))
    if conflicts:
        print('\nCONFLICTS (expected reserve already used):')
        for cid, exp, other in conflicts:
            print(f"Expected {exp} for {cid} already used by charter {other}")
    else:
        print('\nNo conflicts: All expected reserve_numbers are free to use.')
    cur.close(); conn.close()

if __name__=='__main__':
    main()
