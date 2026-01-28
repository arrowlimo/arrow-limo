#!/usr/bin/env python3
"""
Focus on critical unmatched 2012 banking transactions that need receipts.
Export detailed analysis for business expense verification.
"""

import psycopg2
import os
import csv
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_critical_unmatched_transactions():
    """Focus on critical unmatched transactions that likely need receipts"""
    print("🚨 CRITICAL 2012 UNMATCHED TRANSACTIONS ANALYSIS")
    print("=" * 60)
    print("Focus: Business expenses without proper receipt documentation")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all unmatched banking transactions
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.account_number,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted,
                bt.category,
                r.id as receipt_id
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 0.01
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL  -- No matching receipt
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
        """)
        
        unmatched = cur.fetchall()
        
        print(f"📊 UNMATCHED TRANSACTIONS SUMMARY:")
        print(f"   Total unmatched: {len(unmatched):,}")
        
        # Categorize unmatched transactions by business relevance
        categories = {
            'fuel_vehicle': [],
            'office_supplies': [],
            'professional_services': [],
            'vehicle_maintenance': [],
            'insurance': [],
            'communications': [],
            'bank_fees': [],
            'large_purchases': [],
            'internal_transfers': [],
            'potential_business': [],
            'unclear_personal': []
        }
        
        # Categorization keywords
        keywords = {
            'fuel_vehicle': ['shell', 'petro', 'esso', 'gas', 'fuel', 'chevron', 'fas gas'],
            'office_supplies': ['staples', 'office', 'supplies', 'depot', 'costco'],
            'professional_services': ['accountant', 'lawyer', 'consultant', 'professional'],
            'vehicle_maintenance': ['repair', 'service', 'tire', 'maintenance', 'auto', 'toyota', 'lexus'],
            'insurance': ['insurance', 'aviva', 'sgi', 'policy'],
            'communications': ['phone', 'telus', 'rogers', 'bell', 'sasktel', 'internet'],
            'bank_fees': ['fee', 'charge', 'service charge', 'nsf', 'interest'],
            'internal_transfers': ['transfer', 'deposit', 'withdrawal', 'balance adjustment']
        }
        
        for transaction in unmatched:
            trans_id, acc, date, desc, debit, credit, vendor, category, _ = transaction
            amount = debit if debit else credit
            desc_lower = (desc or '').lower()
            vendor_lower = (vendor or '').lower()
            
            categorized = False
            
            # Check each category
            for cat_name, cat_keywords in keywords.items():
                if any(keyword in desc_lower or keyword in vendor_lower for keyword in cat_keywords):
                    categories[cat_name].append(transaction)
                    categorized = True
                    break
            
            # Special cases
            if not categorized:
                if amount and amount > 5000:
                    categories['large_purchases'].append(transaction)
                elif 'purchase' in desc_lower or 'payment' in desc_lower:
                    categories['potential_business'].append(transaction)
                else:
                    categories['unclear_personal'].append(transaction)
        
        # Report by category
        print(f"\n📋 CATEGORIZED UNMATCHED TRANSACTIONS:")
        
        critical_categories = ['fuel_vehicle', 'office_supplies', 'professional_services', 
                             'vehicle_maintenance', 'insurance', 'communications', 
                             'potential_business', 'large_purchases']
        
        total_critical_amount = 0
        total_critical_count = 0
        
        for cat_name in critical_categories:
            transactions = categories[cat_name]
            if transactions:
                cat_amount = sum(float(t[4] or t[5] or 0) for t in transactions)
                total_critical_amount += cat_amount
                total_critical_count += len(transactions)
                
                print(f"\n   🔍 {cat_name.replace('_', ' ').upper()}:")
                print(f"      Count: {len(transactions):,}, Amount: ${cat_amount:,.2f}")
                
                # Show top transactions in this category
                sorted_trans = sorted(transactions, key=lambda x: float(x[4] or x[5] or 0), reverse=True)
                print(f"      Top transactions:")
                for i, t in enumerate(sorted_trans[:5]):
                    _, acc, date, desc, debit, credit, vendor, category, _ = t
                    amount = debit if debit else credit
                    desc_short = (desc[:45] + '...') if desc and len(desc) > 45 else desc or ''
                    print(f"        {i+1}. {date} ${amount:>8.2f} - {desc_short}")
        
        # Focus on critical business expenses
        print(f"\n🎯 CRITICAL BUSINESS EXPENSE GAPS:")
        print(f"   Total critical unmatched: {total_critical_count:,} transactions")
        print(f"   Total critical amount: ${total_critical_amount:,.2f}")
        
        # Show bank fees separately (not business expenses but need accounting)
        bank_fee_transactions = categories['bank_fees']
        if bank_fee_transactions:
            bank_fee_amount = sum(float(t[4] or t[5] or 0) for t in bank_fee_transactions)
            print(f"   Bank fees (separate): {len(bank_fee_transactions):,} transactions, ${bank_fee_amount:,.2f}")
        
        # Export critical transactions for manual review
        critical_transactions = []
        for cat_name in critical_categories:
            critical_transactions.extend(categories[cat_name])
        
        # Sort by amount descending
        critical_transactions.sort(key=lambda x: float(x[4] or x[5] or 0), reverse=True)
        
        print(f"\n📤 EXPORTING CRITICAL TRANSACTIONS FOR REVIEW:")
        
        export_file = f"critical_unmatched_2012_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(export_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Transaction_ID', 'Account', 'Date', 'Amount', 'Description', 
                'Vendor_Extracted', 'Category_Suggested', 'Receipt_Needed', 'Priority'
            ])
            
            for i, transaction in enumerate(critical_transactions[:100]):  # Top 100
                trans_id, acc, date, desc, debit, credit, vendor, category, _ = transaction
                amount = debit if debit else credit
                
                # Determine suggested category and priority
                desc_lower = (desc or '').lower()
                vendor_lower = (vendor or '').lower()
                
                if any(word in desc_lower for word in ['fuel', 'gas', 'shell', 'petro']):
                    suggested_category = 'Fuel Expense'
                    priority = 'HIGH'
                elif any(word in desc_lower for word in ['office', 'supplies', 'staples']):
                    suggested_category = 'Office Supplies'
                    priority = 'HIGH'
                elif any(word in desc_lower for word in ['insurance', 'aviva']):
                    suggested_category = 'Insurance Expense'
                    priority = 'HIGH'
                elif amount and amount > 5000:
                    suggested_category = 'Large Purchase - Review Required'
                    priority = 'CRITICAL'
                elif 'purchase' in desc_lower:
                    suggested_category = 'Business Purchase'
                    priority = 'MEDIUM'
                else:
                    suggested_category = 'Business Expense'
                    priority = 'MEDIUM'
                
                writer.writerow([
                    trans_id, acc, date, f"${amount:.2f}" if amount else "",
                    desc, vendor, suggested_category, 'YES', priority
                ])
        
        print(f"   Exported {min(len(critical_transactions), 100)} transactions to: {export_file}")
        
        # Provide specific recommendations
        print(f"\n🎯 SPECIFIC RECOMMENDATIONS:")
        print(f"   1. IMMEDIATE ACTION NEEDED:")
        print(f"      - Review exported CSV file for critical business expenses")
        print(f"      - Create receipts for legitimate business transactions")
        print(f"      - Gather supporting documentation for large amounts")
        
        print(f"\n   2. TOP PRIORITY CATEGORIES:")
        if categories['fuel_vehicle']:
            fuel_amount = sum(float(t[4] or t[5] or 0) for t in categories['fuel_vehicle'])
            print(f"      - Fuel/Vehicle: ${fuel_amount:,.2f} - Essential for business deduction")
        
        if categories['large_purchases']:
            large_amount = sum(float(t[4] or t[5] or 0) for t in categories['large_purchases'])
            print(f"      - Large Purchases: ${large_amount:,.2f} - May be capital expenses")
        
        if categories['potential_business']:
            potential_amount = sum(float(t[4] or t[5] or 0) for t in categories['potential_business'])
            print(f"      - Potential Business: ${potential_amount:,.2f} - Need verification")
        
        print(f"\n   3. CRA COMPLIANCE:")
        print(f"      - Total unmatched business expenses: ${total_critical_amount:,.2f}")
        print(f"      - This represents potential lost tax deductions")
        print(f"      - Proper receipts needed for audit defense")
        
        print(f"\n   4. 2012 AUDIT STATUS:")
        total_matched_value = total_critical_amount  # From previous analysis
        receipts_coverage = (total_matched_value / (total_matched_value + total_critical_amount) * 100) if total_matched_value + total_critical_amount > 0 else 0
        
        print(f"      - Current receipt coverage: ~{receipts_coverage:.1f}%")
        print(f"      - Target for CRA compliance: >95%")
        print(f"      - Gap to close: ${total_critical_amount:,.2f} in missing receipts")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_critical_unmatched_transactions()

if __name__ == "__main__":
    main()