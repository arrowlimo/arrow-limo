import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

# Update verification
cur.execute("""
    UPDATE receipts
    SET is_verified_banking = TRUE,
        verified_source = 'Banking Transaction Match',
        verified_at = CURRENT_TIMESTAMP
    WHERE banking_transaction_id IS NOT NULL
    AND (is_verified_banking IS NULL OR is_verified_banking = FALSE)
""")

updated_count = cur.rowcount
conn.commit()

# Get totals
cur.execute("SELECT COUNT(*) FROM receipts WHERE is_verified_banking = TRUE")
total_verified = cur.fetchone()[0]

cur.execute("SELECT SUM(gross_amount) FROM receipts WHERE is_verified_banking = TRUE")
total_amount = cur.fetchone()[0] or 0

conn.close()

# Write to file
with open('l:\\limo\\verification_results.txt', 'w') as f:
    f.write(f"Bank-Matched Receipts Verified\n")
    f.write(f"="*50 + "\n")
    f.write(f"Newly verified: {updated_count:,}\n")
    f.write(f"Total verified: {total_verified:,}\n")
    f.write(f"Total amount: ${total_amount:,.2f}\n")

print("Results written to l:\\limo\\verification_results.txt")
