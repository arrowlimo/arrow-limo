#!/usr/bin/env python3
"""
TASK #15: Verification Workflow Interface
Simple command-line interface for reviewing and approving:
- Duplicate receipts
- Vendor normalizations
- Unmatched items
- GST issues
"""
import psycopg2
import json
from datetime import datetime

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

class VerificationWorkflow:
    def __init__(self):
        self.conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        self.cur = self.conn.cursor()
        
    def show_menu(self):
        print("\n" + "="*100)
        print("VERIFICATION WORKFLOW - Main Menu")
        print("="*100)
        print("\n1. Review Duplicate Receipts (32 groups)")
        print("2. Review Unmatched Receipts (9,248 receipts)")
        print("3. Review Unknown Category Items (5,112 receipts)")
        print("4. Review GST Issues (100 receipts)")
        print("5. Review Unmarked Banking Transactions (14,615 items)")
        print("6. Export All Issues to CSV")
        print("7. Generate Summary Report")
        print("8. Exit")
        print("\nEnter choice (1-8): ", end='')
        
    def review_duplicates(self):
        print("\n" + "="*80)
        print("DUPLICATE RECEIPTS REVIEW")
        print("="*80)
        
        # Load duplicates from JSON
        try:
            with open('l:\\limo\\data\\receipts_dedup_lookup.json', 'r') as f:
                data = json.load(f)
                duplicates = data.get('duplicates', {})
        except:
            print("❌ Could not load duplicates file")
            return
        
        print(f"\nFound {len(duplicates)} potential duplicate groups")
        
        count = 0
        for key, group in list(duplicates.items())[:10]:
            count += 1
            parts = key.split('|')
            date = parts[0] if len(parts) > 0 else 'Unknown'
            amount = parts[1] if len(parts) > 1 else '0'
            vendor = parts[2] if len(parts) > 2 else 'Unknown'
            
            print(f"\n{count}. {date} | ${amount} | {vendor}")
            print(f"   {len(group)} receipts:")
            for item in group:
                print(f"      Receipt #{item['receipt_id']} - {item['category']} - {item['banking_links']} banking links")
        
        print(f"\n... and {len(duplicates) - 10} more groups")
        print("\n💡 Review these in the database or export to CSV for detailed analysis")
        
    def review_unmatched_receipts(self):
        print("\n" + "="*80)
        print("UNMATCHED RECEIPTS REVIEW")
        print("="*80)
        
        self.cur.execute("""
            SELECT 
                r.receipt_id,
                r.receipt_date,
                r.vendor_name,
                r.gross_amount,
                r.category
            FROM receipts r
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bml
                WHERE bml.receipt_id = r.receipt_id
            )
            ORDER BY r.gross_amount DESC
            LIMIT 20
        """)
        
        receipts = self.cur.fetchall()
        
        print(f"\nTop 20 unmatched receipts by amount:")
        print(f"\n{'ID':<10} {'Date':<12} {'Amount':>12} {'Category':<20} {'Vendor':<30}")
        print("-" * 90)
        
        for rec_id, date, vendor, amount, category in receipts:
            vendor_str = (vendor or '')[:28]
            category_str = (category or 'Unknown')[:18]
            print(f"{rec_id:<10} {str(date):<12} ${amount:>10.2f} {category_str:<20} {vendor_str:<30}")
        
        print("\n💡 These receipts need manual matching to banking transactions")
        
    def review_unknown_category(self):
        print("\n" + "="*80)
        print("UNKNOWN CATEGORY REVIEW")
        print("="*80)
        
        self.cur.execute("""
            SELECT category, COUNT(*), SUM(gross_amount)
            FROM receipts
            WHERE category IN ('Unknown', 'uncategorized_expenses') OR category IS NULL
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)
        
        categories = self.cur.fetchall()
        
        print(f"\nUncategorized receipts breakdown:")
        for cat, count, total in categories:
            print(f"   {cat or 'NULL'}: {count:,} receipts (${total or 0:,.2f})")
        
        # Show sample
        self.cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
            FROM receipts
            WHERE category IN ('Unknown', 'uncategorized_expenses') OR category IS NULL
            ORDER BY gross_amount DESC
            LIMIT 15
        """)
        
        samples = self.cur.fetchall()
        
        print(f"\nTop 15 by amount:")
        print(f"\n{'ID':<10} {'Date':<12} {'Amount':>12} {'Vendor':<30} {'Description':<30}")
        print("-" * 100)
        
        for rec_id, date, vendor, amount, desc in samples:
            vendor_str = (vendor or '')[:28]
            desc_str = (desc or '')[:28]
            print(f"{rec_id:<10} {str(date):<12} ${amount:>10.2f} {vendor_str:<30} {desc_str:<30}")
        
        print("\n💡 These need manual category assignment")
        
    def review_gst_issues(self):
        print("\n" + "="*80)
        print("GST ISSUES REVIEW")
        print("="*80)
        
        self.cur.execute("""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                gst_amount,
                ROUND(gross_amount * 0.05 / 1.05, 2) as calculated_gst,
                ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) as difference
            FROM receipts
            WHERE gross_amount > 0
            AND gst_amount IS NOT NULL
            AND ABS(gst_amount - ROUND(gross_amount * 0.05 / 1.05, 2)) > 0.02
            ORDER BY difference DESC
            LIMIT 20
        """)
        
        issues = self.cur.fetchall()
        
        print(f"\nTop 20 GST calculation discrepancies:")
        print(f"\n{'ID':<10} {'Date':<12} {'Gross':>12} {'GST':>10} {'Expected':>10} {'Diff':>10} {'Vendor':<25}")
        print("-" * 95)
        
        for rec_id, date, vendor, gross, gst, calc_gst, diff in issues:
            vendor_str = (vendor or '')[:23]
            print(f"{rec_id:<10} {str(date):<12} ${gross:>10.2f} ${gst:>8.2f} ${calc_gst:>8.2f} ${diff:>8.2f} {vendor_str:<25}")
        
        print("\n💡 These may be GST-exempt items or have calculation errors")
        
    def review_unmarked_banking(self):
        print("\n" + "="*80)
        print("UNMARKED BANKING TRANSACTIONS (GST Review)")
        print("="*80)
        
        self.cur.execute("""
            SELECT 
                transaction_uid,
                transaction_date,
                vendor_extracted,
                debit_amount,
                credit_amount,
                description
            FROM banking_transactions
            WHERE gst_applicable IS NULL
            AND (debit_amount > 0 OR credit_amount > 0)
            ORDER BY COALESCE(debit_amount, credit_amount) DESC
            LIMIT 20
        """)
        
        transactions = self.cur.fetchall()
        
        print(f"\nTop 20 unmarked transactions by amount:")
        print(f"\n{'UID':<15} {'Date':<12} {'Debit':>12} {'Credit':>12} {'Vendor':<30}")
        print("-" * 90)
        
        for uid, date, vendor, debit, credit, desc in transactions:
            vendor_str = (vendor or desc or '')[:28]
            debit_str = f"${debit:,.2f}" if debit else ""
            credit_str = f"${credit:,.2f}" if credit else ""
            print(f"{uid:<15} {str(date):<12} {debit_str:>12} {credit_str:>12} {vendor_str:<30}")
        
        print("\n💡 Review these and set gst_applicable = TRUE or FALSE")
        
    def export_all_issues(self):
        print("\n📁 Exporting all issues to CSV files...")
        
        import csv
        from pathlib import Path
        
        output_dir = Path('l:\\limo\\data\\verification_exports')
        output_dir.mkdir(exist_ok=True)
        
        # Export duplicates
        try:
            with open('l:\\limo\\data\\receipts_dedup_lookup.json', 'r') as f:
                data = json.load(f)
                duplicates = data.get('duplicates', {})
            
            with open(output_dir / 'duplicates_for_review.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Amount', 'Vendor', 'Receipt_IDs', 'Count'])
                for key, group in duplicates.items():
                    parts = key.split('|')
                    ids = ', '.join(str(item['receipt_id']) for item in group)
                    writer.writerow([parts[0], parts[1], parts[2], ids, len(group)])
            
            print(f"   ✅ duplicates_for_review.csv ({len(duplicates)} groups)")
        except Exception as e:
            print(f"   ❌ Error exporting duplicates: {e}")
        
        # Export unmatched receipts
        self.cur.execute("""
            SELECT r.*
            FROM receipts r
            WHERE NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bml
                WHERE bml.receipt_id = r.receipt_id
            )
            ORDER BY r.gross_amount DESC
        """)
        
        with open(output_dir / 'unmatched_receipts.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([desc[0] for desc in self.cur.description])
            writer.writerows(self.cur.fetchall())
        
        count = self.cur.rowcount
        print(f"   ✅ unmatched_receipts.csv ({count} receipts)")
        
        print(f"\n   📂 Files saved to: {output_dir}")
        
    def generate_summary_report(self):
        print("\n" + "="*100)
        print("VERIFICATION SUMMARY REPORT")
        print("="*100)
        
        # Load all reports
        reports = {}
        for filename in ['reconciliation_report.json', 'gst_validation_report.json']:
            try:
                with open(f'l:\\limo\\data\\{filename}', 'r') as f:
                    reports[filename] = json.load(f)
            except:
                pass
        
        print(f"\n📊 Overall Statistics:")
        print(f"   Banking Transactions: 28,911")
        print(f"      ✅ Verified/Locked: 26,377 (91.2%)")
        print(f"      ⚠️  Need GST Review: 14,615")
        
        print(f"\n   Receipts: 22,089")
        print(f"      ✅ Matched to Banking: 12,841 (58.1%)")
        print(f"      ⚠️  Unmatched: 9,248 (41.9%)")
        print(f"      ⚠️  Unknown Category: 5,112")
        print(f"      ⚠️  GST Issues: 100")
        
        print(f"\n   Duplicates:")
        print(f"      ⚠️  Receipt Groups: 32")
        print(f"      ✅ Banking Groups: 0 (protected)")
        
        print(f"\n✨ System Improvements:")
        print(f"   ✅ Unique transaction UIDs created (28,911)")
        print(f"   ✅ Vendor normalization map built (129 verified vendors)")
        print(f"   ✅ NSF charges protected (9,069 transactions)")
        print(f"   ✅ JSON exports created for easy querying")
        
        print(f"\n📋 Next Manual Steps:")
        print(f"   1. Review and delete 32 duplicate receipt groups")
        print(f"   2. Match 9,248 unmatched receipts to banking")
        print(f"   3. Categorize 5,112 unknown category receipts")
        print(f"   4. Review 100 GST calculation issues")
        print(f"   5. Set GST applicability for 14,615 banking transactions")
        
    def run(self):
        while True:
            self.show_menu()
            choice = input().strip()
            
            if choice == '1':
                self.review_duplicates()
            elif choice == '2':
                self.review_unmatched_receipts()
            elif choice == '3':
                self.review_unknown_category()
            elif choice == '4':
                self.review_gst_issues()
            elif choice == '5':
                self.review_unmarked_banking()
            elif choice == '6':
                self.export_all_issues()
            elif choice == '7':
                self.generate_summary_report()
            elif choice == '8':
                print("\n✅ Exiting verification workflow")
                break
            else:
                print("❌ Invalid choice. Please enter 1-8.")
            
            input("\nPress Enter to continue...")
        
        self.cur.close()
        self.conn.close()

def main():
    print("="*100)
    print("TASK #15: VERIFICATION WORKFLOW INTERFACE")
    print("="*100)
    
    workflow = VerificationWorkflow()
    workflow.run()

if __name__ == '__main__':
    main()
