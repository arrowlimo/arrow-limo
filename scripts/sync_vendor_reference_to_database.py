#!/usr/bin/env python3
"""
Sync vendor reference XLS updates to database
- Update vendor names from "Vendor Name (ENTER HERE)" column
- Mark NSF cheques (e.g., cheque #350 Karen Richard NSF, cheque #213 Marc Cote NSF)
- Mark voided cheques (from notes)
- Handle donations
- Handle loans/personal payments (Karen Richard)
"""
import pandas as pd
import psycopg2
import sys
from datetime import datetime

# Database connection
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    xls_path = "l:/limo/reports/cheque_vendor_reference.xlsx"
    
    print("="*80)
    print("VENDOR REFERENCE XLS → DATABASE SYNC")
    print("="*80)
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Add is_nsf and is_voided columns if they don't exist
    print("\nChecking for is_nsf and is_voided columns...")
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name IN ('is_nsf', 'is_voided')
    """)
    existing_cols = [r[0] for r in cur.fetchall()]
    
    if 'is_nsf' not in existing_cols:
        print("  Adding is_nsf column...")
        cur.execute("ALTER TABLE receipts ADD COLUMN is_nsf BOOLEAN DEFAULT FALSE")
        conn.commit()
        print("  ✅ is_nsf column added")
    else:
        print("  ✅ is_nsf column already exists")
    
    if 'is_voided' not in existing_cols:
        print("  Adding is_voided column...")
        cur.execute("ALTER TABLE receipts ADD COLUMN is_voided BOOLEAN DEFAULT FALSE")
        conn.commit()
        print("  ✅ is_voided column added")
    else:
        print("  ✅ is_voided column already exists")
    
    xls = pd.ExcelFile(xls_path)
    
    updates = {
        'vendor_updated': 0,
        'nsf_marked': 0,
        'void_marked': 0,
        'donations': 0,
        'loans': 0,
        'errors': []
    }
    
    for sheet in xls.sheet_names:
        if sheet == 'Summary':
            continue
        
        print(f"\n{'='*80}")
        print(f"PROCESSING SHEET: {sheet}")
        print(f"{'='*80}")
        
        df = pd.read_excel(xls, sheet_name=sheet)
        
        # Identify columns
        chq_col = 'CHQ #' if 'CHQ #' in df.columns else 'Cheque #'
        vendor_col = 'Vendor Name (ENTER HERE)'
        notes_col = 'Notes'
        tx_id_col = 'TX ID'
        desc_col = 'Current Description'
        
        for idx, row in df.iterrows():
            tx_id = row[tx_id_col]
            if pd.isna(tx_id):
                continue
            
            tx_id = int(tx_id)
            cheque_num = row[chq_col] if pd.notna(row[chq_col]) else None
            current_desc = row[desc_col] if pd.notna(row[desc_col]) else ''
            
            # Check if there's a vendor name to update
            new_vendor = None
            if pd.notna(row[vendor_col]) and str(row[vendor_col]).strip():
                new_vendor = str(row[vendor_col]).strip()
            
            # Check for NSF in description or notes
            is_nsf = False
            if 'NSF' in current_desc.upper():
                is_nsf = True
            if pd.notna(row[notes_col]) and 'NSF' in str(row[notes_col]).upper():
                is_nsf = True
            
            # Check for VOID in notes
            is_void = False
            if pd.notna(row[notes_col]) and 'VOID' in str(row[notes_col]).upper():
                is_void = True
            
            # Check for donation keywords
            is_donation = False
            check_text = f"{current_desc} {row[notes_col] if pd.notna(row[notes_col]) else ''} {new_vendor if new_vendor else ''}"
            if any(kw in check_text.lower() for kw in ['donation', 'charity', 'charitable']):
                is_donation = True
            
            # Check for loan/personal (Karen Richard)
            is_loan = False
            if any(kw in check_text.lower() for kw in ['loan', 'karen richard', 'personal loan']):
                is_loan = True
            
            # Get current receipt info
            cur.execute("""
                SELECT receipt_id, vendor_name, comment, is_nsf, is_voided
                FROM receipts
                WHERE banking_transaction_id = %s
            """, (tx_id,))
            
            result = cur.fetchone()
            if not result:
                print(f"  ⚠️  TX {tx_id} (Cheque #{cheque_num}) not found in receipts")
                updates['errors'].append(f"TX {tx_id} not found")
                continue
            
            receipt_id, current_vendor, current_notes, current_is_nsf, current_is_voided = result
            
            changes = []
            update_fields = []
            update_values = []
            
            # Update vendor name
            if new_vendor and new_vendor != current_vendor:
                update_fields.append("vendor_name = %s")
                update_values.append(new_vendor)
                changes.append(f"vendor: '{current_vendor}' → '{new_vendor}'")
                updates['vendor_updated'] += 1
            
            # Update NSF flag
            if is_nsf and not current_is_nsf:
                update_fields.append("is_nsf = TRUE")
                changes.append("NSF: FALSE → TRUE")
                updates['nsf_marked'] += 1
            
            # Update voided flag
            if is_void and not current_is_voided:
                update_fields.append("is_voided = TRUE")
                changes.append("VOIDED: FALSE → TRUE")
                updates['void_marked'] += 1
            
            # Add notes about donations or loans
            note_additions = []
            if is_donation:
                if not current_notes or 'DONATION' not in current_notes.upper():
                    note_additions.append("DONATION")
                    updates['donations'] += 1
            
            if is_loan:
                if not current_notes or 'LOAN' not in current_notes.upper():
                    note_additions.append("LOAN/PERSONAL - Karen Richard")
                    updates['loans'] += 1
            
            if note_additions:
                new_note = "; ".join(note_additions)
                if current_notes:
                    new_note = f"{current_notes}; {new_note}"
                update_fields.append("comment = %s")
                update_values.append(new_note)
                changes.append(f"notes: added '{'; '.join(note_additions)}'")
            
            # Execute update if there are changes
            if update_fields:
                update_values.append(receipt_id)
                sql = f"""
                    UPDATE receipts
                    SET {', '.join(update_fields)}
                    WHERE receipt_id = %s
                """
                
                print(f"\n  Cheque #{cheque_num} (TX {tx_id}, Receipt {receipt_id}):")
                for change in changes:
                    print(f"    • {change}")
                
                cur.execute(sql, update_values)
    
    # Summary
    print(f"\n{'='*80}")
    print("SYNC SUMMARY")
    print(f"{'='*80}")
    print(f"Vendor names updated: {updates['vendor_updated']}")
    print(f"NSF flags marked: {updates['nsf_marked']}")
    print(f"VOID flags marked: {updates['void_marked']}")
    print(f"Donations noted: {updates['donations']}")
    print(f"Loans noted: {updates['loans']}")
    print(f"Errors: {len(updates['errors'])}")
    
    if updates['errors']:
        print("\nErrors:")
        for err in updates['errors']:
            print(f"  - {err}")
    
    # Confirm
    total_changes = (updates['vendor_updated'] + updates['nsf_marked'] + 
                    updates['void_marked'] + updates['donations'] + updates['loans'])
    
    if total_changes > 0:
        print(f"\nTotal changes: {total_changes}")
        response = input("\nCommit these changes to the database? (yes/no): ")
        if response.lower() == 'yes':
            conn.commit()
            print("\n✅ Changes committed successfully!")
        else:
            conn.rollback()
            print("\n❌ Changes rolled back.")
    else:
        print("\n✅ No changes needed - database is up to date!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
