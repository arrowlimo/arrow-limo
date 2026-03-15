"""
Final Cleanup: Convert all remaining NULL/TRANSFERS to Unknown
"""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("="*80)
print("FINAL CLEANUP: NULL/TRANSFERS → UNKNOWN")
print("="*80)

try:
    # Show before state
    cur.execute("""
        SELECT category, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category IN ('NULL', 'None', 'TRANSFERS', 'BANKING') OR category IS NULL
        GROUP BY category
    """)
    
    print("\nBEFORE:")
    for cat, count, amount in cur.fetchall():
        cat_name = cat or 'NULL (actual NULL)'
        print(f"  {cat_name}: {count:,} receipts (${amount:,.2f})")
    
    # Convert NULL (string) category
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'NULL'
    """)
    null_string = cur.rowcount
    print(f"\n1. 'NULL' string → Unknown: {null_string:,} receipts")
    
    # Convert actual NULL
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category IS NULL
    """)
    null_actual = cur.rowcount
    print(f"2. NULL (actual) → Unknown: {null_actual:,} receipts")
    
    # Convert None
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'None'
    """)
    none_val = cur.rowcount
    print(f"3. 'None' → Unknown: {none_val:,} receipts")
    
    # Convert TRANSFERS
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'TRANSFERS'
    """)
    transfers = cur.rowcount
    print(f"4. 'TRANSFERS' → Unknown: {transfers:,} receipts")
    
    # Convert BANKING
    cur.execute("""
        UPDATE receipts
        SET category = 'Unknown', updated_at = NOW()
        WHERE category = 'BANKING'
    """)
    banking = cur.rowcount
    print(f"5. 'BANKING' → Unknown: {banking:,} receipts")
    
    total_converted = null_string + null_actual + none_val + transfers + banking
    
    print(f"\n📊 TOTAL CONVERTED: {total_converted:,} receipts")
    
    # Final stats
    print("\n" + "="*80)
    print("FINAL CATEGORIZATION STATUS")
    print("="*80)
    
    cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts")
    total_recs, total_amt = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category = 'Unknown'
    """)
    unknown_recs, unknown_amt = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE category != 'Unknown' AND category IS NOT NULL
    """)
    categorized_recs, categorized_amt = cur.fetchone()
    
    print(f"\nTotal receipts: {total_recs:,} (${total_amt:,.2f})")
    print(f"\n✅ Fully categorized: {categorized_recs:,} ({categorized_recs/total_recs*100:.1f}%)")
    print(f"   Amount: ${categorized_amt:,.2f} ({categorized_amt/total_amt*100:.1f}% of total)")
    print(f"\n⚠️  Unknown category: {unknown_recs:,} ({unknown_recs/total_recs*100:.1f}%)")
    print(f"   Amount: ${unknown_amt:,.2f} ({unknown_amt/total_amt*100:.1f}% of total)")
    
    # Top categories
    print("\n" + "="*80)
    print("TOP 15 CATEGORIES")
    print("="*80)
    
    cur.execute("""
        SELECT category, COUNT(*), SUM(gross_amount)
        FROM receipts
        GROUP BY category
        ORDER BY COUNT(*) DESC
        LIMIT 15
    """)
    
    print(f"\n{'Category':<40} {'Count':>6}  {'Amount':>14}")
    print("-" * 64)
    
    for cat, count, amount in cur.fetchall():
        marker = "⚠️" if cat == 'Unknown' else "✅"
        amt_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{marker} {cat:<37} {count:>6,}  {amt_str:>14}")
    
    response = input("\n✋ COMMIT these changes? (yes/no): ").strip().lower()
    
    if response == 'yes':
        conn.commit()
        print("\n✅ Changes COMMITTED")
        print("\n" + "="*80)
        print("CATEGORIZATION CLEANUP COMPLETE!")
        print("="*80)
        print(f"\n✅ {categorized_recs:,} receipts ({categorized_recs/total_recs*100:.1f}%) fully categorized")
        print(f"⚠️  {unknown_recs:,} receipts ({unknown_recs/total_recs*100:.1f}%) marked as Unknown (require manual review)")
    else:
        conn.rollback()
        print("\n❌ Changes ROLLED BACK")
        
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    raise
    
finally:
    cur.close()
    conn.close()
