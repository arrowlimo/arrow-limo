import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

print("="*80)
print("ROLLING BACK TODAY'S DUPLICATE PAYMENTS")
print("="*80)

# Show what will be deleted
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM charter_payments
    WHERE imported_at::date = CURRENT_DATE
    AND client_name ILIKE '%Perron Ventures%'
""")

count, total = cur.fetchone()
print(f"\n⚠️  Found {count} payment records from today totaling ${total:,.2f}")

response = input("\nDelete these duplicate payments? (yes/no): ")

if response.lower() == 'yes':
    # Delete today's payments
    cur.execute("""
        DELETE FROM charter_payments
        WHERE imported_at::date = CURRENT_DATE
        AND client_name ILIKE '%Perron Ventures%'
    """)
    
    deleted = cur.rowcount
    conn.commit()
    
    print(f"\n✅ Deleted {deleted} duplicate payment records")
    print("   Database restored to pre-duplication state")
    
    # Show new status
    cur.execute("""
        SELECT 
            COUNT(*) as charters,
            SUM(c.total_amount_due) as total_due,
            COALESCE(SUM(cp_sum.paid), 0) as total_paid
        FROM charters c
        LEFT JOIN (
            SELECT charter_id::integer as cid, SUM(amount) as paid
            FROM charter_payments
            WHERE client_name ILIKE '%Perron Ventures%'
            GROUP BY charter_id
        ) cp_sum ON cp_sum.cid = c.charter_id
        WHERE c.client_display_name ILIKE '%Perron Ventures%'
        AND c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    """)
    
    result = cur.fetchone()   
    print(f"\n📊 CORRECTED STATUS:")
    print(f"   Charters: {result[0]}")
    print(f"   Total Due: ${result[1]:,.2f}")
    print(f"   Total Paid: ${result[2]:,.2f}")
    print(f"   Outstanding: ${result[1] - result[2]:,.2f}")
else:
    print("\n❌ Cancelled - no changes made")

conn.close()
