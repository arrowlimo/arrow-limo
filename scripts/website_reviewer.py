#!/usr/bin/env python3
"""
ARROW LIMOUSINE WEBSITE REVIEWER
===============================

Comprehensive website analysis and review tool.
Analyzes site structure, content, SEO, and user experience.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
import re

class WebsiteReviewer:
    """Analyze and review Arrow Limousine website."""
    
    def __init__(self, base_url: str = "https://arrowlimousine.ca"):
        """Initialize with website URL."""
        self.base_url = base_url.rstrip('/')
        self.pages_analyzed = []
        self.issues_found = []
        self.recommendations = []
        
    def analyze_homepage(self) -> Dict:
        """Analyze the homepage structure and content."""
        
        homepage_analysis = {
            'url': self.base_url,
            'accessibility': {},
            'content_structure': {},
            'seo_elements': {},
            'user_experience': {},
            'mobile_optimization': {},
            'loading_performance': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            print(f"🔍 ANALYZING HOMEPAGE: {self.base_url}")
            
            # Attempt to fetch homepage
            response = requests.get(self.base_url, timeout=10, headers={
                'User-Agent': 'Arrow Limousine Website Analyzer/1.0'
            })
            
            if response.status_code == 200:
                html_content = response.text
                homepage_analysis = self._analyze_html_content(html_content, homepage_analysis)
                
            else:
                homepage_analysis['issues'].append({
                    'type': 'accessibility',
                    'severity': 'error',
                    'message': f'Cannot access homepage: HTTP {response.status_code}'
                })
                
        except requests.exceptions.RequestException as e:
            homepage_analysis['issues'].append({
                'type': 'connectivity',
                'severity': 'error',
                'message': f'Connection error: {str(e)}'
            })
        
        return homepage_analysis
    
    def _analyze_html_content(self, html: str, analysis: Dict) -> Dict:
        """Analyze HTML content for structure and SEO."""
        
        # Basic HTML structure analysis
        analysis['content_structure'] = {
            'has_header': '<header' in html.lower() or '<nav' in html.lower(),
            'has_main_content': '<main' in html.lower() or 'main-content' in html.lower(),
            'has_footer': '<footer' in html.lower(),
            'has_navigation': '<nav' in html.lower() or 'navigation' in html.lower(),
            'estimated_word_count': len(html.split())
        }
        
        # SEO elements analysis
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        description_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        
        analysis['seo_elements'] = {
            'title': title_match.group(1).strip() if title_match else None,
            'meta_description': description_match.group(1).strip() if description_match else None,
            'has_h1': '<h1' in html.lower(),
            'h1_count': html.lower().count('<h1'),
            'has_alt_tags': 'alt=' in html.lower(),
            'images_without_alt': html.lower().count('<img') - html.lower().count('alt=')
        }
        
        # Look for business-specific content
        limousine_keywords = [
            'limousine', 'luxury transportation', 'chauffeur', 'airport transfer',
            'wedding transportation', 'corporate transportation', 'saskatchewan'
        ]
        
        keyword_found = {}
        for keyword in limousine_keywords:
            keyword_found[keyword] = keyword.lower() in html.lower()
        
        analysis['content_structure']['business_keywords'] = keyword_found
        
        # Check for contact information
        phone_pattern = r'(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        analysis['content_structure']['contact_info'] = {
            'has_phone': bool(re.search(phone_pattern, html)),
            'has_email': bool(re.search(email_pattern, html)),
            'phone_numbers_found': len(re.findall(phone_pattern, html)),
            'email_addresses_found': len(re.findall(email_pattern, html))
        }
        
        return analysis
    
    def analyze_site_structure(self) -> Dict:
        """Analyze overall site structure based on your description."""
        
        # Based on user description: "one page for each service, one page for each vehicle type, one page for specific information"
        expected_structure = {
            'service_pages': [
                'Airport Transportation',
                'Wedding Transportation', 
                'Corporate Transportation',
                'Special Events Transportation'
            ],
            'vehicle_pages': [
                'Stretch Limousines',
                'Executive Sedans',
                'SUV Limousines',
                'Luxury Vehicles'
            ],
            'information_pages': [
                'About Us',
                'Contact',
                'Booking',
                'Pricing',
                'Service Area'
            ]
        }
        
        structure_analysis = {
            'expected_pages': expected_structure,
            'design_philosophy': 'Single page per service/vehicle for clarity',
            'user_experience_goals': [
                'Easy navigation',
                'Clear service separation',
                'Focused vehicle information',
                'Dedicated information sections'
            ],
            'recommendations': self._generate_structure_recommendations(expected_structure)
        }
        
        return structure_analysis
    
    def _generate_structure_recommendations(self, structure: Dict) -> List[str]:
        """Generate recommendations for site structure."""
        
        recommendations = [
            "Ensure each service page has clear call-to-action buttons",
            "Include pricing information or 'Get Quote' forms on service pages",
            "Add high-quality photos to each vehicle type page",
            "Include vehicle specifications and capacity on vehicle pages",
            "Create clear navigation between related services and vehicles",
            "Add customer testimonials specific to each service type",
            "Include booking forms on relevant service and vehicle pages",
            "Ensure mobile-responsive design for all page types",
            "Add local SEO elements to each page (Saskatchewan keywords)",
            "Include contact information in footer of every page"
        ]
        
        return recommendations
    
    def review_homepage_best_practices(self) -> Dict:
        """Review homepage against limousine business best practices."""
        
        best_practices = {
            'hero_section': {
                'recommended_elements': [
                    'Compelling headline about luxury transportation',
                    'High-quality hero image of premium vehicle',
                    'Clear call-to-action button ("Book Now", "Get Quote")',
                    'Service area mention (Saskatchewan)',
                    'Key value propositions (24/7, Professional, Luxury)'
                ],
                'common_mistakes': [
                    'Generic stock photos',
                    'Unclear value proposition', 
                    'Missing call-to-action',
                    'No mention of service area',
                    'Overcomplicated messaging'
                ]
            },
            'services_preview': {
                'recommended_elements': [
                    'Clear service categories with icons',
                    'Brief descriptions for each service',
                    'Links to dedicated service pages',
                    'Pricing hints or "Starting at" information',
                    'Professional service photos'
                ]
            },
            'trust_indicators': {
                'recommended_elements': [
                    'Years in business',
                    'Professional certifications',
                    'Insurance and licensing mentions',
                    'Customer testimonials',
                    'Fleet size or vehicle count',
                    'Professional chauffeur information'
                ]
            },
            'contact_accessibility': {
                'recommended_elements': [
                    '24/7 phone number prominently displayed',
                    'Online booking form or link',
                    'Service area clearly stated',
                    'Emergency contact information',
                    'Multiple contact methods (phone, email, form)'
                ]
            }
        }
        
        return best_practices
    
    def generate_homepage_checklist(self) -> Dict:
        """Generate comprehensive homepage review checklist."""
        
        checklist = {
            'essential_elements': {
                'above_the_fold': [
                    '☐ Business name clearly visible',
                    '☐ Compelling headline about luxury transportation services',
                    '☐ High-quality hero image of limousine/luxury vehicle',
                    '☐ Clear call-to-action button (Book Now/Get Quote)',
                    '☐ Phone number prominently displayed',
                    '☐ Service area mentioned (Saskatchewan)'
                ],
                'services_section': [
                    '☐ Clear service categories displayed',
                    '☐ Service icons or images for each category',
                    '☐ Brief descriptions for each service',
                    '☐ Links to individual service pages',
                    '☐ Pricing information or "Get Quote" options'
                ],
                'vehicle_showcase': [
                    '☐ Fleet preview with vehicle types',
                    '☐ High-quality vehicle photos',
                    '☐ Vehicle capacity information',
                    '☐ Links to detailed vehicle pages',
                    '☐ Premium/luxury positioning emphasized'
                ],
                'trust_building': [
                    '☐ Years in business highlighted',
                    '☐ Professional certifications displayed',
                    '☐ Customer testimonials featured',
                    '☐ Safety and insurance mentions',
                    '☐ Professional chauffeur information'
                ],
                'contact_information': [
                    '☐ 24/7 phone number in header/footer',
                    '☐ Email address accessible',
                    '☐ Physical location or service area',
                    '☐ Online booking form or link',
                    '☐ Emergency contact information'
                ]
            },
            'seo_optimization': [
                '☐ Page title includes "Limousine Service Saskatchewan"',
                '☐ Meta description mentions key services and location',
                '☐ H1 tag with primary keyword phrase',
                '☐ Alt tags on all images',
                '☐ Local business schema markup',
                '☐ Loading speed optimized',
                '☐ Mobile-responsive design'
            ],
            'user_experience': [
                '☐ Easy navigation to service pages',
                '☐ Clear path to vehicle information',
                '☐ Quick access to booking/contact',
                '☐ Consistent branding throughout',
                '☐ Professional color scheme and fonts',
                '☐ Fast loading times',
                '☐ Mobile-friendly interface'
            ]
        }
        
        return checklist
    
    def save_review_report(self, output_dir: str) -> Dict:
        """Generate and save comprehensive website review report."""
        
        print("📊 GENERATING COMPREHENSIVE WEBSITE REVIEW")
        print("=" * 42)
        
        # Analyze homepage
        homepage_analysis = self.analyze_homepage()
        
        # Analyze site structure  
        structure_analysis = self.analyze_site_structure()
        
        # Get best practices
        best_practices = self.review_homepage_best_practices()
        
        # Generate checklist
        checklist = self.generate_homepage_checklist()
        
        # Compile full report
        full_report = {
            'timestamp': datetime.now().isoformat(),
            'website_url': self.base_url,
            'analysis_type': 'Comprehensive Homepage & Structure Review',
            'homepage_analysis': homepage_analysis,
            'site_structure': structure_analysis,
            'best_practices': best_practices,
            'review_checklist': checklist,
            'overall_recommendations': self._generate_overall_recommendations()
        }
        
        # Save report
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        report_path = os.path.join(output_dir, 'website_review_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, indent=2, default=str)
        
        # Create readable summary
        summary_path = os.path.join(output_dir, 'homepage_review_summary.md')
        self._create_markdown_summary(full_report, summary_path)
        
        return {
            'report_path': report_path,
            'summary_path': summary_path,
            'analysis': full_report
        }
    
    def _generate_overall_recommendations(self) -> List[str]:
        """Generate overall recommendations for the website."""
        
        return [
            "🎯 HOMEPAGE OPTIMIZATION",
            "• Ensure hero section immediately communicates luxury transportation value",
            "• Add prominent '24/7 Service Available' messaging",
            "• Include 'Serving Saskatchewan' in hero section",
            "",
            "🚗 SERVICE PAGE STRATEGY", 
            "• Create separate landing pages for each service type",
            "• Include service-specific pricing and booking forms",
            "• Add customer testimonials relevant to each service",
            "",
            "🏆 VEHICLE SHOWCASE",
            "• Feature high-quality photos of your actual fleet",
            "• Include vehicle specifications and passenger capacity",
            "• Add luxury amenities and features for each vehicle type",
            "",
            "📱 USER EXPERIENCE",
            "• Implement clear navigation between service and vehicle pages",
            "• Add quick booking/quote request forms on every page",
            "• Ensure mobile optimization for on-the-go bookings",
            "",
            "🔍 SEO & LOCAL SEARCH",
            "• Optimize each page for local Saskatchewan keywords",
            "• Add location-specific landing pages if serving multiple cities",
            "• Implement Google My Business integration",
            "",
            "💼 TRUST & CREDIBILITY",
            "• Display professional certifications and insurance info",
            "• Add driver/chauffeur qualifications and training info",
            "• Include years in business and company history"
        ]
    
    def _create_markdown_summary(self, report: Dict, summary_path: str):
        """Create readable markdown summary."""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("# Arrow Limousine Website Review Summary\n\n")
            f.write(f"*Analysis Date: {report['timestamp']}*\n\n")
            
            # Homepage Analysis Results
            homepage = report.get('homepage_analysis', {})
            
            if 'issues' in homepage and homepage['issues']:
                f.write("## 🚨 Critical Issues Found\n\n")
                for issue in homepage['issues']:
                    f.write(f"- **{issue['severity'].upper()}**: {issue['message']}\n")
                f.write("\n")
            
            # SEO Elements
            seo = homepage.get('seo_elements', {})
            if seo:
                f.write("## 🔍 SEO Analysis\n\n")
                f.write(f"- **Page Title**: {seo.get('title', 'Not found')}\n")
                f.write(f"- **Meta Description**: {seo.get('meta_description', 'Not found')}\n")
                f.write(f"- **H1 Tags**: {seo.get('h1_count', 0)} found\n")
                f.write(f"- **Images without Alt Tags**: {seo.get('images_without_alt', 0)}\n\n")
            
            # Site Structure Recommendations
            structure = report.get('site_structure', {})
            if 'recommendations' in structure:
                f.write("## 📋 Site Structure Recommendations\n\n")
                for rec in structure['recommendations'][:10]:  # Show first 10
                    f.write(f"- {rec}\n")
                f.write("\n")
            
            # Overall Recommendations
            overall_recs = report.get('overall_recommendations', [])
            if overall_recs:
                f.write("## 💡 Priority Improvements\n\n")
                for rec in overall_recs:
                    f.write(f"{rec}\n")
                f.write("\n")


def main():
    """Main function to run website review."""
    
    print("🎯 ARROW LIMOUSINE WEBSITE REVIEWER")
    print("=" * 35)
    print("Comprehensive homepage and site structure analysis")
    print()
    
    # Initialize reviewer
    reviewer = WebsiteReviewer()
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"L:/limo/website_review/{timestamp}"
    
    print(f"📁 Generating review in: {output_dir}")
    
    # Generate comprehensive review
    results = reviewer.save_review_report(output_dir)
    
    analysis = results['analysis']
    
    print(f"\n[OK] WEBSITE REVIEW COMPLETE")
    print(f"📄 Files created:")
    print(f"   • website_review_report.json (detailed analysis)")
    print(f"   • homepage_review_summary.md (readable format)")
    
    # Display key findings
    homepage = analysis.get('homepage_analysis', {})
    
    if 'issues' in homepage and homepage['issues']:
        print(f"\n🚨 CRITICAL ISSUES FOUND: {len(homepage['issues'])}")
        for issue in homepage['issues']:
            print(f"   • {issue['message']}")
    else:
        print(f"\n[OK] HOMEPAGE ACCESSIBLE")
    
    # Show SEO status
    seo = homepage.get('seo_elements', {})
    if seo:
        print(f"\n🔍 SEO STATUS:")
        print(f"   • Title: {'[OK]' if seo.get('title') else '[FAIL]'} {seo.get('title', 'Missing')}")
        print(f"   • Description: {'[OK]' if seo.get('meta_description') else '[FAIL]'} {seo.get('meta_description', 'Missing')}")
        print(f"   • H1 Tags: {seo.get('h1_count', 0)}")
    
    # Show structure analysis
    structure = analysis.get('site_structure', {})
    expected = structure.get('expected_pages', {})
    
    print(f"\n📊 EXPECTED SITE STRUCTURE:")
    print(f"   • Service Pages: {len(expected.get('service_pages', []))}")
    print(f"   • Vehicle Pages: {len(expected.get('vehicle_pages', []))}")  
    print(f"   • Information Pages: {len(expected.get('information_pages', []))}")
    
    print(f"\n🎯 REVIEW CHECKLIST CREATED:")
    checklist = analysis.get('review_checklist', {})
    essential = checklist.get('essential_elements', {})
    
    total_items = sum(len(items) for items in essential.values())
    print(f"   • Essential Elements: {total_items} items to check")
    print(f"   • SEO Optimization: {len(checklist.get('seo_optimization', []))} items")
    print(f"   • User Experience: {len(checklist.get('user_experience', []))} items")
    
    print(f"\n💡 TOP RECOMMENDATIONS:")
    overall_recs = analysis.get('overall_recommendations', [])
    for rec in overall_recs[:6]:  # Show first 6
        if rec.startswith('🎯') or rec.startswith('🚗') or rec.startswith('🏆'):
            print(f"   {rec}")
    
    print(f"\n📖 NEXT STEPS:")
    print(f"   1. Read: {results['summary_path']}")
    print(f"   2. Review homepage checklist items")
    print(f"   3. Verify each service page exists and is optimized")
    print(f"   4. Check vehicle pages have proper content")
    print(f"   5. Implement SEO recommendations")
    
    return results


if __name__ == "__main__":
    main()