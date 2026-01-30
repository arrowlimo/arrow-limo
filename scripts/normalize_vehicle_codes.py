"""
Normalize vehicle codes to standard L-# or L-## format:
- Limo01 → L-1
- Limo08 → L-8
- Limo11 → L-11
- L3 → L-3
- L05 → L-5
- limo02 → L-2 (fix capitalization)

Pattern: L-# for single digit, L-## for double digit (no zero-padding)
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

def normalize_vehicle_code(code):
    """
    Normalize vehicle code to L-# or L-## format.
    
    Examples:
        Limo01 → L-1
        Limo08 → L-8
        Limo11 → L-11
        L3 → L-3
        L05 → L-5
        limo02 → L-2
    """
    if not code:
        return code
    
    code = code.strip()
    if not code:
        return code
    
    # Handle "Limo##" or "limo##" format
    if code.lower().startswith('limo'):
        num_str = code[4:]  # Everything after "Limo"
        if num_str.isdigit():
            num = int(num_str)
            return f"L-{num}"
    
    # Handle "L##" or "L#" without dash
    if code.upper().startswith('L') and not '-' in code:
        num_str = code[1:]  # Everything after "L"
        if num_str.isdigit():
            num = int(num_str)
            return f"L-{num}"
    
    # Handle "L-##" or "L-#" - check for zero-padding
    if code.upper().startswith('L-'):
        num_str = code[2:]  # Everything after "L-"
        if num_str.isdigit():
            num = int(num_str)
            return f"L-{num}"
    
    # No normalization needed
    return code

def process_table(cur, table, column, id_column):
    """Extract vehicle codes that need normalization."""
    print(f"\n{'='*80}")
    print(f"Processing {table}.{column}...")
    print('='*80)
    
    cur.execute(f"""
        SELECT {id_column}, {column}
        FROM {table}
        WHERE {column} IS NOT NULL AND {column} != ''
        ORDER BY {column};
    """)
    
    rows = cur.fetchall()
    updates = {}  # {id: (old_code, new_code)}
    
    for row in rows:
        row_id, code = row
        normalized = normalize_vehicle_code(code)
        if normalized != code:
            updates[row_id] = (code, normalized)
    
    print(f"Found {len(updates):,} codes to normalize out of {len(rows):,} total")
    
    if updates:
        print("\nSample normalizations:")
        for i, (row_id, (old, new)) in enumerate(list(updates.items())[:10]):
            print(f"  {old} → {new}")
        if len(updates) > 10:
            print(f"  ... and {len(updates) - 10:,} more")
    
    return updates

def apply_updates(cur, table, column, id_column, updates, dry_run=True):
    """Apply normalization updates."""
    if not updates:
        print("No updates needed")
        return
    
    if dry_run:
        print(f"\n{'='*80}")
        print("DRY RUN - No changes will be committed")
        print('='*80)
        return
    
    print(f"\n{'='*80}")
    print(f"Applying {len(updates):,} updates to {table}.{column}...")
    print('='*80)
    
    for row_id, (old_code, new_code) in updates.items():
        cur.execute(f"""
            UPDATE {table}
            SET {column} = %s
            WHERE {id_column} = %s;
        """, (new_code, row_id))
    
    print(f"✅ Updated {len(updates):,} records")

def fetch_distinct_codes(cur, table, column):
    """Fetch all distinct codes after normalization."""
    cur.execute(f"""
        SELECT DISTINCT {column}
        FROM {table}
        WHERE {column} IS NOT NULL AND {column} != ''
        ORDER BY {column};
    """)
    return [row[0] for row in cur.fetchall()]

def sort_codes(codes):
    """Sort vehicle codes numerically (L-1, L-2, ... L-10, L-11, not L-1, L-10, L-11, L-2)."""
    def key_func(code):
        if not code:
            return ('', 0, '')
        
        # Handle L-# or L-## format
        if code.upper().startswith('L-'):
            num_str = code[2:]
            if num_str.isdigit():
                return ('L', int(num_str), code)
        
        # Handle L# without dash
        if code.upper().startswith('L') and len(code) > 1:
            num_str = code[1:]
            if num_str.isdigit():
                return ('L', int(num_str), code)
        
        # Other codes sort alphabetically
        return (code, 0, code)
    
    return sorted(codes, key=key_func)

def print_codes(title, codes):
    """Print sorted vehicle codes."""
    sorted_codes = sort_codes(codes)
    print(f"\n{title}: {len(sorted_codes)} unique codes")
    print('-'*80)
    
    # Group by prefix for cleaner display
    grouped = defaultdict(list)
    for code in sorted_codes:
        if code.upper().startswith('L'):
            grouped['L'].append(code)
        else:
            grouped['OTHER'].append(code)
    
    for prefix in ['L', 'OTHER']:
        if prefix in grouped:
            codes_list = grouped[prefix]
            print(f"\n{prefix} ({len(codes_list)} total):")
            # Print in rows of 10
            for i in range(0, len(codes_list), 10):
                row = codes_list[i:i+10]
                print(f"  {', '.join(row)}")

def main():
    dry_run = '--write' not in sys.argv
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # Process charters table
        charters_updates = process_table(cur, 'charters', 'vehicle', 'charter_id')
        apply_updates(cur, 'charters', 'vehicle', 'charter_id', charters_updates, dry_run)
        
        if not dry_run:
            conn.commit()
            print(f"\n{'='*80}")
            print(f"✅ COMMITTED: {len(charters_updates):,} vehicle codes normalized")
            print('='*80)
            
            # Show final state
            print("\n" + "="*80)
            print("FINAL STATE:")
            print("="*80)
            
            charters_codes = fetch_distinct_codes(cur, 'charters', 'vehicle')
            print_codes("Charters vehicle codes", charters_codes)
        else:
            print(f"\n{'='*80}")
            print(f"DRY RUN COMPLETE - Use --write to apply changes")
            print(f"Would update: {len(charters_updates):,} vehicle codes")
            print('='*80)
    
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
