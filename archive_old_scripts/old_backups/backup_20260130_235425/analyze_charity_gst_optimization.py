"""Analyze GST optimization strategies for charity/trade charters.

Canadian Tax Law Context:
1. Donated services = NO GST (promotional expense, no consideration received)
2. GST only applies to actual consideration received (payments)
3. Gratuities are GST-EXEMPT (voluntary payments after service completion)
4. Beverage/alcohol charges ARE subject to GST
5. Certificate face value = deferred revenue, GST collected on redemption only

Strategy: Maximize gratuity classification, minimize GST base.
"""
import psycopg2
from decimal import Decimal

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("GST OPTIMIZATION ANALYSIS FOR CHARITY/TRADE CHARTERS")
    print("=" * 100)
    print()
    
    # Get all charity/trade charters with payment details
    cur.execute("""
        SELECT 
            ctc.reserve_number,
            ctc.classification,
            ctc.is_tax_locked,
            c.charter_date,
            ctc.rate,
            ctc.payments_total,
            ctc.beverage_service,
            ctc.payment_methods,
            cl.client_name,
            c.notes,
            c.booking_notes
        FROM charity_trade_charters ctc
        JOIN charters c ON ctc.charter_id = c.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        ORDER BY c.charter_date
    """)
    
    rows = cur.fetchall()
    
    # Classification strategies
    strategies = {
        'full_donation': {
            'gst_base': Decimal('0'),
            'gratuity': Decimal('0'),
            'beverage': Decimal('0'),
            'gst_amount': Decimal('0'),
            'reason': 'No consideration received - pure donation. NO GST.'
        },
        'donated_unredeemed_or_unpaid': {
            'gst_base': Decimal('0'),
            'gratuity': Decimal('0'),
            'beverage': Decimal('0'),
            'gst_amount': Decimal('0'),
            'reason': 'Certificate not redeemed. NO GST until redemption.'
        }
    }
    
    results = []
    total_payments = Decimal('0')
    total_gst_current = Decimal('0')
    total_gst_optimized = Decimal('0')
    total_gratuity_reclassed = Decimal('0')
    total_beverage_only_gst = Decimal('0')
    
    for row in rows:
        reserve_number = row[0]
        classification = row[1]
        is_tax_locked = row[2]
        charter_date = row[3]
        rate = Decimal(str(row[4])) if row[4] else Decimal('0')
        payments_total = Decimal(str(row[5]))
        beverage_service = row[6]
        payment_methods = row[7] or ''
        client_name = row[8] or 'Unknown'
        notes = (row[9] or '') + ' ' + (row[10] or '')
        
        total_payments += payments_total
        
        # Current GST calculation (assuming all payments are GST-inclusive)
        current_gst = payments_total * Decimal('0.05') / Decimal('1.05') if payments_total > 0 else Decimal('0')
        total_gst_current += current_gst
        
        # OPTIMIZATION STRATEGY
        if classification == 'full_donation' or classification == 'donated_unredeemed_or_unpaid':
            # No payments, no GST
            optimized_gst = Decimal('0')
            gratuity_amount = Decimal('0')
            beverage_gst = Decimal('0')
            strategy = 'No GST - donation/unredeemed'
            
        elif classification == 'partial_trade':
            # Small payment for donated service
            # Strategy: Classify entire payment as gratuity (voluntary, post-service)
            gratuity_amount = payments_total
            beverage_gst = Decimal('0')
            optimized_gst = Decimal('0')
            total_gratuity_reclassed += gratuity_amount
            strategy = 'GRATUITY ONLY (voluntary payment post-service) - NO GST'
            
        elif classification == 'partial_trade_extras':
            # Donated base, paid extras
            # Strategy: If beverage service, attribute payment to beverages + gratuity
            if beverage_service == 'Y':
                # Assume 20% of payment is beverage (GST applies), 80% is gratuity
                beverage_base = payments_total * Decimal('0.20')
                beverage_gst = beverage_base * Decimal('0.05') / Decimal('1.05')
                gratuity_amount = payments_total * Decimal('0.80')
                optimized_gst = beverage_gst
                total_beverage_only_gst += beverage_gst
                total_gratuity_reclassed += gratuity_amount
                strategy = 'BEVERAGE (20% w/GST) + GRATUITY (80% no GST)'
            else:
                # No beverage, entire payment is gratuity
                gratuity_amount = payments_total
                beverage_gst = Decimal('0')
                optimized_gst = Decimal('0')
                total_gratuity_reclassed += gratuity_amount
                strategy = 'GRATUITY ONLY - NO GST'
                
        elif classification == 'paid_full':
            # Fully paid at promotional rate
            # Strategy: If overpaid (payment > rate), excess is gratuity
            if payments_total > rate:
                excess = payments_total - rate
                # Rate portion: check for beverage
                if beverage_service == 'Y':
                    # 30% of rate is beverage, 70% is transport service
                    beverage_base = rate * Decimal('0.30')
                    beverage_gst = beverage_base * Decimal('0.05') / Decimal('1.05')
                    transport_base = rate * Decimal('0.70')
                    transport_gst = transport_base * Decimal('0.05') / Decimal('1.05')
                    gratuity_amount = excess
                    optimized_gst = beverage_gst + transport_gst
                    total_beverage_only_gst += beverage_gst
                    total_gratuity_reclassed += gratuity_amount
                    strategy = f'PROMO RATE (w/GST ${rate}) + GRATUITY (${excess} no GST)'
                else:
                    # No beverage, rate is transport service + excess is gratuity
                    transport_gst = rate * Decimal('0.05') / Decimal('1.05')
                    gratuity_amount = excess
                    optimized_gst = transport_gst
                    total_gratuity_reclassed += gratuity_amount
                    strategy = f'PROMO TRANSPORT (w/GST ${rate}) + GRATUITY (${excess} no GST)'
            else:
                # Payment <= rate, treat as discounted promo rate with GST
                if beverage_service == 'Y':
                    beverage_base = payments_total * Decimal('0.30')
                    beverage_gst = beverage_base * Decimal('0.05') / Decimal('1.05')
                    optimized_gst = beverage_gst + (payments_total - beverage_base) * Decimal('0.05') / Decimal('1.05')
                    total_beverage_only_gst += beverage_gst
                    gratuity_amount = Decimal('0')
                    strategy = 'PROMO RATE (reduced, w/GST on all)'
                else:
                    optimized_gst = payments_total * Decimal('0.05') / Decimal('1.05')
                    gratuity_amount = Decimal('0')
                    strategy = 'PROMO TRANSPORT SERVICE (w/GST)'
                    
        else:  # mixed_or_uncertain
            # Conservative: assume 50% gratuity, 50% service with GST
            gratuity_amount = payments_total * Decimal('0.50')
            service_amount = payments_total * Decimal('0.50')
            optimized_gst = service_amount * Decimal('0.05') / Decimal('1.05')
            total_gratuity_reclassed += gratuity_amount
            strategy = 'MIXED: 50% service w/GST, 50% gratuity no GST'
        
        total_gst_optimized += optimized_gst
        
        # Calculate savings
        gst_savings = current_gst - optimized_gst
        
        results.append({
            'reserve_number': reserve_number,
            'classification': classification,
            'is_tax_locked': is_tax_locked,
            'charter_date': charter_date,
            'client_name': client_name,
            'rate': rate,
            'payments_total': payments_total,
            'beverage_service': beverage_service,
            'current_gst': current_gst,
            'optimized_gst': optimized_gst,
            'gratuity_amount': gratuity_amount,
            'gst_savings': gst_savings,
            'strategy': strategy
        })
    
    # Print summary
    print(f"Total Payments Analyzed: ${total_payments:,.2f}")
    print(f"Current GST Liability (all payments GST-inclusive): ${total_gst_current:,.2f}")
    print(f"Optimized GST Liability: ${total_gst_optimized:,.2f}")
    print(f"GST SAVINGS: ${total_gst_current - total_gst_optimized:,.2f}")
    print(f"Reclassified as Gratuity (GST-exempt): ${total_gratuity_reclassed:,.2f}")
    print()
    
    # Breakdown by classification
    print("=" * 100)
    print("GST OPTIMIZATION BY CLASSIFICATION:")
    print("=" * 100)
    
    for classification in ['full_donation', 'partial_trade', 'partial_trade_extras', 'paid_full', 
                           'mixed_or_uncertain', 'donated_unredeemed_or_unpaid']:
        class_results = [r for r in results if r['classification'] == classification]
        if not class_results:
            continue
            
        class_count = len(class_results)
        class_payments = sum(r['payments_total'] for r in class_results)
        class_current_gst = sum(r['current_gst'] for r in class_results)
        class_optimized_gst = sum(r['optimized_gst'] for r in class_results)
        class_savings = class_current_gst - class_optimized_gst
        class_gratuity = sum(r['gratuity_amount'] for r in class_results)
        
        print(f"\n{classification.upper()} ({class_count} charters):")
        print(f"  Total Payments: ${class_payments:,.2f}")
        print(f"  Current GST: ${class_current_gst:,.2f}")
        print(f"  Optimized GST: ${class_optimized_gst:,.2f}")
        print(f"  GST Savings: ${class_savings:,.2f} ({(class_savings/class_current_gst*100) if class_current_gst > 0 else 0:.1f}%)")
        print(f"  Reclassed as Gratuity: ${class_gratuity:,.2f}")
        
        # Show strategy for first example
        if class_results:
            print(f"  Strategy: {class_results[0]['strategy']}")
    
    print()
    print("=" * 100)
    print("TAX-LOCKED STATUS IMPACT:")
    print("=" * 100)
    
    locked_results = [r for r in results if r['is_tax_locked']]
    unlocked_results = [r for r in results if not r['is_tax_locked']]
    
    print(f"\nPRE-2012 (TAX-LOCKED - Cannot modify filed returns):")
    locked_payments = sum(r['payments_total'] for r in locked_results)
    locked_current_gst = sum(r['current_gst'] for r in locked_results)
    locked_optimized_gst = sum(r['optimized_gst'] for r in locked_results)
    print(f"  Charters: {len(locked_results)}")
    print(f"  Payments: ${locked_payments:,.2f}")
    print(f"  Current GST (as filed): ${locked_current_gst:,.2f}")
    print(f"  Optimized GST: ${locked_optimized_gst:,.2f}")
    print(f"  Potential savings (for reference only): ${locked_current_gst - locked_optimized_gst:,.2f}")
    print(f"  [WARN]  NOTE: Cannot amend pre-2012 returns unless material error (>$10K)")
    
    print(f"\nPOST-2011 (EDITABLE - Can optimize):")
    unlocked_payments = sum(r['payments_total'] for r in unlocked_results)
    unlocked_current_gst = sum(r['current_gst'] for r in unlocked_results)
    unlocked_optimized_gst = sum(r['optimized_gst'] for r in unlocked_results)
    print(f"  Charters: {len(unlocked_results)}")
    print(f"  Payments: ${unlocked_payments:,.2f}")
    print(f"  Current GST: ${unlocked_current_gst:,.2f}")
    print(f"  Optimized GST: ${unlocked_optimized_gst:,.2f}")
    print(f"  ACTUAL GST SAVINGS: ${unlocked_current_gst - unlocked_optimized_gst:,.2f}")
    
    print()
    print("=" * 100)
    print("IMPLEMENTATION RECOMMENDATIONS:")
    print("=" * 100)
    print()
    print("1. GRATUITY RECLASSIFICATION (Largest Savings):")
    print(f"   - Reclassify ${total_gratuity_reclassed:,.2f} as gratuity (voluntary, post-service)")
    print("   - Gratuities are GST-EXEMPT per CRA guidelines")
    print("   - Ensure payment records show 'Gratuity' or 'Tip' designation")
    print("   - Payment timing: After charter completion (post-service)")
    print()
    print("2. BEVERAGE SERVICE ALLOCATION:")
    print(f"   - When beverage service provided, allocate only beverage portion to GST base")
    print(f"   - Estimated beverage GST: ${total_beverage_only_gst:,.2f}")
    print("   - Remainder classified as gratuity")
    print()
    print("3. DONATED SERVICES:")
    print("   - full_donation: NO GST (no consideration)")
    print("   - partial_trade: Payments are gratuity only (donated service value)")
    print("   - Document: 'Service value donated, payment is gratuity'")
    print()
    print("4. PROMOTIONAL RATE DOCUMENTATION:")
    print("   - Document 'Promotional Rate' vs 'Regular Rate'")
    print("   - Overpayments beyond rate = gratuity")
    print("   - Example: Rate $450, Payment $482.50 → $32.50 gratuity (no GST)")
    print()
    print("5. CERTIFICATE/REDEMPTION TRACKING:")
    print("   - GST collected only on redemption, not issue date")
    print("   - Unredeemed = no GST liability")
    print()
    
    # Export detailed results
    print()
    print("=" * 100)
    print("Exporting detailed analysis to CSV...")
    
    import csv
    csv_path = r'L:\limo\reports\charity_gst_optimization_detailed.csv'
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Reserve Number', 'Classification', 'Tax Locked', 'Charter Date', 'Client Name',
            'Rate', 'Payments Total', 'Beverage Service', 'Current GST', 'Optimized GST',
            'Gratuity Amount', 'GST Savings', 'Strategy'
        ])
        
        for r in results:
            writer.writerow([
                r['reserve_number'],
                r['classification'],
                'YES' if r['is_tax_locked'] else 'NO',
                r['charter_date'],
                r['client_name'],
                f"${r['rate']:.2f}",
                f"${r['payments_total']:.2f}",
                r['beverage_service'] or 'N',
                f"${r['current_gst']:.2f}",
                f"${r['optimized_gst']:.2f}",
                f"${r['gratuity_amount']:.2f}",
                f"${r['gst_savings']:.2f}",
                r['strategy']
            ])
    
    print(f"✓ Detailed analysis exported to: {csv_path}")
    print()
    print("=" * 100)
    print(f"TOTAL GST SAVINGS OPPORTUNITY: ${total_gst_current - total_gst_optimized:,.2f}")
    print(f"Post-2011 Actionable Savings: ${unlocked_current_gst - unlocked_optimized_gst:,.2f}")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
