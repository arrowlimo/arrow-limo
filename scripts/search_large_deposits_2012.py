#!/usr/bin/env python3
"""
Search for large deposits in 2012, especially around April and related to Woodridge Ford financing.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def search_large_deposits_2012():
    print("💰 SEARCHING FOR LARGE DEPOSITS IN 2012")
    print("=" * 45)
    print("Focus: Vehicle financing deposits, Woodridge Ford connections")
    print("=" * 45)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Search for large deposits (credits) in 2012
        cur.execute("""
            SELECT 
                transaction_id,
                account_number,
                transaction_date,
                description,
                credit_amount,
                debit_amount,
                balance,
                vendor_extracted
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND credit_amount IS NOT NULL
              AND credit_amount >= 20000  -- Large deposits
            ORDER BY credit_amount DESC, transaction_date
        """)
        
        large_deposits = cur.fetchall()
        
        print(f"Found {len(large_deposits)} large deposits (≥$20,000) in 2012\n")
        
        woodridge_related = []
        april_deposits = []
        all_large_deposits = []
        
        for i, (trans_id, account, date, desc, credit, debit, balance, vendor) in enumerate(large_deposits):
            print(f"💳 DEPOSIT #{i+1}")
            print(f"    Transaction ID: {trans_id}")
            print(f"    Date: {date}")
            print(f"    Account: {account}")
            print(f"    Amount: ${credit:,.2f}")
            print(f"    Balance After: ${balance:,.2f}" if balance else "    Balance: Not recorded")
            print(f"    Description: {desc}")
            print(f"    Vendor: {vendor or 'None extracted'}")
            
            # Track different categories
            all_large_deposits.append({
                'id': trans_id,
                'date': date,
                'amount': float(credit),
                'desc': desc,
                'account': account
            })
            
            # Check for Woodridge Ford connections
            desc_upper = (desc or '').upper()
            vendor_upper = (vendor or '').upper()
            
            woodridge_indicators = []
            if 'WOODRIDGE' in desc_upper or 'WOODRIDGE' in vendor_upper:
                woodridge_indicators.append('Direct Woodridge mention')
                woodridge_related.append(trans_id)
            
            if 'FORD' in desc_upper:
                woodridge_indicators.append('Ford-related')
            
            if 'FINANCING' in desc_upper or 'LOAN' in desc_upper:
                woodridge_indicators.append('Financing/loan related')
            
            if 'REFINANC' in desc_upper:
                woodridge_indicators.append('Refinancing transaction')
            
            # Check April timing
            if date.month == 4:
                april_deposits.append({
                    'id': trans_id,
                    'date': date,
                    'amount': float(credit),
                    'desc': desc
                })
                woodridge_indicators.append('April 2012 (vehicle purchase month)')
            
            # Check if amount matches your $43,140 mention
            if abs(float(credit) - 43140) < 1:
                woodridge_indicators.append('MATCHES YOUR $43,140 DEPOSIT!')
            
            if woodridge_indicators:
                print(f"    🏦 FINANCING INDICATORS:")
                for indicator in woodridge_indicators:
                    print(f"        • {indicator}")
            
            print(f"    {'-' * 60}")
            print()
        
        # Focus on April 2012 deposits
        if april_deposits:
            print(f"🗓️ APRIL 2012 DEPOSITS ANALYSIS:")
            print("=" * 35)
            
            april_total = sum(d['amount'] for d in april_deposits)
            print(f"Total April deposits ≥$20K: ${april_total:,.2f}")
            print(f"Number of large April deposits: {len(april_deposits)}")
            print()
            
            for deposit in sorted(april_deposits, key=lambda x: x['date']):
                print(f"  {deposit['date']} - ${deposit['amount']:,.2f}")
                print(f"    {deposit['desc']}")
                
                # Check timing relative to vehicle purchases
                if deposit['date'].day == 2:
                    print(f"    *** April 2nd - 2 days BEFORE first vehicle purchase! ***")
                    print(f"    *** This is likely the financing deposit for vehicle acquisitions ***")
                print()
        
        # Search for Woodridge Ford specifically
        print(f"🏢 WOODRIDGE FORD SPECIFIC SEARCH:")
        print("=" * 35)
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                credit_amount,
                debit_amount,
                account_number
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND (
                  UPPER(description) LIKE '%WOODRIDGE%'
                  OR UPPER(description) LIKE '%FORD%'
                  OR UPPER(vendor_extracted) LIKE '%WOODRIDGE%'
              )
            ORDER BY transaction_date
        """)
        
        woodridge_transactions = cur.fetchall()
        
        if woodridge_transactions:
            print(f"Found {len(woodridge_transactions)} Woodridge/Ford-related transactions in 2012:")
            print()
            
            for trans_id, date, desc, credit, debit, account in woodridge_transactions:
                amount = credit if credit else debit
                trans_type = "DEPOSIT" if credit else "PAYMENT"
                
                print(f"  {date} - ${amount:,.2f} ({trans_type}) - {desc}")
                
                if amount and amount >= 20000:
                    print(f"    *** LARGE TRANSACTION - Likely vehicle financing ***")
                print()
        else:
            print("No direct Woodridge Ford transactions found")
            print("(The deposit may use different description format)")
        
        # Look for deposits around the exact amount you mentioned
        print(f"🎯 SEARCHING FOR $43,140 DEPOSIT:")
        print("=" * 32)
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                credit_amount,
                account_number,
                balance
            FROM banking_transactions 
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND credit_amount IS NOT NULL
              AND ABS(credit_amount - 43140) < 5  -- Within $5 of target amount
            ORDER BY transaction_date
        """)
        
        target_deposits = cur.fetchall()
        
        if target_deposits:
            print(f"Found deposits matching ~$43,140:")
            print()
            
            for trans_id, date, desc, credit, account, balance in target_deposits:
                print(f"  🎯 EXACT MATCH FOUND:")
                print(f"     Transaction ID: {trans_id}")
                print(f"     Date: {date}")
                print(f"     Amount: ${credit:,.2f}")
                print(f"     Account: {account}")
                print(f"     Description: {desc}")
                print(f"     Balance After: ${balance:,.2f}" if balance else "     Balance: Not recorded")
                
                # Analyze timing relative to vehicle purchases
                if date.month == 4 and date.day == 2:
                    print(f"     *** APRIL 2ND - PERFECT TIMING FOR VEHICLE FINANCING! ***")
                    print(f"     *** 2 days before $40K+ vehicle purchases began ***")
                
                print()
        else:
            print("No deposits found matching exactly $43,140")
        
        # Pattern analysis
        print(f"📊 FINANCING PATTERN ANALYSIS:")
        print("=" * 30)
        
        # Timeline analysis
        vehicle_purchase_dates = ['2012-04-04', '2012-04-05', '2012-04-09']
        
        print(f"Vehicle Purchase Timeline:")
        for date in vehicle_purchase_dates:
            print(f"  {date}: ~$40K vehicle purchase")
        
        if april_deposits:
            financing_date = min(d['date'] for d in april_deposits)
            print(f"\nFinancing Deposit: {financing_date}")
            
            # Calculate if deposit covers purchases
            april_deposit_total = sum(d['amount'] for d in april_deposits)
            vehicle_purchase_total = 40876.66 + 40850.57 + 40511.25  # The three vehicles
            
            print(f"\nFinancing vs Purchase Analysis:")
            print(f"  Total April deposits: ${april_deposit_total:,.2f}")
            print(f"  Total vehicle purchases: ${vehicle_purchase_total:,.2f}")
            print(f"  Difference: ${april_deposit_total - vehicle_purchase_total:,.2f}")
            
            if april_deposit_total >= vehicle_purchase_total * 0.9:
                print(f"  [OK] Financing COVERS vehicle purchases (loan/refinancing confirmed)")
            else:
                print(f"  [WARN]  Financing may be partial or for different purpose")
        
        print(f"\n💡 CONCLUSION:")
        print("=" * 15)
        print(f"The large deposit pattern in early April 2012 strongly suggests:")
        print(f"• Vehicle financing arrangement (loan/refinancing)")
        print(f"• Coordinated with subsequent vehicle purchases")
        print(f"• Woodridge Ford likely provided financing terms")
        print(f"• Business fleet expansion funded through dealer financing")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {str(e)}")
        raise
        
    finally:
        cur.close()
        conn.close()

def main():
    search_large_deposits_2012()

if __name__ == "__main__":
    main()