#!/usr/bin/env python
"""
Compare schema_comparison JSON with almsdata_current_state JSON
to identify what changed during reconciliation.
"""
import json
import os
from collections import defaultdict

def load_json(filename):
    """Load JSON file from reports directory"""
    filepath = rf"L:\limo\reports\{filename}"
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found")
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)

def analyze_schema_structure():
    """Analyze what tables exist and their fields"""
    schema = load_json('schema_comparison_2025-12-26.json')
    
    if not schema:
        return None
    
    print("\n" + "="*70)
    print("SCHEMA ANALYSIS")
    print("="*70)
    
    # Identify charter/payment/charge tables
    mdb_tables = {}
    pg_tables = {}
    
    for table_name, table_data in schema['tables'].items():
        if table_data.get('in_mdb'):
            key_word = None
            if any(w in table_name.lower() for w in ['reserve', 'charter', 'order']):
                key_word = 'charter'
            elif 'payment' in table_name.lower():
                key_word = 'payment'
            elif any(w in table_name.lower() for w in ['charge', 'invoice']):
                key_word = 'charge'
            
            if key_word:
                mdb_tables[table_name] = key_word
        
        if table_data.get('in_pg'):
            key_word = None
            if any(w in table_name.lower() for w in ['charter', 'reserve']):
                key_word = 'charter'
            elif 'payment' in table_name.lower():
                key_word = 'payment'
            elif 'charge' in table_name.lower():
                key_word = 'charge'
            
            if key_word:
                pg_tables[table_name] = key_word
    
    print("\nMDB TABLES:")
    for table, category in sorted(mdb_tables.items()):
        print(f"  [{category.upper()}] {table}")
    
    print("\nPOSTGRESQL TABLES (sample):")
    for table, category in sorted(pg_tables.items())[:30]:
        print(f"  [{category.upper()}] {table}")
    
    return mdb_tables, pg_tables

def analyze_current_state():
    """Analyze the current state JSON"""
    almsdata = load_json('almsdata_current_state.json')
    
    if not almsdata:
        return None
    
    print("\n" + "="*70)
    print("ALMSDATA CURRENT STATE ANALYSIS")
    print("="*70)
    
    stats = almsdata.get('statistics', {})
    
    print(f"\n📊 Statistics:")
    print(f"  Charters extracted: {stats.get('charters_count', 0)}")
    print(f"  Payment groups: {stats.get('payment_groups_count', 0)}")
    print(f"  Charge groups: {stats.get('charge_groups_count', 0)}")
    
    # Analyze charter balances
    charters = almsdata.get('charters', {})
    print(f"\n📋 Charter Analysis ({len(charters)} total):")
    
    zero_balance = sum(1 for c in charters.values() if c.get('balance', 0) == 0)
    with_gratuity = sum(1 for c in charters.values() if c.get('driver_gratuity', 0) > 0)
    with_payments = sum(1 for c in charters.values() if c.get('total_amount_due', 0) > 0)
    
    print(f"  Charters with $0 balance: {zero_balance} ({zero_balance/len(charters)*100:.1f}%)")
    print(f"  Charters with gratuity: {with_gratuity} ({with_gratuity/len(charters)*100:.1f}%)")
    print(f"  Charters with amount due: {with_payments} ({with_payments/len(charters)*100:.1f}%)")
    
    # Analyze payments
    payments = almsdata.get('payments', {})
    total_payments = sum(len(v) for v in payments.values())
    total_paid = sum(sum(p.get('amount', 0) for p in v) for v in payments.values())
    
    print(f"\n💳 Payment Analysis:")
    print(f"  Payment entries: {total_payments}")
    print(f"  Unique reserves with payments: {len(payments)}")
    print(f"  Total paid amount: ${total_paid:,.2f}")
    
    # Analyze charges
    charges = almsdata.get('charges', {})
    total_charges = sum(len(v) for v in charges.values())
    total_charge_amount = sum(sum(c.get('amount', 0) for c in v) for v in charges.values())
    
    print(f"\n💰 Charge Analysis:")
    print(f"  Charge entries: {total_charges}")
    print(f"  Unique reserves with charges: {len(charges)}")
    print(f"  Total charge amount: ${total_charge_amount:,.2f}")
    
    # Show sample charter with all components
    print(f"\n📌 SAMPLE CHARTER WITH FULL DETAILS:")
    for reserve_num, charter in list(charters.items())[:1]:
        print(f"\n  Reserve: {charter['reserve_number']}")
        print(f"  Charter ID: {charter['charter_id']}")
        print(f"  Date: {charter['charter_date']}")
        print(f"  Balance: ${charter['balance']:.2f}")
        print(f"  Total Due: ${charter['total_amount_due']:.2f}")
        print(f"  Driver Paid: ${charter['driver_paid']:.2f}")
        print(f"  Driver Gratuity: ${charter['driver_gratuity']:.2f}")
        
        # Show payments for this reserve
        if reserve_num in payments:
            print(f"\n  Payments ({len(payments[reserve_num])}):")
            for p in payments[reserve_num][:3]:
                print(f"    - ${p['amount']:.2f} on {p['payment_date']} ({p['payment_method']})")
            if len(payments[reserve_num]) > 3:
                print(f"    ... and {len(payments[reserve_num]) - 3} more")
        
        # Show charges for this reserve
        if reserve_num in charges:
            print(f"\n  Charges ({len(charges[reserve_num])}):")
            for c in charges[reserve_num][:3]:
                print(f"    - ${c['amount']:.2f} {c.get('description', 'N/A')}")
            if len(charges[reserve_num]) > 3:
                print(f"    ... and {len(charges[reserve_num]) - 3} more")
    
    return almsdata

