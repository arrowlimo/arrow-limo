#!/usr/bin/env python3
"""
HOMEPAGE CONTENT STRUCTURE ANALYZER
===================================

Detailed analysis of Arrow Limousine homepage content organization:
- Who Are We section
- What We Offer section  
- Quick Access links and navigation
- Visual elements and pictures for user direction
"""

import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import json

class HomepageContentAnalyzer:
    """Analyze specific homepage content structure and organization."""
    
    def __init__(self, url: str = "https://arrowlimousine.ca"):
        """Initialize with website URL."""
        self.url = url
        self.soup = None
        self.raw_html = ""
        
    def fetch_and_parse_homepage(self) -> bool:
        """Fetch homepage and parse content."""
        
        try:
            print(f"🔍 FETCHING HOMEPAGE CONTENT: {self.url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                self.raw_html = response.text
                self.soup = BeautifulSoup(self.raw_html, 'html.parser')
                print("[OK] Homepage content loaded successfully")
                return True
            else:
                print(f"[FAIL] Failed to load homepage: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[FAIL] Error fetching homepage: {str(e)}")
            return False
    
    def analyze_who_we_are_section(self) -> dict:
        """Analyze 'Who Are We' content section."""
        
        who_we_are_analysis = {
            'section_found': False,
            'content_elements': [],
            'key_messages': [],
            'company_identity': {},
            'trust_indicators': [],
            'missing_elements': []
        }
        
        if not self.soup:
            return who_we_are_analysis
        
        # Look for "Who We Are" or "About" content patterns
        about_patterns = [
            'who we are', 'about us', 'about arrow', 'our company', 
            'our story', 'company profile', 'established', 'years of experience',
            'professional', 'trusted', 'reliable'
        ]
        
        # Find sections that might contain "who we are" content
        text_content = self.soup.get_text().lower()
        
        for pattern in about_patterns:
            if pattern in text_content:
                who_we_are_analysis['section_found'] = True
                who_we_are_analysis['content_elements'].append(pattern)
        
        # Look for company identity elements
        identity_indicators = {
            'years_in_business': re.search(r'(\d+)\s*years?\s*(of\s*)?(experience|business|service)', text_content),
            'professional_mention': 'professional' in text_content,
            'licensed_insured': any(term in text_content for term in ['licensed', 'insured', 'insurance']),
            'fleet_size': re.search(r'(\d+)\s*(vehicles?|cars?|limos?|limousines?)', text_content),
            'service_area': any(area in text_content for area in ['saskatchewan', 'saskatoon', 'regina', 'red deer']),
            'company_values': any(value in text_content for value in ['luxury', 'premium', 'reliable', 'professional', 'safe'])
        }
        
        who_we_are_analysis['company_identity'] = identity_indicators
        
        # Extract key trust indicators
        trust_elements = []
        if identity_indicators['years_in_business']:
            trust_elements.append(f"Years in business mentioned: {identity_indicators['years_in_business'].group()}")
        if identity_indicators['licensed_insured']:
            trust_elements.append("Licensed and insured mentioned")
        if identity_indicators['fleet_size']:
            trust_elements.append(f"Fleet information: {identity_indicators['fleet_size'].group()}")
        
        who_we_are_analysis['trust_indicators'] = trust_elements
        
        return who_we_are_analysis
    
    def analyze_what_we_offer_section(self) -> dict:
        """Analyze 'What We Offer' services content."""
        
        services_analysis = {
            'services_section_found': False,
            'services_identified': [],
            'service_descriptions': {},
            'pricing_info': {},
            'call_to_actions': [],
            'visual_elements': []
        }
        
        if not self.soup:
            return services_analysis
        
        text_content = self.soup.get_text().lower()
        
        # Core services to look for
        expected_services = {
            'airport_transportation': ['airport', 'transfer', 'pickup', 'drop-off', 'flight'],
            'wedding_transportation': ['wedding', 'bride', 'bridal', 'ceremony', 'reception'],
            'corporate_transportation': ['corporate', 'business', 'executive', 'meeting', 'conference'],
            'party_bus': ['party bus', 'group', 'celebration', 'event'],
            'limousine_service': ['limousine', 'limo', 'luxury', 'stretch'],
            'special_events': ['special event', 'prom', 'graduation', 'anniversary', 'night out']
        }
        
        # Check which services are mentioned
        for service_type, keywords in expected_services.items():
            for keyword in keywords:
                if keyword in text_content:
                    if service_type not in services_analysis['services_identified']:
                        services_analysis['services_identified'].append(service_type)
                        services_analysis['services_section_found'] = True
        
        # Look for pricing indicators
        pricing_patterns = [
            'starting at', 'from $', 'price', 'rate', 'cost', 'quote', 'estimate', 'affordable'
        ]
        
        pricing_found = []
        for pattern in pricing_patterns:
            if pattern in text_content:
                pricing_found.append(pattern)
        
        services_analysis['pricing_info'] = {
            'pricing_mentioned': len(pricing_found) > 0,
            'pricing_terms_found': pricing_found
        }
        
        # Look for call-to-action elements
        cta_patterns = [
            'book now', 'reserve now', 'get quote', 'call now', 'contact us', 
            'request quote', 'book online', 'schedule', 'reserve'
        ]
        
        cta_found = []
        for pattern in cta_patterns:
            if pattern in text_content:
                cta_found.append(pattern)
        
        services_analysis['call_to_actions'] = cta_found
        
        return services_analysis
    
    def analyze_quick_access_navigation(self) -> dict:
        """Analyze quick access links and navigation structure."""
        
        navigation_analysis = {
            'main_menu_found': False,
            'menu_items': [],
            'quick_access_links': [],
            'contact_accessibility': {},
            'booking_access': {},
            'navigation_structure': {}
        }
        
        if not self.soup:
            return navigation_analysis
        
        # Find navigation elements
        nav_elements = self.soup.find_all(['nav', 'menu', 'ul'])
        
        menu_items = []
        for nav in nav_elements:
            links = nav.find_all('a')
            for link in links:
                link_text = link.get_text().strip()
                link_href = link.get('href', '')
                if link_text and len(link_text) < 50:  # Reasonable menu item length
                    menu_items.append({
                        'text': link_text,
                        'href': link_href,
                        'is_service_related': any(service in link_text.lower() for service in 
                                                ['service', 'limo', 'wedding', 'airport', 'corporate', 'party'])
                    })
        
        navigation_analysis['main_menu_found'] = len(menu_items) > 0
        navigation_analysis['menu_items'] = menu_items[:15]  # Limit to first 15 items
        
        # Look for quick access elements
        quick_access_indicators = ['phone', 'call', 'email', 'contact', 'book', 'quote', 'emergency']
        
        # Find contact information accessibility
        text_content = self.soup.get_text()
        
        # Phone number patterns
        phone_pattern = r'(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
        phones_found = re.findall(phone_pattern, text_content)
        
        # Email patterns  
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails_found = re.findall(email_pattern, text_content)
        
        navigation_analysis['contact_accessibility'] = {
            'phone_numbers_found': len(phones_found),
            'email_addresses_found': len(emails_found),
            'contact_prominent': 'contact' in text_content.lower()[:1000]  # In first 1000 chars
        }
        
        return navigation_analysis
    
    def analyze_visual_direction_elements(self) -> dict:
        """Analyze pictures and visual elements for user direction."""
        
        visual_analysis = {
            'images_found': 0,
            'image_categories': {},
            'alt_text_analysis': {},
            'visual_cues': [],
            'hero_image': {},
            'service_visuals': []
        }
        
        if not self.soup:
            return visual_analysis
        
        # Find all images
        images = self.soup.find_all('img')
        visual_analysis['images_found'] = len(images)
        
        # Categorize images by alt text and src
        image_categories = {
            'vehicles': 0,
            'services': 0,
            'staff': 0,
            'locations': 0,
            'decorative': 0
        }
        
        alt_texts = []
        src_analysis = []
        
        for img in images:
            alt_text = img.get('alt', '').lower()
            src = img.get('src', '').lower()
            
            alt_texts.append(alt_text)
            src_analysis.append(src)
            
            # Categorize images
            if any(vehicle in alt_text or vehicle in src for vehicle in ['limo', 'car', 'vehicle', 'bus', 'sedan']):
                image_categories['vehicles'] += 1
            elif any(service in alt_text or service in src for service in ['wedding', 'airport', 'corporate', 'party']):
                image_categories['services'] += 1
            elif any(staff in alt_text or staff in src for staff in ['driver', 'chauffeur', 'staff', 'team']):
                image_categories['staff'] += 1
            elif any(location in alt_text or location in src for location in ['building', 'office', 'city']):
                image_categories['locations'] += 1
            else:
                image_categories['decorative'] += 1
        
        visual_analysis['image_categories'] = image_categories
        visual_analysis['alt_text_analysis'] = {
            'total_alt_texts': len([alt for alt in alt_texts if alt]),
            'missing_alt_texts': len([alt for alt in alt_texts if not alt]),
            'alt_text_quality': 'good' if len([alt for alt in alt_texts if alt and len(alt) > 10]) > len(images) * 0.7 else 'needs_improvement'
        }
        
        return visual_analysis
    
    def generate_content_structure_report(self) -> dict:
        """Generate comprehensive content structure analysis."""
        
        if not self.fetch_and_parse_homepage():
            return {'error': 'Could not fetch homepage content'}
        
        print("\n📊 ANALYZING HOMEPAGE CONTENT STRUCTURE")
        print("=" * 40)
        
        # Analyze each section
        who_we_are = self.analyze_who_we_are_section()
        what_we_offer = self.analyze_what_we_offer_section()
        navigation = self.analyze_quick_access_navigation()
        visuals = self.analyze_visual_direction_elements()
        
        # Compile comprehensive report
        report = {
            'timestamp': datetime.now().isoformat(),
            'url_analyzed': self.url,
            'content_structure': {
                'who_we_are_section': who_we_are,
                'what_we_offer_section': what_we_offer,
                'quick_access_navigation': navigation,
                'visual_direction_elements': visuals
            },
            'overall_assessment': self._generate_overall_assessment(who_we_are, what_we_offer, navigation, visuals),
            'improvement_recommendations': self._generate_content_recommendations(who_we_are, what_we_offer, navigation, visuals)
        }
        
        return report
    
    def _generate_overall_assessment(self, who_we_are, what_we_offer, navigation, visuals) -> dict:
        """Generate overall content structure assessment."""
        
        assessment = {
            'structure_score': 0,
            'strengths': [],
            'weaknesses': [],
            'user_experience_rating': 'unknown'
        }
        
        # Score each section (0-25 points each, total 100)
        scores = {
            'who_we_are': 0,
            'what_we_offer': 0, 
            'navigation': 0,
            'visuals': 0
        }
        
        # Who We Are scoring
        if who_we_are['section_found']:
            scores['who_we_are'] += 10
        if who_we_are['trust_indicators']:
            scores['who_we_are'] += 10
        if who_we_are['company_identity']['professional_mention']:
            scores['who_we_are'] += 5
        
        # What We Offer scoring
        if what_we_offer['services_section_found']:
            scores['what_we_offer'] += 10
        if len(what_we_offer['services_identified']) >= 4:
            scores['what_we_offer'] += 10
        if what_we_offer['call_to_actions']:
            scores['what_we_offer'] += 5
        
        # Navigation scoring
        if navigation['main_menu_found']:
            scores['navigation'] += 10
        if navigation['contact_accessibility']['phone_numbers_found'] > 0:
            scores['navigation'] += 10
        if len(navigation['menu_items']) >= 5:
            scores['navigation'] += 5
        
        # Visuals scoring
        if visuals['images_found'] > 5:
            scores['visuals'] += 10
        if visuals['image_categories']['vehicles'] > 0:
            scores['visuals'] += 10
        if visuals['alt_text_analysis']['alt_text_quality'] == 'good':
            scores['visuals'] += 5
        
        total_score = sum(scores.values())
        assessment['structure_score'] = total_score
        assessment['section_scores'] = scores
        
        # Determine rating
        if total_score >= 80:
            assessment['user_experience_rating'] = 'excellent'
        elif total_score >= 60:
            assessment['user_experience_rating'] = 'good'
        elif total_score >= 40:
            assessment['user_experience_rating'] = 'fair'
        else:
            assessment['user_experience_rating'] = 'needs_improvement'
        
        return assessment
    
    def _generate_content_recommendations(self, who_we_are, what_we_offer, navigation, visuals) -> list:
        """Generate specific content improvement recommendations."""
        
        recommendations = []
        
        # Who We Are recommendations
        if not who_we_are['section_found']:
            recommendations.append("🏢 ADD: Clear 'Who We Are' section explaining company history and values")
        
        if not who_we_are['trust_indicators']:
            recommendations.append("🛡️ ADD: Trust indicators (years in business, certifications, insurance info)")
        
        # What We Offer recommendations  
        if len(what_we_offer['services_identified']) < 4:
            recommendations.append("📋 EXPAND: Service offerings section - add missing service types")
        
        if not what_we_offer['pricing_info']['pricing_mentioned']:
            recommendations.append("💰 ADD: Pricing information or 'Get Quote' options for services")
        
        if len(what_we_offer['call_to_actions']) < 3:
            recommendations.append("🎯 ADD: More call-to-action buttons throughout services section")
        
        # Navigation recommendations
        if navigation['contact_accessibility']['phone_numbers_found'] == 0:
            recommendations.append("📞 FIX: Make phone number more prominent in navigation")
        
        if len(navigation['menu_items']) < 5:
            recommendations.append("🧭 EXPAND: Navigation menu with clear service and vehicle page links")
        
        # Visual recommendations
        if visuals['image_categories']['vehicles'] < 3:
            recommendations.append("🚗 ADD: More high-quality vehicle photos for visual direction")
        
        if visuals['alt_text_analysis']['alt_text_quality'] == 'needs_improvement':
            recommendations.append("🖼️ IMPROVE: Image alt text for better accessibility and SEO")
        
        return recommendations
    
    def save_content_analysis(self, output_dir: str) -> dict:
        """Save comprehensive content analysis report."""
        
        import os
        
        # Generate analysis
        report = self.generate_content_structure_report()
        
        if 'error' in report:
            return report
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save detailed JSON report
        report_path = os.path.join(output_dir, 'homepage_content_analysis.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Create readable summary
        summary_path = os.path.join(output_dir, 'content_structure_summary.md')
        self._create_content_summary(report, summary_path)
        
        return {
            'report_path': report_path,
            'summary_path': summary_path,
            'analysis': report
        }
    
    def _create_content_summary(self, report: dict, summary_path: str):
        """Create readable content structure summary."""
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("# Arrow Limousine Homepage Content Structure Analysis\n\n")
            f.write(f"*Analysis Date: {report['timestamp']}*\n\n")
            
            content = report['content_structure']
            assessment = report['overall_assessment']
            
            # Overall Score
            f.write(f"## 📊 Overall Content Structure Score: {assessment['structure_score']}/100\n")
            f.write(f"**User Experience Rating: {assessment['user_experience_rating'].upper()}**\n\n")
            
            # Section Scores
            f.write("### Section Breakdown:\n")
            for section, score in assessment['section_scores'].items():
                f.write(f"- **{section.replace('_', ' ').title()}**: {score}/25\n")
            f.write("\n")
            
            # Who We Are Analysis
            who_we_are = content['who_we_are_section']
            f.write("## 🏢 'Who We Are' Section Analysis\n\n")
            f.write(f"**Section Found**: {'[OK] Yes' if who_we_are['section_found'] else '[FAIL] No'}\n\n")
            
            if who_we_are['trust_indicators']:
                f.write("**Trust Indicators Found**:\n")
                for indicator in who_we_are['trust_indicators']:
                    f.write(f"- {indicator}\n")
                f.write("\n")
            
            # What We Offer Analysis
            what_we_offer = content['what_we_offer_section']
            f.write("## 📋 'What We Offer' Section Analysis\n\n")
            f.write(f"**Services Section Found**: {'[OK] Yes' if what_we_offer['services_section_found'] else '[FAIL] No'}\n\n")
            
            if what_we_offer['services_identified']:
                f.write("**Services Identified**:\n")
                for service in what_we_offer['services_identified']:
                    f.write(f"- {service.replace('_', ' ').title()}\n")
                f.write("\n")
            
            if what_we_offer['call_to_actions']:
                f.write("**Call-to-Actions Found**:\n")
                for cta in what_we_offer['call_to_actions']:
                    f.write(f"- {cta}\n")
                f.write("\n")
            
            # Navigation Analysis
            navigation = content['quick_access_navigation']
            f.write("## 🧭 Quick Access & Navigation Analysis\n\n")
            f.write(f"**Main Menu Found**: {'[OK] Yes' if navigation['main_menu_found'] else '[FAIL] No'}\n")
            f.write(f"**Menu Items Count**: {len(navigation['menu_items'])}\n")
            f.write(f"**Phone Numbers Found**: {navigation['contact_accessibility']['phone_numbers_found']}\n")
            f.write(f"**Email Addresses Found**: {navigation['contact_accessibility']['email_addresses_found']}\n\n")
            
            # Visual Elements Analysis
            visuals = content['visual_direction_elements']
            f.write("## 🖼️ Visual Direction Elements Analysis\n\n")
            f.write(f"**Total Images**: {visuals['images_found']}\n\n")
            
            f.write("**Image Categories**:\n")
            for category, count in visuals['image_categories'].items():
                f.write(f"- {category.replace('_', ' ').title()}: {count}\n")
            f.write("\n")
            
            # Recommendations
            recommendations = report['improvement_recommendations']
            if recommendations:
                f.write("## 💡 Priority Recommendations\n\n")
                for rec in recommendations:
                    f.write(f"{rec}\n\n")


def main():
    """Main function to analyze homepage content structure."""
    
    print("🎯 HOMEPAGE CONTENT STRUCTURE ANALYZER")
    print("=" * 38)
    print("Analyzing: Who Are We | What We Offer | Quick Access | Visual Direction")
    print()
    
    # Initialize analyzer
    analyzer = HomepageContentAnalyzer()
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"L:/limo/homepage_analysis/{timestamp}"
    
    print(f"📁 Saving analysis to: {output_dir}")
    
    # Generate and save analysis
    results = analyzer.save_content_analysis(output_dir)
    
    if 'error' in results:
        print(f"[FAIL] Analysis failed: {results['error']}")
        return
    
    analysis = results['analysis']
    assessment = analysis['overall_assessment']
    
    print(f"\n[OK] HOMEPAGE CONTENT ANALYSIS COMPLETE")
    print(f"📄 Files created:")
    print(f"   • homepage_content_analysis.json (detailed data)")
    print(f"   • content_structure_summary.md (readable report)")
    
    print(f"\n📊 CONTENT STRUCTURE SCORE: {assessment['structure_score']}/100")
    print(f"🎯 User Experience Rating: {assessment['user_experience_rating'].upper()}")
    
    print(f"\n📋 SECTION ANALYSIS:")
    for section, score in assessment['section_scores'].items():
        emoji = "[OK]" if score >= 20 else "[WARN]" if score >= 15 else "[FAIL]"
        print(f"   {emoji} {section.replace('_', ' ').title()}: {score}/25")
    
    # Show key findings
    content = analysis['content_structure']
    
    print(f"\n🔍 KEY FINDINGS:")
    
    # Who We Are
    who_we_are = content['who_we_are_section']
    print(f"   🏢 Who We Are Section: {'[OK] Found' if who_we_are['section_found'] else '[FAIL] Missing'}")
    
    # What We Offer
    what_we_offer = content['what_we_offer_section']
    print(f"   📋 Services Identified: {len(what_we_offer['services_identified'])} types")
    print(f"   🎯 Call-to-Actions: {len(what_we_offer['call_to_actions'])} found")
    
    # Navigation
    navigation = content['quick_access_navigation']
    print(f"   📞 Contact Access: {navigation['contact_accessibility']['phone_numbers_found']} phone numbers")
    print(f"   🧭 Menu Items: {len(navigation['menu_items'])} navigation links")
    
    # Visuals
    visuals = content['visual_direction_elements']
    print(f"   🖼️ Visual Elements: {visuals['images_found']} images total")
    print(f"   🚗 Vehicle Photos: {visuals['image_categories']['vehicles']} vehicle images")
    
    # Top recommendations
    recommendations = analysis['improvement_recommendations']
    if recommendations:
        print(f"\n💡 TOP RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"   {i}. {rec}")
    
    return results


if __name__ == "__main__":
    main()