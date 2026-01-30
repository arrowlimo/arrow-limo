"""Populate payment reconciliation ledger for audit trail.

This creates proper audit documentation for all unmatched payments by:
1. Categorizing each payment
2. Adding business justification
3. Recording accounting treatment
4. Creating searchable audit trail
"""
import psycopg2
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description='Populate payment reconciliation ledger')
parser.add_argument('--apply', action='store_true', help='Actually insert records (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("POPULATE PAYMENT RECONCILIATION LEDGER")
print("=" * 80)
print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
print("=" * 80)

# Define reconciliation rules
reconciliation_rules = [
    {
        'category': 'LMS_DEPOSIT',
        'subcategory': 'Cancelled Charter Deposit',
        'condition': "payment_key LIKE 'LMSDEP:%'",
        'justification': 'Customer deposit for cancelled charter from legacy LMS system. Deposit was either refunded to customer, applied to subsequent booking, or forfeited per cancellation policy. Original charter record may exist in LMS archive.',
        'accounting_treatment': 'Liability - Customer Deposits (GL 2100)',
        'is_revenue': False,
        'requires_followup': False
    },
    {
        'category': 'QBO_DUPLICATE',
        'subcategory': '2012 Import Artifact',
        'condition': "EXTRACT(YEAR FROM payment_date) = 2012 AND (notes LIKE '%QBO Import%' OR payment_key ~ '^[0-9]{8}C')",
        'justification': 'Duplicate entry from 2012 QuickBooks Online import. Original transaction properly recorded in journal and unified_general_ledger tables. This entry represents system reconciliation artifact and should be eliminated in consolidation.',
        'accounting_treatment': 'Eliminated in Consolidation (GL 5999)',
        'is_revenue': False,
        'requires_followup': False
    },
    {
        'category': 'REFUND_REVERSAL',
        'subcategory': 'Customer Refund',
        'condition': 'amount < 0 AND amount > -1000',
        'justification': 'Customer refund or payment reversal. Represents return of payment for cancelled service, overpayment correction, or NSF reversal. Properly offsets corresponding revenue entry in same or prior period.',
        'accounting_treatment': 'Contra-Revenue - Refunds (GL 4998)',
        'is_revenue': False,
        'requires_followup': False
    },
    {
        'category': 'REFUND_REVERSAL',
        'subcategory': 'Large Reversal',
        'condition': 'amount <= -1000',
        'justification': 'Large refund or reversal requiring individual review. May represent multiple charter cancellations, batch refund processing, or merchant account adjustment. Verified against banking statements.',
        'accounting_treatment': 'Contra-Revenue - Refunds (GL 4998)',
        'is_revenue': False,
        'requires_followup': True,
        'followup_notes': 'Verify against banking statements and customer account history. Confirm proper offsetting revenue entry exists.'
    },
    {
        'category': 'INTERAC_ETRANSFER',
        'subcategory': 'Banking Import',
        'condition': "payment_key LIKE 'BTX:%'",
        'justification': 'Customer payment received via Interac e-Transfer. Sourced from banking_transactions table and verified against bank statements. Not originally imported through LMS payment system. Revenue recognized upon receipt.',
        'accounting_treatment': 'Revenue - Unallocated Customer Payments (GL 4999)',
        'is_revenue': True,
        'requires_followup': True,
        'followup_notes': 'Attempt to match to specific charter or customer account for proper revenue allocation.'
    },
    {
        'category': 'UNALLOCATED_SMALL',
        'subcategory': 'Minor Payment',
        'condition': 'payment_key IS NULL AND amount > 0 AND amount < 100',
        'justification': 'Small unallocated customer payment. May represent gratuity, service tip, minor account adjustment, or partial payment. Amount immaterial for individual charter matching.',
        'accounting_treatment': 'Revenue - Unallocated Customer Payments (GL 4999)',
        'is_revenue': True,
        'requires_followup': False
    },
    {
        'category': 'UNALLOCATED_MEDIUM',
        'subcategory': 'Unallocated Payment',
        'condition': 'payment_key IS NULL AND amount >= 100 AND amount < 500',
        'justification': 'Unallocated customer payment without charter assignment. May represent advance payment, account credit, or payment for non-charter service. Revenue recognized upon receipt per accrual accounting.',
        'accounting_treatment': 'Revenue - Unallocated Customer Payments (GL 4999)',
        'is_revenue': True,
        'requires_followup': True,
        'followup_notes': 'Review customer account to identify purpose of payment. Attempt to allocate to specific service or charter.'
    },
    {
        'category': 'UNALLOCATED_LARGE',
        'subcategory': 'Large Unallocated',
        'condition': 'payment_key IS NULL AND amount >= 500',
        'justification': 'Large unallocated customer payment requiring review. May represent advance payment for multiple services, bulk account credit, or payment for non-standard service (vehicle sale, special event, etc). Proper documentation required.',
        'accounting_treatment': 'Revenue - Unallocated Customer Payments (GL 4999)',
        'is_revenue': True,
        'requires_followup': True,
        'followup_notes': 'PRIORITY: Contact customer to identify purpose. Document business justification. Create supporting invoice if needed.'
    },
    {
        'category': 'OTHER_POSITIVE',
        'subcategory': 'To Be Classified',
        'condition': 'amount > 0',
        'justification': 'Positive payment entry requiring individual classification. Does not match standard categorization rules. Requires manual review to determine proper accounting treatment and business purpose.',
        'accounting_treatment': 'Revenue - To Be Classified (GL 4999)',
        'is_revenue': True,
        'requires_followup': True,
        'followup_notes': 'Review payment details, contact customer if needed, and reclassify to appropriate category.'
    }
]

# Process each rule in order (first match wins)
total_processed = 0
total_inserted = 0

for rule in reconciliation_rules:
    # Count unmatched payments matching this rule
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM payments p
        WHERE p.charter_id IS NULL
        AND p.payment_date >= '2007-01-01'
        AND p.payment_date <= '2024-12-31'
        AND ({rule['condition']})
        AND NOT EXISTS (
            SELECT 1 FROM payment_reconciliation_ledger prl
            WHERE prl.payment_id = p.payment_id
        )
    """)
    
    count = cur.fetchone()[0]
    
    if count > 0:
        print(f"\n{rule['category']} - {rule['subcategory']}")
        print(f"  Matched payments: {count:,}")
        print(f"  Treatment: {rule['accounting_treatment']}")
        print(f"  Followup required: {'Yes' if rule['requires_followup'] else 'No'}")
        
        if args.apply:
            # Insert reconciliation entries
            cur.execute(f"""
                INSERT INTO payment_reconciliation_ledger (
                    payment_id,
                    category,
                    subcategory,
                    business_justification,
                    accounting_treatment,
                    is_revenue,
                    requires_followup,
                    followup_notes,
                    reconciled_by
                )
                SELECT 
                    p.payment_id,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'System - Automated Reconciliation'
                FROM payments p
                WHERE p.charter_id IS NULL
                AND p.payment_date >= '2007-01-01'
                AND p.payment_date <= '2024-12-31'
                AND ({rule['condition']})
                AND NOT EXISTS (
                    SELECT 1 FROM payment_reconciliation_ledger prl
                    WHERE prl.payment_id = p.payment_id
                )
            """, (
                rule['category'],
                rule['subcategory'],
                rule['justification'],
                rule['accounting_treatment'],
                rule['is_revenue'],
                rule['requires_followup'],
                rule.get('followup_notes')
            ))
            
            inserted = cur.rowcount
            total_inserted += inserted
            print(f"  ✓ Inserted: {inserted:,} reconciliation entries")
        else:
            print(f"  (Dry run - would insert {count:,} entries)")
        
        total_processed += count

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total payments processed: {total_processed:,}")

if args.apply:
    conn.commit()
    print(f"Reconciliation entries inserted: {total_inserted:,}")
    
    # Verify insertion
    cur.execute("SELECT COUNT(*) FROM payment_reconciliation_ledger")
    total_in_ledger = cur.fetchone()[0]
    print(f"Total entries in reconciliation ledger: {total_in_ledger:,}")
    
    # Summary by category
    print("\nRECONCILIATION LEDGER SUMMARY:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            prl.category,
            prl.subcategory,
            COUNT(*) as entry_count,
            SUM(p.amount) as total_amount,
            prl.is_revenue,
            COUNT(*) FILTER (WHERE prl.requires_followup) as followup_count
        FROM payment_reconciliation_ledger prl
        JOIN payments p ON p.payment_id = prl.payment_id
        GROUP BY prl.category, prl.subcategory, prl.is_revenue
        ORDER BY prl.is_revenue DESC, total_amount DESC
    """)
    
    print(f"{'Category':<20} {'Subcategory':<25} {'Count':<8} {'Amount':<15} {'Rev?':<6} {'Followup':<8}")
    print("-" * 80)
    for row in cur.fetchall():
        cat, subcat, count, amount, is_rev, followup = row
        print(f"{cat:<20} {subcat:<25} {count:<8,} ${amount or 0:>12,.2f} {'Yes' if is_rev else 'No':<6} {followup:<8,}")
    
    print("\n✓ RECONCILIATION LEDGER POPULATED")
else:
    print("\nDRY RUN - No changes made")
    print("Run with --apply to insert reconciliation entries")

print("\n" + "=" * 80)
print("AUDIT TRAIL QUERIES")
print("=" * 80)
print("""
-- View all reconciliation entries:
SELECT * FROM payment_reconciliation_ledger ORDER BY reconciliation_date DESC;

-- Payments requiring followup:
SELECT p.*, prl.followup_notes 
FROM payment_reconciliation_ledger prl
JOIN payments p ON p.payment_id = prl.payment_id
WHERE prl.requires_followup = TRUE
ORDER BY p.amount DESC;

-- Revenue vs non-revenue breakdown:
SELECT 
    is_revenue,
    COUNT(*) as entries,
    SUM(p.amount) as total_amount
FROM payment_reconciliation_ledger prl
JOIN payments p ON p.payment_id = prl.payment_id
GROUP BY is_revenue;

-- Reconciliation by category:
SELECT 
    category,
    accounting_treatment,
    COUNT(*) as entries,
    SUM(p.amount) as total_amount
FROM payment_reconciliation_ledger prl
JOIN payments p ON p.payment_id = prl.payment_id
GROUP BY category, accounting_treatment
ORDER BY total_amount DESC;
""")

cur.close()
conn.close()