def generate_comparison_report():
    """Generate final comparison report"""
    almsdata = load_json('almsdata_current_state.json')
    
    if not almsdata:
        return
    
    print("\n" + "="*70)
    print("RECONCILIATION FINDINGS")
    print("="*70)
    
    charters = almsdata.get('charters', {})
    payments = almsdata.get('payments', {})
    charges = almsdata.get('charges', {})
    
    findings = {
        'timestamp': almsdata.get('timestamp'),
        'summary': {
            'total_charters': len(charters),
            'total_payment_entries': sum(len(v) for v in payments.values()),
            'total_charge_entries': sum(len(v) for v in charges.values()),
            'total_paid': sum(sum(p.get('amount', 0) for p in v) for v in payments.values()),
            'total_charged': sum(sum(c.get('amount', 0) for c in v) for v in charges.values())
        },
        'indicators': {
            'zero_balance_charters': sum(1 for c in charters.values() if c.get('balance', 0) == 0),
            'charters_with_gratuity': sum(1 for c in charters.values() if c.get('driver_gratuity', 0) > 0),
            'charters_fully_paid': sum(1 for c in charters.values() 
                                      if payments.get(str(c['reserve_number']), [])
                                      and sum(p['amount'] for p in payments.get(str(c['reserve_number']), [])) >= c['total_amount_due']),
            'reserves_with_both_payments_and_charges': sum(1 for r in charters.keys() 
                                                          if r in payments and r in charges)
        }
    }
    
    print("\n✓ Summary Statistics:")
    for key, value in findings['summary'].items():
        if 'total_' in key and key.endswith('_entries'):
            print(f"  {key}: {value:,}")
        elif 'total_' in key:
            print(f"  {key}: ${value:,.2f}")
        else:
            print(f"  {key}: {value:,}")
    
    print("\n✓ Reconciliation Indicators:")
    for key, value in findings['indicators'].items():
        pct = (value / findings['summary']['total_charters'] * 100) if findings['summary']['total_charters'] > 0 else 0
        print(f"  {key}: {value:,} ({pct:.1f}%)")
    
    print("\n📊 These indicators suggest:")
    
    if findings['indicators']['zero_balance_charters'] > findings['summary']['total_charters'] * 0.3:
        print("  ✓ Significant number of charters reconciled (high % at $0 balance)")
    
    if findings['indicators']['charters_with_gratuity'] > findings['summary']['total_charters'] * 0.05:
        print("  ✓ Gratuity field is being used (populated in ~" + 
              f"{findings['indicators']['charters_with_gratuity']/findings['summary']['total_charters']*100:.1f}% of charters)")
    
    if findings['indicators']['reserves_with_both_payments_and_charges'] > 0:
        print("  ✓ Payments and charges linked by reserve_number (confirmed: " + 
              f"{findings['indicators']['reserves_with_both_payments_and_charges']} reserves)")
    
    # Save report
    output_file = r"L:\limo\reports\comparison_findings.json"
    with open(output_file, 'w') as f:
        json.dump(findings, f, indent=2)
    
    print(f"\n✓ Report saved to {output_file}")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("COMPARING SCHEMA AND CURRENT STATE JSON FILES")
    print("="*70)
    
    # Analyze schema structure
    analyze_schema_structure()
    
    # Analyze current state
    analyze_current_state()
    
    # Generate comparison report
    generate_comparison_report()
    
    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print("="*70)
    print("\nFiles created:")
    print("  L:\\limo\\reports\\almsdata_current_state.json")
    print("  L:\\limo\\reports\\comparison_findings.json")
