#!/usr/bin/env python3
"""
Analyze vendor reference XLS for updates (cleared, NSF, voided, donations, loans)
"""
import pandas as pd
import sys

def main():
    xls_path = "l:/limo/reports/cheque_vendor_reference.xlsx"
    
    print("="*80)
    print("VENDOR REFERENCE XLS ANALYSIS")
    print("="*80)
    
    xls = pd.ExcelFile(xls_path)
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_colwidth', 50)
    
    for sheet in xls.sheet_names:
        if sheet == 'Summary':
            continue
            
        print(f"\n{'='*80}")
        print(f"SHEET: {sheet}")
        print(f"{'='*80}")
        
        df = pd.read_excel(xls, sheet_name=sheet)
        
        # Identify cheque number column
        chq_col = 'CHQ #' if 'CHQ #' in df.columns else 'Cheque #'
        vendor_col = 'Vendor Name (ENTER HERE)'
        notes_col = 'Notes'
        
        print(f"\nTotal cheques: {len(df)}")
        
        # Find rows with vendor names entered
        has_vendor = df[vendor_col].notna() & (df[vendor_col].astype(str).str.strip() != '')
        print(f"Vendor names entered: {has_vendor.sum()}")
        
        # Find rows with notes
        has_notes = df[notes_col].notna() & (df[notes_col].astype(str).str.strip() != '')
        print(f"Rows with notes: {has_notes.sum()}")
        
        # Show all rows with vendor names or notes
        if has_vendor.any() or has_notes.any():
            print(f"\n{'='*80}")
            print("ROWS WITH UPDATES:")
            print(f"{'='*80}")
            
            updated_rows = df[has_vendor | has_notes].copy()
            
            for idx, row in updated_rows.iterrows():
                print(f"\nCheque #{row[chq_col]:.0f} | Date: {row['Date']} | Amount: ${row['Amount']:.2f}")
                print(f"  Current: {row['Current Description']}")
                
                if pd.notna(row[vendor_col]) and str(row[vendor_col]).strip():
                    print(f"  → VENDOR: {row[vendor_col]}")
                
                if pd.notna(row[notes_col]) and str(row[notes_col]).strip():
                    note = str(row[notes_col])
                    print(f"  → NOTES: {note}")
                    
                    # Check for special keywords
                    note_lower = note.lower()
                    if 'nsf' in note_lower:
                        print(f"     ⚠️  NSF DETECTED")
                    if 'void' in note_lower:
                        print(f"     ⚠️  VOIDED")
                    if 'clear' in note_lower or 'cleared' in note_lower:
                        print(f"     ✅ CLEARED")
                    if 'donat' in note_lower or 'charity' in note_lower:
                        print(f"     🎁 DONATION")
                    if 'loan' in note_lower or 'karen' in note_lower:
                        print(f"     💰 LOAN/PERSONAL")
                
                tx_id_val = f"{row['TX ID']:.0f}" if pd.notna(row['TX ID']) else 'N/A'
                print(f"  TX ID: {tx_id_val}")
        
        # Categorize updates
        print(f"\n{'='*80}")
        print("UPDATE CATEGORIES:")
        print(f"{'='*80}")
        
        categories = {
            'NSF': lambda n: 'nsf' in str(n).lower(),
            'VOID': lambda n: 'void' in str(n).lower(),
            'CLEARED': lambda n: 'clear' in str(n).lower(),
            'DONATION': lambda n: any(x in str(n).lower() for x in ['donat', 'charity']),
            'LOAN/KAREN': lambda n: any(x in str(n).lower() for x in ['loan', 'karen']),
        }
        
        for cat_name, check_func in categories.items():
            matching = df[df[notes_col].apply(check_func) | df[vendor_col].apply(check_func)]
            if len(matching) > 0:
                print(f"\n{cat_name}: {len(matching)} cheques")
                for _, row in matching.iterrows():
                    print(f"  #{row[chq_col]:.0f} ${row['Amount']:.2f} - {row[vendor_col] if pd.notna(row[vendor_col]) else row['Current Description']}")

if __name__ == "__main__":
    main()
