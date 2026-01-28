import psycopg2, os, re
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***')
    )

def main():
    print(f"== Scan Client Alternative Names {datetime.now():%Y-%m-%d %H:%M:%S} ==")
    conn = get_conn(); cur = conn.cursor()

    # Introspect available columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='clients' ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    name_like_cols = [c for c in cols if 'name' in c.lower() and c.lower() != 'client_name']

    # Build dynamic select list of potential alt name columns if they exist
    candidate_cols = [c for c in ['full_name','first_name','last_name','contact_info','notes'] if c in cols]
    select_list = ', '.join(['client_id','client_name'] + candidate_cols)

    cur.execute(f"""
        SELECT {select_list}
        FROM clients
        WHERE client_name IS NULL OR TRIM(client_name)=''
    """)
    rows = cur.fetchall()

    total_blank = len(rows)
    print(f"Blank client_name rows: {total_blank}")

    source_counts = {
        'full_name':0,
        'first_last':0,
        'first_only':0,
        'contact_info':0,
        'notes_name':0,
        'none':0
    }

    samples = {k:[] for k in source_counts.keys()}

    # Precompile regex patterns
    notes_name_pattern = re.compile(r'(?i)name[:\-]\s*([A-Za-z][A-Za-z\s]{1,80})')
    contact_name_pattern = re.compile(r'^[A-Za-z][A-Za-z\s]{1,60}$')

    col_index = {c:i for i,c in enumerate(['client_id','client_name']+candidate_cols)}

    for row in rows:
        client_id = row[col_index['client_id']]
        full_name = row[col_index.get('full_name')] if 'full_name' in candidate_cols else None
        first_name = row[col_index.get('first_name')] if 'first_name' in candidate_cols else None
        last_name = row[col_index.get('last_name')] if 'last_name' in candidate_cols else None
        contact_info = row[col_index.get('contact_info')] if 'contact_info' in candidate_cols else None
        notes = row[col_index.get('notes')] if 'notes' in candidate_cols else None

        chosen = None
        # Priority order
        if full_name and str(full_name).strip():
            chosen = str(full_name).strip(); source = 'full_name'
        elif first_name and last_name and str(first_name).strip() and str(last_name).strip():
            chosen = f"{first_name.strip()} {last_name.strip()}"; source = 'first_last'
        elif first_name and str(first_name).strip():
            chosen = first_name.strip(); source = 'first_only'
        elif contact_info and isinstance(contact_info,str) and contact_name_pattern.match(contact_info.strip()):
            chosen = contact_info.strip(); source = 'contact_info'
        elif notes and isinstance(notes,str):
            m = notes_name_pattern.search(notes)
            if m:
                chosen = m.group(1).strip(); source = 'notes_name'
            else:
                source = 'none'
        else:
            source = 'none'

        source_counts[source]+=1
        if chosen and len(samples[source])<5:
            samples[source].append((client_id, chosen))
        elif source=='none' and len(samples['none'])<5:
            samples['none'].append((client_id, None))

    print("\nSource classification counts:")
    for k,v in source_counts.items():
        print(f"  {k}: {v}")

    print("\nSample extracted names:")
    for k,vals in samples.items():
        if not vals: continue
        print(f"  {k}:")
        for cid,name in vals:
            print(f"    client_id={cid} -> {name}")

    # Estimate backfill impact
    backfillable = total_blank - source_counts['none']
    print(f"\nBackfillable rows (would gain a name): {backfillable}")
    print(f"Remaining rows with no alternative source: {source_counts['none']}")

    # Proposed UPDATE statement (not executed) for review
    update_parts = []
    if 'full_name' in candidate_cols:
        update_parts.append("COALESCE(NULLIF(full_name,''),")
    if 'first_name' in candidate_cols and 'last_name' in candidate_cols:
        update_parts.append("CASE WHEN NULLIF(first_name,'') IS NOT NULL AND NULLIF(last_name,'') IS NOT NULL THEN (first_name||' '||last_name) END,")
    if 'first_name' in candidate_cols:
        update_parts.append("NULLIF(first_name,''),")
    if 'contact_info' in candidate_cols:
        update_parts.append("CASE WHEN contact_info ~ '^[A-Za-z\\s]+$' THEN contact_info END,")
    # notes pattern can't be used directly in pure SQL easily; skip for automatic backfill
    coalesce_expr = 'COALESCE(' + ''.join(update_parts) + "client_id::text)"

    print("\nProposed backfill expression:")
    print(coalesce_expr)
    print("\nExample UPDATE (review before running):")
    print("UPDATE clients SET client_name = " + coalesce_expr + " WHERE (client_name IS NULL OR TRIM(client_name)='');")

    conn.close()

if __name__=='__main__':
    main()
