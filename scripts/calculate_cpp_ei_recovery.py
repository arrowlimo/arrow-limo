#!/usr/bin/env python3
"""
Calculate CPP/EI overpayments on gratuities and generate correction filing.

Since gratuities should be treated as direct tips (no employer CPP/EI required),
we can recover years of overpaid employer contributions through CRA adjustments.
"""

import sys
import os
import psycopg2
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def get_cpp_ei_rates_by_year():
    """Get historical CPP/EI rates for overpayment calculations."""
    
    rates = {
        2025: {'cpp_rate': 0.0595, 'ei_rate': 0.0229, 'ei_multiplier': 1.4},  # Estimated
        2024: {'cpp_rate': 0.0595, 'ei_rate': 0.0229, 'ei_multiplier': 1.4},
        2023: {'cpp_rate': 0.0595, 'ei_rate': 0.0229, 'ei_multiplier': 1.4},
        2022: {'cpp_rate': 0.0564, 'ei_rate': 0.0229, 'ei_multiplier': 1.4},
        2021: {'cpp_rate': 0.0545, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2020: {'cpp_rate': 0.0525, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2019: {'cpp_rate': 0.0525, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2018: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2017: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2016: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2015: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2014: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},
        2013: {'cpp_rate': 0.0495, 'ei_rate': 0.0188, 'ei_multiplier': 1.4},  # From user's data
        2012: {'cpp_rate': 0.0495, 'ei_rate': 0.0173, 'ei_multiplier': 1.4},
        2011: {'cpp_rate': 0.0495, 'ei_rate': 0.0178, 'ei_multiplier': 1.4},
        2010: {'cpp_rate': 0.0495, 'ei_rate': 0.0173, 'ei_multiplier': 1.4},
    }
    
    return rates

def calculate_gratuity_overpayments_by_year():
    """Calculate CPP/EI overpayments on gratuities by year."""
    
    print("CPP/EI OVERPAYMENT CALCULATION ON GRATUITIES")
    print("=" * 60)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get gratuities by year from charters
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM charter_date) as year,
                COUNT(*) as charters_with_tips,
                SUM(driver_gratuity) as total_gratuities
            FROM charters 
            WHERE driver_gratuity > 0 
                AND charter_date >= '2010-01-01'
            GROUP BY EXTRACT(YEAR FROM charter_date)
            ORDER BY year DESC
        """)
        
        yearly_gratuities = cur.fetchall()
        
        cur.close()
        conn.close()
        
        rates = get_cpp_ei_rates_by_year()
        total_overpayment = Decimal('0')
        overpayment_details = []
        
        print("YEAR-BY-YEAR OVERPAYMENT ANALYSIS:")
        print("=" * 60)
        
        for year_data in yearly_gratuities:
            year = int(year_data[0])
            charters = year_data[1]
            gratuities = Decimal(str(year_data[2]))
            
            if year in rates:
                year_rates = rates[year]
                cpp_rate = Decimal(str(year_rates['cpp_rate']))
                ei_rate = Decimal(str(year_rates['ei_rate'])) * Decimal(str(year_rates['ei_multiplier']))
                
                # Calculate employer overpayments
                cpp_overpaid = gratuities * cpp_rate
                ei_overpaid = gratuities * ei_rate
                total_year_overpaid = cpp_overpaid + ei_overpaid
                
                overpayment_details.append({
                    'year': year,
                    'gratuities': gratuities,
                    'cpp_overpaid': cpp_overpaid,
                    'ei_overpaid': ei_overpaid,
                    'total_overpaid': total_year_overpaid,
                    'charters': charters
                })
                
                total_overpayment += total_year_overpaid
                
                print(f"{year}:")
                print(f"  Gratuities Subject to CPP/EI:   ${gratuities:,.2f}")
                print(f"  CPP Overpaid ({cpp_rate:.2%}):        ${cpp_overpaid:,.2f}")
                print(f"  EI Overpaid ({ei_rate:.3%}):         ${ei_overpaid:,.2f}")
                print(f"  Total Year Overpayment:         ${total_year_overpaid:,.2f}")
                print(f"  Charters with Tips:             {charters:,}")
                print()
        
        print("OVERPAYMENT SUMMARY:")
        print("=" * 30)
        print(f"Total CPP/EI Overpaid:           ${total_overpayment:,.2f}")
        print(f"Years Affected:                  {len(overpayment_details)}")
        print(f"Total Gratuity Charters:         {sum(d['charters'] for d in overpayment_details):,}")
        
        return {
            'total_overpayment': total_overpayment,
            'yearly_details': overpayment_details,
            'recoverable': True
        }
        
    except Exception as e:
        print(f"Error calculating overpayments: {e}")
        return None

def generate_cra_adjustment_requests(overpayment_data):
    """Generate CRA adjustment request documentation."""
    
    print("\nCRA ADJUSTMENT REQUEST PREPARATION")
    print("=" * 50)
    
    if not overpayment_data:
        return None
    
    yearly_details = overpayment_data['yearly_details']
    total_recovery = overpayment_data['total_overpayment']
    
    # Group by time periods for filing
    recent_years = [d for d in yearly_details if d['year'] >= 2021]  # Last 4 years
    older_years = [d for d in yearly_details if d['year'] < 2021]    # Older years
    
    recent_recovery = sum(d['total_overpaid'] for d in recent_years)
    older_recovery = sum(d['total_overpaid'] for d in older_years)
    
    print("ADJUSTMENT REQUEST STRATEGY:")
    print("=" * 30)
    print(f"Recent Years (2021+):            ${recent_recovery:,.2f}")
    print(f"Older Years (2010-2020):         ${older_recovery:,.2f}")
    print(f"Total Recovery Potential:        ${total_recovery:,.2f}")
    
    print(f"\nFILING APPROACH:")
    print("1. **Form T4A-RCA** (Request for CPP/EI Adjustment)")
    print("2. **Supporting Documentation**: Gratuity reclassification as direct tips")
    print("3. **Period Coverage**: Multi-year adjustments allowed")
    print("4. **Interest**: CRA may pay interest on overpayments")
    
    # Generate specific adjustment requests
    print(f"\nRECOMMENDED ADJUSTMENT REQUESTS:")
    
    for detail in yearly_details[:5]:  # Show top 5 years
        year = detail['year']
        total_overpaid = detail['total_overpaid']
        gratuities = detail['gratuities']
        
        print(f"\n{year} Adjustment Request:")
        print(f"  - Reclassify ${gratuities:,.2f} in gratuities as direct tips")
        print(f"  - Recover ${detail['cpp_overpaid']:,.2f} in CPP overpayment")
        print(f"  - Recover ${detail['ei_overpaid']:,.2f} in EI overpayment")
        print(f"  - Total recovery: ${total_overpaid:,.2f}")
    
    if len(yearly_details) > 5:
        remaining_recovery = sum(d['total_overpaid'] for d in yearly_details[5:])
        print(f"\n+ {len(yearly_details) - 5} additional years: ${remaining_recovery:,.2f}")
    
    return {
        'total_recovery': total_recovery,
        'adjustment_years': len(yearly_details),
        'filing_ready': True
    }

def generate_payroll_adjustment_summary():
    """Generate summary for payroll system adjustments."""
    
    print("\nPAYROLL SYSTEM ADJUSTMENT REQUIREMENTS")
    print("=" * 50)
    
    print("IMMEDIATE PAYROLL CHANGES NEEDED:")
    print("1. **Stop CPP/EI withholding** on gratuities going forward")
    print("2. **Reclassify gratuities** as 'direct tips' in payroll system")
    print("3. **Issue T4A slips** to drivers for tip income (personal tax)")
    print("4. **Adjust remittance calculations** to exclude tips")
    
    print(f"\nDRIVER NOTIFICATION REQUIREMENTS:")
    print("- Inform drivers that tips are now treated as direct income")
    print("- Drivers must declare tips on personal returns (Line 10400)")
    print("- No more CPP/EI deductions on tip portions")
    print("- Company no longer pays employer portions on tips")
    
    print(f"\nONGOING COMPLIANCE:")
    print("- Invoice templates show gratuities as customer-added")
    print("- Payroll system separates wages from tips")
    print("- Annual T4A reporting for drivers' tip income")
    print("- Regular audits to ensure continued compliance")

def main():
    """Main function to calculate and process CPP/EI corrections."""
    
    print("CPP/EI OVERPAYMENT RECOVERY SYSTEM")
    print("=" * 60)
    print("Calculating recoverable CPP/EI overpayments on gratuities")
    print("that should have been treated as direct tips.\n")
    
    # Calculate overpayments
    overpayment_data = calculate_gratuity_overpayments_by_year()
    
    if overpayment_data:
        # Generate CRA adjustment requests
        adjustment_info = generate_cra_adjustment_requests(overpayment_data)
        
        # Generate payroll adjustment requirements
        generate_payroll_adjustment_summary()
        
        print(f"\n🎯 CPP/EI RECOVERY OPPORTUNITY!")
        print(f"Total Recoverable: ${overpayment_data['total_overpayment']:,.2f}")
        print(f"Years Affected: {len(overpayment_data['yearly_details'])}")
        
        print(f"\n📋 NEXT STEPS:")
        print("1. File CRA Form T4A-RCA for CPP/EI adjustments")
        print("2. Submit supporting documentation (gratuity reclassification)")
        print("3. Adjust payroll system for future compliance")
        print("4. Notify drivers of tip income reporting requirements")
        
        # Calculate combined savings (CPP/EI recovery + GST savings)
        annual_gst_savings = Decimal('87200.39')  # From previous calculation
        if overpayment_data['yearly_details']:
            recent_annual_avg = sum(d['total_overpaid'] for d in overpayment_data['yearly_details'][:3]) / 3
            print(f"\nCOMBINED ANNUAL SAVINGS:")
            print(f"GST Savings (ongoing):           ${annual_gst_savings:,.2f}")
            print(f"CPP/EI Recovery (one-time):      ${overpayment_data['total_overpayment']:,.2f}")
            print(f"Future CPP/EI Savings (annual):  ${recent_annual_avg:,.2f}")

if __name__ == "__main__":
    main()