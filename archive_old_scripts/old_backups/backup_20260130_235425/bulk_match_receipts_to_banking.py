#!/usr/bin/env python
"""
Bulk Receipt-to-Banking Matching Engine
Matches receipts to banking transactions after all data is imported

Matching Rules:
1. Exact amount + vendor name match + date within ±30 days
2. Partial payments: Multiple receipts to one banking transaction
3. Split payments: One receipt to multiple banking transactions
4. Manual review for ambiguous matches
"""

import psycopg2
from datetime import datetime, timedelta
from decimal import Decimal
import json

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

class ReceiptBankingMatcher:
    """Smart matching engine for receipts and banking transactions"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, 
            user=DB_USER, password=DB_PASSWORD
        )
        self.matches = []
        self.unmatched_receipts = []
        self.unmatched_banking = []
        
    def run_matching(self):
        """Execute the matching process"""
        print("=" * 80)
        print("RECEIPT-TO-BANKING BULK MATCHING ENGINE")
        print("=" * 80)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE - WILL UPDATE DATABASE'}")
        print()
        
        # Step 1: Find unmatched receipts
        print("Step 1: Finding unmatched receipts...")
        self.find_unmatched_receipts()
        
        # Step 2: Find unmatched banking transactions
        print("Step 2: Finding unmatched banking transactions...")
        self.find_unmatched_banking()
        
        # Step 3: Attempt automatic matching
        print("\nStep 3: Attempting automatic matches...")
        self.auto_match()
        
        # Step 4: Report results
        print("\nStep 4: Generating match report...")
        self.generate_report()
        
        # Step 5: Apply matches (if not dry run)
        if not self.dry_run and self.matches:
            self.apply_matches()
            
    def find_unmatched_receipts(self):
        """Find receipts not linked to banking"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                receipt_id, receipt_date, vendor_name, gross_amount,
                description, source_reference, category
            FROM receipts
            WHERE banking_transaction_id IS NULL
                AND gross_amount > 0
                AND EXTRACT(YEAR FROM receipt_date) <= 2025
            ORDER BY receipt_date
        """)
        self.unmatched_receipts = cur.fetchall()
        cur.close()
        print(f"  Found {len(self.unmatched_receipts)} unmatched receipts")
        
    def find_unmatched_banking(self):
        """Find banking transactions not fully matched to receipts"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.vendor_extracted,
                COALESCE(SUM(r.gross_amount), 0) as allocated_amount
            FROM banking_transactions bt
            LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
            WHERE bt.debit_amount > 0
                AND EXTRACT(YEAR FROM bt.transaction_date) <= 2025
            GROUP BY bt.transaction_id, bt.transaction_date, bt.description, 
                     bt.debit_amount, bt.vendor_extracted
            HAVING bt.debit_amount > COALESCE(SUM(r.gross_amount), 0) + 0.01
            ORDER BY bt.transaction_date
        """)
        self.unmatched_banking = cur.fetchall()
        cur.close()
        print(f"  Found {len(self.unmatched_banking)} unmatched banking transactions")
        
    def auto_match(self):
        """Attempt automatic matching with confidence scoring"""
        self.matches = []
        
        for receipt in self.unmatched_receipts:
            receipt_id, receipt_date, vendor, amount, desc, ref, category = receipt
            
            # Find candidate banking transactions
            candidates = self.find_banking_candidates(receipt_date, vendor, amount)
            
            for candidate in candidates:
                bt_id, bt_date, bt_desc, bt_amount, bt_vendor, allocated = candidate
                confidence = self.calculate_match_confidence(
                    receipt, candidate
                )
                
                if confidence >= 0.8:  # High confidence threshold
                    self.matches.append({
                        'receipt_id': receipt_id,
                        'banking_id': bt_id,
                        'confidence': confidence,
                        'receipt_amount': amount,
                        'banking_amount': bt_amount,
                        'receipt_vendor': vendor,
                        'banking_desc': bt_desc,
                        'receipt_date': receipt_date,
                        'banking_date': bt_date,
                        'reason': self.get_match_reason(receipt, candidate, confidence)
                    })
                    break  # Take first high-confidence match
                    
        print(f"  Found {len(self.matches)} automatic matches")
        
    def find_banking_candidates(self, receipt_date, vendor, amount):
        """Find potential banking matches for a receipt"""
        cur = self.conn.cursor()
        
        # Search window: ±30 days, vendor match, amount within ±$5
        date_min = receipt_date - timedelta(days=30)
        date_max = receipt_date + timedelta(days=30)
        amount_min = float(amount) - 5.0
        amount_max = float(amount) + 5.0
        
        sql = """
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.debit_amount,
                bt.vendor_extracted,
                COALESCE(SUM(r.gross_amount), 0) as allocated_amount
            FROM banking_transactions bt
            LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
            WHERE bt.transaction_date BETWEEN %s AND %s
                AND bt.debit_amount BETWEEN %s AND %s
            GROUP BY bt.transaction_id, bt.transaction_date, bt.description,
                     bt.debit_amount, bt.vendor_extracted
            HAVING bt.debit_amount > COALESCE(SUM(r.gross_amount), 0) + 0.01
            ORDER BY ABS(bt.debit_amount - %s), ABS(EXTRACT(EPOCH FROM (bt.transaction_date - %s)))
            LIMIT 10
        """
        
        cur.execute(sql, (date_min, date_max, amount_min, amount_max, float(amount), receipt_date))
        candidates = cur.fetchall()
        cur.close()
        
        # Filter by vendor similarity if vendor is known
        if vendor:
            candidates = [
                c for c in candidates
                if self.vendor_similarity(vendor, c[2]) > 0.5 or 
                   self.vendor_similarity(vendor, c[4] or '') > 0.5
            ]
            
        return candidates
        
    def vendor_similarity(self, vendor1, vendor2):
        """Calculate vendor name similarity (0-1)"""
        if not vendor1 or not vendor2:
            return 0.0
            
        v1 = vendor1.lower().strip()
        v2 = vendor2.lower().strip()
        
        # Exact match
        if v1 == v2:
            return 1.0
            
        # Contains match
        if v1 in v2 or v2 in v1:
            return 0.9
            
        # Common words
        words1 = set(v1.split())
        words2 = set(v2.split())
        common = len(words1 & words2)
        total = len(words1 | words2)
        
        return common / total if total > 0 else 0.0
        
    def calculate_match_confidence(self, receipt, banking):
        """Calculate match confidence score (0-1)"""
        receipt_id, receipt_date, vendor, amount, desc, ref, category = receipt
        bt_id, bt_date, bt_desc, bt_amount, bt_vendor, allocated = banking
        
        confidence = 0.0
        
        # Amount match (40% weight)
        amount_diff = abs(float(amount) - float(bt_amount - allocated))
        if amount_diff < 0.01:
            confidence += 0.40
        elif amount_diff < 1.0:
            confidence += 0.35
        elif amount_diff < 5.0:
            confidence += 0.25
        elif amount_diff < 10.0:
            confidence += 0.15
            
        # Date proximity (30% weight)
        date_diff = abs((receipt_date - bt_date).days)
        if date_diff == 0:
            confidence += 0.30
        elif date_diff <= 3:
            confidence += 0.25
        elif date_diff <= 7:
            confidence += 0.20
        elif date_diff <= 30:
            confidence += 0.10
            
        # Vendor match (30% weight)
        vendor_sim = max(
            self.vendor_similarity(vendor or '', bt_desc or ''),
            self.vendor_similarity(vendor or '', bt_vendor or '')
        )
        confidence += vendor_sim * 0.30
        
        return confidence
        
    def get_match_reason(self, receipt, banking, confidence):
        """Generate human-readable match reason"""
        receipt_id, receipt_date, vendor, amount, desc, ref, category = receipt
        bt_id, bt_date, bt_desc, bt_amount, bt_vendor, allocated = banking
        
        reasons = []
        
        amount_diff = abs(float(amount) - float(bt_amount - allocated))
        if amount_diff < 0.01:
            reasons.append("Exact amount match")
        else:
            reasons.append(f"Amount diff: ${amount_diff:.2f}")
            
        date_diff = abs((receipt_date - bt_date).days)
        if date_diff == 0:
            reasons.append("Same date")
        else:
            reasons.append(f"{date_diff} days apart")
            
        vendor_sim = max(
            self.vendor_similarity(vendor or '', bt_desc or ''),
            self.vendor_similarity(vendor or '', bt_vendor or '')
        )
        if vendor_sim > 0.8:
            reasons.append("Strong vendor match")
        elif vendor_sim > 0.5:
            reasons.append("Partial vendor match")
            
        return " | ".join(reasons)
        
    def generate_report(self):
        """Generate detailed match report"""
        print("\n" + "=" * 80)
        print("MATCHING REPORT")
        print("=" * 80)
        
        print(f"\n📊 SUMMARY:")
        print(f"  Total Receipts Unmatched: {len(self.unmatched_receipts)}")
        print(f"  Total Banking Unmatched: {len(self.unmatched_banking)}")
        print(f"  Automatic Matches Found: {len(self.matches)}")
        
        if self.matches:
            print(f"\n✅ HIGH-CONFIDENCE MATCHES ({len(self.matches)}):")
            for i, match in enumerate(self.matches[:20], 1):  # Show first 20
                print(f"\n  {i}. Receipt {match['receipt_id']} → Banking {match['banking_id']}")
                print(f"     Confidence: {match['confidence']:.1%}")
                print(f"     Receipt: ${match['receipt_amount']:,.2f} on {match['receipt_date']} ({match['receipt_vendor']})")
                print(f"     Banking: ${match['banking_amount']:,.2f} on {match['banking_date']}")
                print(f"     Reason: {match['reason']}")
                
            if len(self.matches) > 20:
                print(f"\n  ... and {len(self.matches) - 20} more matches")
                
        # Statistics
        if self.matches:
            total_matched_amount = sum(m['receipt_amount'] for m in self.matches)
            avg_confidence = sum(m['confidence'] for m in self.matches) / len(self.matches)
            print(f"\n📈 STATISTICS:")
            print(f"  Total Matched Amount: ${total_matched_amount:,.2f}")
            print(f"  Average Confidence: {avg_confidence:.1%}")
            
    def apply_matches(self):
        """Apply matches to database"""
        print("\n" + "=" * 80)
        print("APPLYING MATCHES TO DATABASE")
        print("=" * 80)
        
        cur = self.conn.cursor()
        applied = 0
        
        for match in self.matches:
            try:
                cur.execute("""
                    UPDATE receipts
                    SET banking_transaction_id = %s
                    WHERE receipt_id = %s
                """, (match['banking_id'], match['receipt_id']))
                applied += 1
            except Exception as e:
                print(f"  ❌ Error applying match {match['receipt_id']}: {e}")
                
        self.conn.commit()
        cur.close()
        
        print(f"\n✅ Applied {applied} matches successfully")
        
    def close(self):
        """Close database connection"""
        self.conn.close()


if __name__ == "__main__":
    import sys
    
    # Default: dry run
    dry_run = True
    
    # Check for --apply flag
    if '--apply' in sys.argv:
        dry_run = False
        print("⚠️  LIVE MODE - Will update database")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled")
            sys.exit(0)
    
    matcher = ReceiptBankingMatcher(dry_run=dry_run)
    matcher.run_matching()
    matcher.close()
    
    print("\n" + "=" * 80)
    if dry_run:
        print("DRY RUN COMPLETE - No changes made")
        print("Run with --apply flag to apply matches: python script.py --apply")
    else:
        print("MATCHING COMPLETE - Database updated")
    print("=" * 80)
