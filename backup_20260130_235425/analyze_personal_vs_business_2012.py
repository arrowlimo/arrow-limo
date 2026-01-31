#!/usr/bin/env python3
"""
Analyze 2012 unmatched transactions to identify personal vs business purchases.
Focus on separating legitimate business expenses from personal transactions.
"""

import psycopg2
import os
import re
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def analyze_personal_vs_business():
    """Analyze transactions to separate personal from business expenses"""
    print("🔍 PERSONAL VS BUSINESS TRANSACTION ANALYSIS - 2012")
    print("=" * 60)
    print("Identifying likely personal purchases that should NOT be receipted")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all unmatched transactions
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.account_number,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.credit_amount,
                bt.vendor_extracted,
                bt.category
            FROM banking_transactions bt
            LEFT JOIN receipts r ON (
                r.receipt_date = bt.transaction_date
                AND ABS(COALESCE(r.gross_amount, 0) - COALESCE(bt.debit_amount, bt.credit_amount, 0)) < 0.01
            )
            WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
              AND bt.account_number IN ('0228362', '903990106011', '3648117')
              AND r.id IS NULL  -- No matching receipt
              AND COALESCE(bt.debit_amount, bt.credit_amount, 0) > 0
            ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
        """)
        
        transactions = cur.fetchall()
        
        print(f"📊 Analyzing {len(transactions):,} unmatched transactions")
        
        # Define classification patterns
        personal_patterns = {
            'grocery_food': {
                'keywords': ['grocery', 'superstore', 'safeway', 'sobeys', 'iga', 'food', 'restaurant', 'tim hortons', 'mcdonalds', 'subway', 'pizza'],
                'confidence': 'HIGH'
            },
            'personal_shopping': {
                'keywords': ['walmart', 'target', 'canadian tire personal', 'clothing', 'shoes', 'pharmacy', 'drug store'],
                'confidence': 'HIGH'  
            },
            'personal_services': {
                'keywords': ['haircut', 'salon', 'spa', 'personal care', 'dental', 'medical', 'doctor'],
                'confidence': 'HIGH'
            },
            'entertainment': {
                'keywords': ['movie', 'theatre', 'entertainment', 'bar', 'pub', 'liquor', 'casino', 'gaming'],
                'confidence': 'HIGH'
            },
            'personal_banking': {
                'keywords': ['cash withdrawal', 'atm', 'e-transfer personal', 'personal loan'],
                'confidence': 'MEDIUM'
            }
        }
        
        business_patterns = {
            'fuel_vehicle': {
                'keywords': ['shell', 'petro', 'esso', 'chevron', 'fas gas', 'fuel', 'gas station'],
                'confidence': 'HIGH'
            },
            'vehicle_business': {
                'keywords': ['service', 'repair', 'maintenance', 'tire', 'auto parts', 'toyota', 'lexus', 'dealership'],
                'confidence': 'HIGH'
            },
            'office_business': {
                'keywords': ['staples', 'office supplies', 'business depot', 'printer', 'computer', 'software'],
                'confidence': 'HIGH'
            },
            'professional_services': {
                'keywords': ['accountant', 'lawyer', 'consultant', 'professional', 'business services'],
                'confidence': 'HIGH'
            },
            'communications': {
                'keywords': ['phone', 'telus', 'rogers', 'bell', 'sasktel', 'internet', 'wireless'],
                'confidence': 'HIGH'
            },
            'insurance_business': {
                'keywords': ['insurance commercial', 'liability', 'fleet insurance', 'aviva business'],
                'confidence': 'HIGH'
            },
            'utilities_business': {
                'keywords': ['electricity', 'gas utility', 'water', 'utilities business'],
                'confidence': 'MEDIUM'
            }
        }
        
        ambiguous_patterns = {
            'could_be_either': {
                'keywords': ['canadian tire', 'costco', 'home depot', 'purchase', 'payment', 'misc'],
                'confidence': 'LOW'
            }
        }
        
        # Classify transactions
        classifications = {
            'likely_personal': [],
            'likely_business': [],
            'ambiguous': [],
            'bank_fees': [],
            'large_unknown': []
        }
        
        for transaction in transactions:
            trans_id, acc, date, desc, debit, credit, vendor, category = transaction
            amount = float(debit if debit else credit or 0)
            
            desc_lower = (desc or '').lower()
            vendor_lower = (vendor or '').lower()
            combined_text = f"{desc_lower} {vendor_lower}"
            
            classified = False
            
            # Check for bank fees first
            if any(word in combined_text for word in ['fee', 'charge', 'service charge', 'nsf', 'overdraft', 'interest']):
                classifications['bank_fees'].append({
                    'transaction': transaction,
                    'reason': 'Bank fee or charge',
                    'amount': amount
                })
                classified = True
            
            # Check personal patterns
            elif not classified:
                for pattern_name, pattern_info in personal_patterns.items():
                    if any(keyword in combined_text for keyword in pattern_info['keywords']):
                        classifications['likely_personal'].append({
                            'transaction': transaction,
                            'reason': f"Personal - {pattern_name.replace('_', ' ')}",
                            'confidence': pattern_info['confidence'],
                            'amount': amount
                        })
                        classified = True
                        break
            
            # Check business patterns
            elif not classified:
                for pattern_name, pattern_info in business_patterns.items():
                    if any(keyword in combined_text for keyword in pattern_info['keywords']):
                        classifications['likely_business'].append({
                            'transaction': transaction,
                            'reason': f"Business - {pattern_name.replace('_', ' ')}",
                            'confidence': pattern_info['confidence'],
                            'amount': amount
                        })
                        classified = True
                        break
            
            # Check ambiguous patterns
            elif not classified:
                for pattern_name, pattern_info in ambiguous_patterns.items():
                    if any(keyword in combined_text for keyword in pattern_info['keywords']):
                        classifications['ambiguous'].append({
                            'transaction': transaction,
                            'reason': f"Ambiguous - {pattern_name.replace('_', ' ')}",
                            'confidence': pattern_info['confidence'],
                            'amount': amount
                        })
                        classified = True
                        break
            
            # Large unknown transactions need manual review
            if not classified:
                if amount > 5000:
                    classifications['large_unknown'].append({
                        'transaction': transaction,
                        'reason': 'Large amount - requires manual review',
                        'confidence': 'UNKNOWN',
                        'amount': amount
                    })
                else:
                    classifications['ambiguous'].append({
                        'transaction': transaction,
                        'reason': 'Unknown - needs review',
                        'confidence': 'LOW',
                        'amount': amount
                    })
        
        # Report classification results
        print(f"\n📋 CLASSIFICATION RESULTS:")
        
        total_amount = sum(float(t[4] or t[5] or 0) for t in transactions)
        
        for class_name, items in classifications.items():
            if items:
                count = len(items)
                amount = sum(item['amount'] for item in items)
                percentage = (amount / total_amount * 100) if total_amount > 0 else 0
                
                print(f"\n   📊 {class_name.upper().replace('_', ' ')}:")
                print(f"      Count: {count:,} transactions")
                print(f"      Amount: ${amount:,.2f} ({percentage:.1f}%)")
                
                # Show examples
                print(f"      Examples:")
                sorted_items = sorted(items, key=lambda x: x['amount'], reverse=True)
                for i, item in enumerate(sorted_items[:5]):
                    trans = item['transaction']
                    desc = trans[3][:50] + '...' if trans[3] and len(trans[3]) > 50 else trans[3] or ''
                    print(f"        {i+1}. ${item['amount']:>8.2f} - {desc}")
                    print(f"           Reason: {item['reason']}")
        
        # Focus on likely personal transactions
        personal_items = classifications['likely_personal']
        if personal_items:
            print(f"\n🚨 LIKELY PERSONAL TRANSACTIONS (SHOULD NOT BE RECEIPTED):")
            print(f"   Total personal: {len(personal_items):,} transactions")
            personal_amount = sum(item['amount'] for item in personal_items)
            print(f"   Total amount: ${personal_amount:,.2f}")
            
            # Group by category
            personal_by_category = {}
            for item in personal_items:
                reason = item['reason']
                if reason not in personal_by_category:
                    personal_by_category[reason] = {'count': 0, 'amount': 0}
                personal_by_category[reason]['count'] += 1
                personal_by_category[reason]['amount'] += item['amount']
            
            print(f"\n   Personal categories:")
            for category, summary in sorted(personal_by_category.items()):
                print(f"      {category}: {summary['count']:,} transactions, ${summary['amount']:,.2f}")
        
        # Focus on business transactions that should be receipted
        business_items = classifications['likely_business']
        if business_items:
            print(f"\n[OK] LEGITIMATE BUSINESS EXPENSES (SHOULD BE RECEIPTED):")
            print(f"   Total business: {len(business_items):,} transactions")
            business_amount = sum(item['amount'] for item in business_items)
            print(f"   Total amount: ${business_amount:,.2f}")
            
            # Group by category
            business_by_category = {}
            for item in business_items:
                reason = item['reason']
                if reason not in business_by_category:
                    business_by_category[reason] = {'count': 0, 'amount': 0}
                business_by_category[reason]['count'] += 1
                business_by_category[reason]['amount'] += item['amount']
            
            print(f"\n   Business categories:")
            for category, summary in sorted(business_by_category.items()):
                print(f"      {category}: {summary['count']:,} transactions, ${summary['amount']:,.2f}")
        
        # Ambiguous transactions need manual review
        ambiguous_items = classifications['ambiguous']
        large_unknown_items = classifications['large_unknown']
        
        if ambiguous_items or large_unknown_items:
            print(f"\n[WARN]  REQUIRES MANUAL REVIEW:")
            if ambiguous_items:
                ambig_amount = sum(item['amount'] for item in ambiguous_items)
                print(f"   Ambiguous: {len(ambiguous_items):,} transactions, ${ambig_amount:,.2f}")
            
            if large_unknown_items:
                large_amount = sum(item['amount'] for item in large_unknown_items)
                print(f"   Large unknown: {len(large_unknown_items):,} transactions, ${large_amount:,.2f}")
                
                print(f"\n   Large transactions requiring review:")
                for item in sorted(large_unknown_items, key=lambda x: x['amount'], reverse=True)[:10]:
                    trans = item['transaction']
                    desc = trans[3][:60] if trans[3] else 'No description'
                    print(f"      ${item['amount']:>10.2f} - {desc}")
        
        # Summary and recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        
        if personal_items:
            personal_total = sum(item['amount'] for item in personal_items)
            print(f"   1. EXCLUDE FROM RECEIPTS: ${personal_total:,.2f} in personal transactions")
            print(f"      - These should NOT be created as business receipts")
            print(f"      - Keep separate for personal tax purposes only")
        
        if business_items:
            business_total = sum(item['amount'] for item in business_items)
            print(f"   2. CREATE BUSINESS RECEIPTS: ${business_total:,.2f} in legitimate expenses")
            print(f"      - These are valid business deductions")
            print(f"      - Should be receipted for CRA compliance")
        
        ambiguous_total = sum(item['amount'] for item in (ambiguous_items + large_unknown_items))
        if ambiguous_total > 0:
            print(f"   3. MANUAL REVIEW NEEDED: ${ambiguous_total:,.2f} in unclear transactions")
            print(f"      - Review each transaction individually")
            print(f"      - Determine business vs personal nature")
        
        # Calculate revised business expense opportunity
        if business_items:
            business_total = sum(item['amount'] for item in business_items)
            potential_gst = business_total * 0.05 / 1.05  # GST included calculation
            print(f"\n💰 TAX IMPACT ANALYSIS:")
            print(f"   Legitimate business expenses: ${business_total:,.2f}")
            print(f"   Potential GST credit: ${potential_gst:,.2f}")
            print(f"   Business tax deduction opportunity: ${business_total - potential_gst:,.2f}")
        
        print(f"\n📊 FINAL CLASSIFICATION SUMMARY:")
        business_count = len(business_items) if business_items else 0
        personal_count = len(personal_items) if personal_items else 0
        review_count = len(ambiguous_items) + len(large_unknown_items)
        
        print(f"   Business expenses: {business_count:,} transactions")
        print(f"   Personal expenses: {personal_count:,} transactions") 
        print(f"   Needs review: {review_count:,} transactions")
        print(f"   Bank fees: {len(classifications['bank_fees']):,} transactions")
        
        classification_accuracy = ((business_count + personal_count) / len(transactions) * 100) if transactions else 0
        print(f"   Classification confidence: {classification_accuracy:.1f}%")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    analyze_personal_vs_business()

if __name__ == "__main__":
    main()