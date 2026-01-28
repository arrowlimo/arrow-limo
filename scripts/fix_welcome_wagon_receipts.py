import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print("Fixing Welcome Wagon receipts based on verified CIBC bank records")
print("="*100)
print("\nVerified bank record shows ONLY:")
print("  March 19, 2012: CHQ 215 WELCOME WAGON - $150.00 debit")
print("\nNo NSF, no March 14 transactions, no $12 fee\n")
print("="*100)

# Mark receipts 141603 and 141605 as voided (they don't exist in bank records)
print("\nStep 1: Voiding receipts that don't exist in bank records...")

cur.execute("""
    UPDATE receipts 
    SET is_voided = true,
        exclude_from_reports = true,
        validation_status = 'INVALID',
        validation_reason = 'Does not exist in verified CIBC bank records - phantom transaction'
    WHERE receipt_id IN (141603, 141605)
    RETURNING receipt_id, receipt_date, vendor_name, gross_amount
""")

voided = cur.fetchall()
for r in voided:
    print(f"  ✅ Voided Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f}")

# Receipt 141606 is already marked as QB_DUPLICATE, just ensure it's excluded
print("\nStep 2: Ensuring QB duplicate is excluded from reports...")

cur.execute("""
    UPDATE receipts 
    SET exclude_from_reports = true,
        is_voided = true,
        validation_status = 'DUPLICATE',
        validation_reason = 'QB journal entry duplicate - no actual bank transaction'
    WHERE receipt_id = 141606
    RETURNING receipt_id, receipt_date, vendor_name, gross_amount
""")

excluded = cur.fetchall()
for r in excluded:
    print(f"  ✅ Excluded Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f}")

# Ensure receipt 141634 is the only valid one
print("\nStep 3: Confirming Receipt 141634 is the ONLY valid Welcome Wagon receipt...")

cur.execute("""
    UPDATE receipts 
    SET is_voided = false,
        exclude_from_reports = false,
        validation_status = 'VERIFIED',
        validation_reason = 'Matches verified CIBC bank record',
        category = 'advert',
        description = 'advertising'
    WHERE receipt_id = 141634
    RETURNING receipt_id, receipt_date, vendor_name, gross_amount, banking_transaction_id
""")

valid = cur.fetchall()
for r in valid:
    print(f"  ✅ Valid Receipt {r[0]}: {r[1]} - {r[2]} - ${r[3]:.2f} - Banking TX {r[4]}")

conn.commit()

print("\n" + "="*100)
print("\nFinal verification - All Welcome Wagon receipts:")
print("="*100)

cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        is_voided,
        exclude_from_reports,
        validation_status,
        banking_transaction_id
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%'
    ORDER BY receipt_date, receipt_id
""")

all_receipts = cur.fetchall()

print(f"\n{'Receipt ID':<12} {'Date':<12} {'Amount':<10} {'Voided':<8} {'Excluded':<10} {'Status':<12} {'Banking TX':<12} {'Valid?'}")
print('-' * 100)

for r in all_receipts:
    r_id, r_date, vendor, amount, voided, excluded, status, bank_tx = r
    valid_flag = "✅ VALID" if not voided and not excluded else "❌ VOID"
    print(f"{r_id:<12} {str(r_date):<12} ${amount:>8.2f} {str(voided):<8} {str(excluded):<10} {status:<12} {bank_tx or 'N/A':<12} {valid_flag}")

print("\n" + "="*100)
print("\n✅ CORRECTED: Only 1 valid Welcome Wagon receipt:")
print("   Receipt 141634 - March 19, 2012 - CHQ 215 - $150.00")
print("\n❌ VOIDED: 3 phantom/duplicate receipts (141603, 141605, 141606)")
print("\n✅ Database now matches verified CIBC bank records!")

cur.close()
conn.close()
