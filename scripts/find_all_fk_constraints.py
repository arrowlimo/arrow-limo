"""
Find all foreign key constraints that reference specific tables

This will help us discover ALL FKs before attempting deletions
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Tables we're trying to clean
target_tables = ['payments', 'banking_transactions']

for target_table in target_tables:
    print(f"\n{'='*80}")
    print(f"FOREIGN KEY CONSTRAINTS REFERENCING {target_table.upper()}")
    print('='*80)
    
    # Find all FKs that reference this table
    cur.execute("""
        SELECT 
            tc.table_name AS referencing_table,
            kcu.column_name AS referencing_column,
            ccu.table_name AS referenced_table,
            ccu.column_name AS referenced_column,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu 
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name = %s
        ORDER BY tc.table_name
    """, (target_table,))
    
    fks = cur.fetchall()
    
    if fks:
        print(f"\nFound {len(fks)} foreign key constraint(s):\n")
        for ref_table, ref_col, tgt_table, tgt_col, constraint_name in fks:
            print(f"  {ref_table}.{ref_col}")
            print(f"    -> {tgt_table}.{tgt_col}")
            print(f"    Constraint: {constraint_name}")
            print()
    else:
        print("\n✅ No foreign key constraints found")

conn.close()
