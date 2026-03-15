#!/usr/bin/env python3
"""
Analyze Arrow Limousine homepage content against GSC performance data
to identify optimization opportunities.

Created: 2025-10-31
"""

import json
from datetime import datetime

def analyze_homepage_content():
    """Analyze current homepage content structure and SEO elements."""
    
    print("=" * 80)
    print("ARROW LIMOUSINE HOMEPAGE CONTENT ANALYSIS")
    print("Current Date:", datetime.now().strftime("%Y-%m-%d"))
    print("=" * 80)
    print()
    
    # Current homepage analysis
    print("### CURRENT HOMEPAGE STRUCTURE ###")
    print()
    
    homepage_elements = {
        "Company Names": [
            "Arrow Limousine & Sedan Services Ltd",
            "Red Deer Party Bus"
        ],
        "Primary Phone": "(403)-346-0034",
        "Service Categories Listed": [
            "Sedan services",
            "Black Car Services", 
            "Corporate transportation",
            "Stretch Limousine Service",
            "SUV Limousine Service",
            "Private Shuttle style Limousine Bus Service",
            "Airport transfer services (YYC, YEG, YQF)",
            "Wedding services",
            "Party bus rental"
        ],
        "Geographic Coverage": [
            "Red Deer (based)",
            "Central Alberta",
            "Calgary",
            "Edmonton",
            "Sylvan lake",
            "Blackfalds",
            "Eckville",
            "Penhold",
            "Innisfail",
            "Stettler",
            "Lacombe",
            "Bentley",
            "Camrose",
            "Ponoka",
            "Wetaskiwin"
        ],
        "Trust Signals": [
            "In business since 1985 (40 years!)",
            "Largest fleet",
            "Excellent rates",
            "Trusted drivers"
        ],
        "Fleet Sizes Listed": [
            "4 Passengers (Executive Sedans)",
            "4 Passengers (Luxury Sedans)",
            "6 Passengers (Luxury SUV)",
            "4-6 Passengers (Stretch Limousines)",
            "13 Passengers (SUV Stretch Limousines)",
            "14 Passengers",
            "18 Passengers (Shuttle Style Limo Bus)",
            "20 Passengers (Vegas style party bus)",
            "20 Passengers (Luxury party bus with washroom)",
            "27 Passengers (ExtremeVegas Style Party Bus)"
        ]
    }
    
    for key, value in homepage_elements.items():
        print(f"\n{key}:")
        if isinstance(value, list):
            for item in value:
                print(f"  - {item}")
        else:
            print(f"  {value}")
    
    print("\n" + "=" * 80)
    print("### GSC PERFORMANCE DATA (Homepage) ###")
    print("=" * 80)
    print()
    
    gsc_homepage_stats = {
        "Impressions": 47293,
        "Clicks": 529,
        "CTR": "1.12%",
        "Average Position": 12.5,
        "Trend": "DOWN 15% in last period"
    }
    
    print("Current Performance:")
    for key, value in gsc_homepage_stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 80)
    print("### CRITICAL SEO ISSUES IDENTIFIED ###")
    print("=" * 80)
    print()
    
    issues = [
        {
            "issue": "Missing Geographic Focus in Title/Headers",
            "severity": "CRITICAL",
            "impact": "Homepage CTR 1.12% vs target 3-5%",
            "evidence": "Most clicks are 'arrow limousine' (91 clicks) but position is 12.5 avg",
            "fix": "Add 'Red Deer' to primary heading and meta title"
        },
        {
            "issue": "Airport Service Buried in Content",
            "severity": "HIGH", 
            "impact": "Airport keywords getting impressions but near 0 clicks",
            "evidence": "GSC shows airport-related queries but minimal clicks",
            "fix": "Move airport transfer service to top 3 services listed"
        },
        {
            "issue": "Calgary/Edmonton Positioning Unclear",
            "severity": "HIGH",
            "impact": "Users may think you serve local Calgary/Edmonton (you don't)",
            "evidence": "Content lists 'Calgary, Edmonton' without clarifying point-to-point only",
            "fix": "Clarify: 'Calgary Airport (YYC) Shuttle' and 'Edmonton Airport (YEG) Transfer'"
        },
        {
            "issue": "Since 1985 Buried Mid-Page",
            "severity": "MEDIUM",
            "impact": "Trust signal not visible in search snippets or above fold",
            "evidence": "Appears in paragraph 6, not in title or first paragraph",
            "fix": "Add 'Family Owned Since 1985' to company name or first line"
        },
        {
            "issue": "No Schema Markup Visible",
            "severity": "HIGH",
            "impact": "Google can't display rich results (stars, pricing, fleet)",
            "evidence": "No LocalBusiness schema apparent in content",
            "fix": "Add LocalBusiness + Service schema markup"
        },
        {
            "issue": "Multiple Company Names Confusing",
            "severity": "MEDIUM",
            "impact": "Brand consistency and search visibility diluted",
            "evidence": "Arrow Limousine, Red Deer Party Bus, RedDeerpartybus.ca, etc.",
            "fix": "Primary brand should be dominant, others as DBA"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue['issue']}")
        print(f"   Severity: {issue['severity']}")
        print(f"   Impact: {issue['impact']}")
        print(f"   Evidence: {issue['evidence']}")
        print(f"   Fix: {issue['fix']}")
    
    print("\n" + "=" * 80)
    print("### OPTIMIZATION RECOMMENDATIONS ###")
    print("=" * 80)
    print()
    
    recommendations = [
        {
            "priority": "IMMEDIATE",
            "action": "Update Meta Title",
            "current": "Arrow Limousine & Sedan Services Ltd and Red Deer Party Bus",
            "optimized": "Red Deer Limousine & Party Bus | Calgary Airport Shuttle | Arrow Limo Since 1985",
            "expected_impact": "+50-100 clicks/month from improved CTR"
        },
        {
            "priority": "IMMEDIATE", 
            "action": "Update Meta Description",
            "current": "Likely auto-generated from first paragraph",
            "optimized": "Red Deer's trusted limo service since 1985. Party bus rentals, Calgary Airport (YYC) shuttle, Edmonton transfers. 20+ vehicles, 4-27 passengers. Book 403-346-0034",
            "expected_impact": "+100-150 clicks/month from improved relevance"
        },
        {
            "priority": "HIGH",
            "action": "Restructure First Paragraph",
            "current": "Long paragraph listing all services without hierarchy",
            "optimized": "Lead with: 'Red Deer's premier limousine service since 1985. Specializing in Calgary Airport (YYC) shuttle service, party bus rentals, and corporate transportation throughout Alberta.'",
            "expected_impact": "Better user engagement, improved bounce rate"
        },
        {
            "priority": "HIGH",
            "action": "Add Schema Markup",
            "current": "No structured data visible",
            "optimized": "LocalBusiness schema with: address, phone, hours, priceRange, serviceArea, aggregateRating",
            "expected_impact": "Rich results eligibility, enhanced SERP appearance"
        },
        {
            "priority": "MEDIUM",
            "action": "Simplify Geographic Coverage Section",
            "current": "Long list of towns without context",
            "optimized": "Map showing '160km service radius from Red Deer' + key routes (YYC, YEG airports)",
            "expected_impact": "Clearer service area understanding"
        }
    ]
    
    for rec in recommendations:
        print(f"\n[{rec['priority']}] {rec['action']}")
        print(f"  Current: {rec['current']}")
        print(f"  Optimized: {rec['optimized']}")
        print(f"  Expected Impact: {rec['expected_impact']}")
    
    print("\n" + "=" * 80)
    print("### CONTENT GAPS vs GSC QUERY DATA ###")
    print("=" * 80)
    print()
    
    query_gaps = [
        {
            "query_theme": "Calgary Airport Shuttle",
            "gsc_impressions": "300+ impressions",
            "current_clicks": "Near 0",
            "homepage_mentions": "Buried in bullet point 'Airport transfer services'",
            "gap": "No dedicated section, unclear it's a primary service",
            "action": "Create prominent 'Calgary Airport (YYC) Shuttle Service' section with pricing"
        },
        {
            "query_theme": "Party Bus Red Deer",
            "gsc_impressions": "High volume",
            "current_clicks": "Page exists but declining 17%",
            "homepage_mentions": "Good - appears in company name and services",
            "gap": "Page content may need refresh (check /party-bus-red-deer)",
            "action": "Update party bus page meta description to match search intent"
        },
        {
            "query_theme": "Limousine [generic]",
            "gsc_impressions": "899 impressions",
            "current_clicks": "0 clicks",
            "homepage_mentions": "Multiple times but not optimized for generic search",
            "gap": "Content too local-specific, missing 'what is a limousine service' content",
            "action": "Add educational content: 'What to expect from professional limo service'"
        },
        {
            "query_theme": "Red Deer Weddings",
            "gsc_impressions": "Moderate",
            "current_clicks": "Good", 
            "homepage_mentions": "Listed in services but not elaborated",
            "gap": "No wedding-specific content on homepage",
            "action": "Add 'Wedding Transportation' section with testimonial or image"
        }
    ]
    
    print("\nQuery Themes vs Homepage Content:")
    for gap in query_gaps:
        print(f"\n  {gap['query_theme']}:")
        print(f"    GSC Impressions: {gap['gsc_impressions']}")
        print(f"    Current Clicks: {gap['current_clicks']}")
        print(f"    Homepage Mentions: {gap['homepage_mentions']}")
        print(f"    Gap: {gap['gap']}")
        print(f"    Action: {gap['action']}")
    
    print("\n" + "=" * 80)
    print("### COMPETITIVE INTELLIGENCE INSIGHTS ###")
    print("=" * 80)
    print()
    
    print("\nStrengths to Emphasize:")
    strengths = [
        "Since 1985 (40 years) - ONLY company with this longevity",
        "Largest fleet in region (2-27 passengers)",
        "Family owned (2-person operation = personalized service)",
        "Provincial carrier license (160km+ service radius)",
        "24/7 reservations (competitive advantage)",
        "Non-refundable retainers can be transferred (unique policy)"
    ]
    for strength in strengths:
        print(f"  ✓ {strength}")
    
    print("\n" + "=" * 80)
    print("### QUICK WINS (Implement This Week) ###")
    print("=" * 80)
    print()
    
    quick_wins = [
        {
            "task": "Update homepage meta title and description",
            "time": "15 minutes",
            "difficulty": "Easy (Wix SEO settings)",
            "impact": "High - improves CTR immediately"
        },
        {
            "task": "Move 'Since 1985' to company name/first line",
            "time": "10 minutes", 
            "difficulty": "Easy (text edit)",
            "impact": "Medium - adds trust signal above fold"
        },
        {
            "task": "Add 'Calgary Airport (YYC) Shuttle' as separate service item",
            "time": "5 minutes",
            "difficulty": "Easy (add bullet point)",
            "impact": "High - clarifies primary service"
        },
        {
            "task": "Change 'Calgary, Edmonton' to 'Calgary Airport, Edmonton Airport'",
            "time": "5 minutes",
            "difficulty": "Easy (text edit)",
            "impact": "High - prevents confusion about service area"
        },
        {
            "task": "Add phone number to meta description",
            "time": "5 minutes",
            "difficulty": "Easy (Wix SEO settings)",
            "impact": "Medium - click-to-call in mobile SERPs"
        }
    ]
    
    total_time = sum(int(qw['time'].split()[0]) for qw in quick_wins)
    
    print(f"\nTotal Implementation Time: ~{total_time} minutes")
    print("\nQuick Win Checklist:")
    for i, qw in enumerate(quick_wins, 1):
        print(f"\n  {i}. {qw['task']}")
        print(f"     Time: {qw['time']} | Difficulty: {qw['difficulty']}")
        print(f"     Impact: {qw['impact']}")
    
    print("\n" + "=" * 80)
    print("### EXPECTED RESULTS ###")
    print("=" * 80)
    print()
    
    print("\nCurrent Performance:")
    print("  Homepage: 47,293 impressions → 529 clicks (1.12% CTR)")
    print("  All pages: 118,772 impressions → 712 clicks (0.60% CTR)")
    
    print("\n30-Day Projections (Conservative):")
    print("  With optimized meta title/description:")
    print("    Homepage: 47,293 impressions → 1,419 clicks (3% CTR)")
    print("    Increase: +890 clicks/month (+168%)")
    print()
    print("  With all quick wins implemented:")
    print("    All pages: 118,772 impressions → 2,375 clicks (2% CTR)")
    print("    Increase: +1,663 clicks/month (+234%)")
    
    print("\n90-Day Projections (With ongoing optimization):")
    print("  Homepage: 47,293 impressions → 2,365 clicks (5% CTR)")
    print("  All pages: 118,772 impressions → 4,751 clicks (4% CTR)")
    print("  Increase: +4,039 clicks/month (+567%)")
    
    print("\n" + "=" * 80)
    print("### NEXT STEPS ###")
    print("=" * 80)
    print()
    
    print("\nPhase 1: Quick Wins (This Week)")
    print("  [ ] Update homepage meta title")
    print("  [ ] Update homepage meta description")
    print("  [ ] Move 'Since 1985' to top")
    print("  [ ] Clarify airport shuttle services")
    print("  [ ] Add phone to meta description")
    
    print("\nPhase 2: Content Enhancement (Next 2 Weeks)")
    print("  [ ] Create dedicated Calgary Airport shuttle page")
    print("  [ ] Fix 0-click pages (stretch-limousine, new-years-eve, bachelor-bachelorette)")
    print("  [ ] Add schema markup (LocalBusiness)")
    print("  [ ] Add customer testimonials with schema")
    print("  [ ] Create service area map (160km radius)")
    
    print("\nPhase 3: Backlink Campaign (Ongoing)")
    print("  [ ] Contact 5 existing wedding vendor links for reciprocal links")
    print("  [ ] Apply for Red Deer Chamber of Commerce directory")
    print("  [ ] Contact Hockey Alberta about sports transportation") 
    print("  [ ] Get listed on YYC/YEG airport ground transportation directories")
    print("  [ ] Partner with Red Deer hotels for guest transportation")
    
    print("\n" + "=" * 80)
    print("\nAnalysis complete! Ready to implement optimizations.")
    print("=" * 80)

if __name__ == "__main__":
    analyze_homepage_content()
