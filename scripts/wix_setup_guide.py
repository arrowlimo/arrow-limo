#!/usr/bin/env python3
"""
WIX INTEGRATION SETUP GUIDE
===========================

Step-by-step guide to implement Wix API integration for Arrow Limousine.
This guide covers everything from authentication to full website management.
"""

import os
import json
from datetime import datetime

def create_wix_setup_guide():
    """Generate comprehensive setup instructions."""
    
    guide = {
        'title': 'Arrow Limousine Wix Integration Setup Guide',
        'last_updated': datetime.now().isoformat(),
        'sections': {}
    }
    
    # STEP 1: WIX API AUTHENTICATION
    guide['sections']['1_authentication'] = {
        'title': '🔑 STEP 1: Wix API Authentication Setup',
        'description': 'Set up proper Wix API credentials and authentication',
        'steps': [
            {
                'step': '1.1',
                'title': 'Access Wix Developer Dashboard',
                'instructions': [
                    'Go to https://dev.wix.com/',
                    'Log in with your Wix account (the one that owns arrowlimousine.ca)',
                    'Navigate to "My Apps" or "Dashboard"'
                ],
                'expected_result': 'You should see the Wix Developer dashboard'
            },
            {
                'step': '1.2', 
                'title': 'Create New Wix App',
                'instructions': [
                    'Click "Create New App"',
                    'Choose "Build an App for Your Site" or "Headless/Backend App"',
                    'Name it "Arrow Limousine Management System"',
                    'Select your Arrow Limousine site from the dropdown'
                ],
                'expected_result': 'New app created and connected to your site'
            },
            {
                'step': '1.3',
                'title': 'Configure API Permissions',
                'instructions': [
                    'In your app dashboard, go to "Permissions"',
                    'Enable these permissions:',
                    '  • Business Info: Read & Write',
                    '  • Bookings: Read & Write', 
                    '  • Site Content: Read & Write',
                    '  • Contacts/CRM: Read & Write',
                    '  • Events: Read',
                    'Save the permissions'
                ],
                'expected_result': 'API permissions configured for full site management'
            },
            {
                'step': '1.4',
                'title': 'Get API Keys',
                'instructions': [
                    'Go to "OAuth" or "API Keys" section',
                    'Copy your "App ID" and "App Secret"',
                    'Generate an "Access Token" for your site',
                    'Save these credentials securely'
                ],
                'expected_result': 'You have App ID, App Secret, and Access Token',
                'security_note': '[WARN] NEVER share these credentials publicly!'
            }
        ]
    }
    
    # STEP 2: ENVIRONMENT SETUP
    guide['sections']['2_environment'] = {
        'title': '💻 STEP 2: Development Environment Setup',
        'description': 'Configure your local environment for Wix integration',
        'steps': [
            {
                'step': '2.1',
                'title': 'Install Required Python Packages',
                'instructions': [
                    'Open PowerShell in your L:\\limo directory',
                    'Run: pip install requests python-dotenv',
                    'Verify installation: pip list | grep requests'
                ],
                'commands': [
                    'cd L:\\limo',
                    'pip install requests python-dotenv wixapi',
                    'pip list'
                ]
            },
            {
                'step': '2.2',
                'title': 'Create Environment Configuration',
                'instructions': [
                    'Create a .env file in L:\\limo\\',
                    'Add your Wix credentials to this file',
                    'Never commit this file to version control'
                ],
                'file_content': '''# Wix API Configuration
WIX_APP_ID=your-app-id-here
WIX_APP_SECRET=your-app-secret-here  
WIX_ACCESS_TOKEN=your-access-token-here
WIX_SITE_ID=your-site-id-here

# Optional: Wix webhook settings
WIX_WEBHOOK_SECRET=your-webhook-secret-here'''
            },
            {
                'step': '2.3',
                'title': 'Test API Connection',
                'instructions': [
                    'Run the connection test script',
                    'Verify you can connect to Wix APIs',
                    'Check that permissions are working'
                ],
                'test_command': 'python scripts/test_wix_connection.py'
            }
        ]
    }
    
    # STEP 3: BASIC IMPLEMENTATION
    guide['sections']['3_implementation'] = {
        'title': '🔧 STEP 3: Basic Wix Integration Implementation',
        'description': 'Implement core Wix functionality step by step',
        'steps': [
            {
                'step': '3.1',
                'title': 'Business Information Sync',
                'instructions': [
                    'Start with updating basic business info',
                    'Test reading current site information',
                    'Update contact details from your database'
                ],
                'script': 'scripts/wix_business_info_sync.py',
                'features': ['Read business info', 'Update contact details', 'Sync hours of operation']
            },
            {
                'step': '3.2',
                'title': 'Booking System Integration',
                'instructions': [
                    'Set up Wix Bookings service',
                    'Configure service types and pricing',
                    'Test booking creation and retrieval'
                ],
                'script': 'scripts/wix_bookings_integration.py',
                'features': ['Create services', 'Manage bookings', 'Sync to database']
            },
            {
                'step': '3.3',
                'title': 'Content Management',
                'instructions': [
                    'Update website content from templates',
                    'Manage service descriptions',
                    'Update pricing and availability'
                ],
                'script': 'scripts/wix_content_management.py',
                'features': ['Update page content', 'Manage SEO settings', 'Upload images']
            }
        ]
    }
    
    # STEP 4: ADVANCED FEATURES
    guide['sections']['4_advanced'] = {
        'title': '🚀 STEP 4: Advanced Integration Features',
        'description': 'Implement advanced automation and monitoring',
        'steps': [
            {
                'step': '4.1',
                'title': 'Automated Data Sync',
                'instructions': [
                    'Set up scheduled tasks for regular syncing',
                    'Sync customer data between systems',
                    'Update pricing based on database changes'
                ],
                'automation_schedule': {
                    'daily': ['Sync new bookings', 'Update availability'],
                    'weekly': ['Update service pricing', 'Sync customer reviews'],
                    'monthly': ['Content audit', 'SEO optimization']
                }
            },
            {
                'step': '4.2',
                'title': 'Webhook Integration', 
                'instructions': [
                    'Set up Wix webhooks for real-time updates',
                    'Handle booking notifications',
                    'Process payment confirmations'
                ],
                'webhook_events': [
                    'Booking created/updated/cancelled',
                    'Payment completed',
                    'Customer registered',
                    'Review submitted'
                ]
            },
            {
                'step': '4.3',
                'title': 'Error Monitoring & Reporting',
                'instructions': [
                    'Implement error tracking and alerts',
                    'Generate performance reports',
                    'Monitor SEO and site health'
                ],
                'monitoring_features': [
                    'API error logging',
                    'Performance metrics',
                    'SEO ranking tracking',
                    'Booking conversion rates'
                ]
            }
        ]
    }
    
    # STEP 5: SEO & GOOGLE INTEGRATION
    guide['sections']['5_seo_google'] = {
        'title': '🔍 STEP 5: SEO & Google Integration',
        'description': 'Optimize for search engines and integrate with Google services',
        'steps': [
            {
                'step': '5.1',
                'title': 'Upload SEO Files',
                'instructions': [
                    'Upload generated sitemap.xml to your Wix site',
                    'Upload robots.txt file',
                    'Implement structured data markup'
                ],
                'files_to_upload': [
                    'sitemap.xml → Site root directory',
                    'robots.txt → Site root directory', 
                    'structured_data.json → Page HTML head sections'
                ]
            },
            {
                'step': '5.2',
                'title': 'Google Search Console Setup',
                'instructions': [
                    'Add your site to Google Search Console',
                    'Verify ownership using HTML tag method',
                    'Submit your sitemap',
                    'Monitor indexing status'
                ],
                'google_tools': [
                    'Google Search Console',
                    'Google Analytics', 
                    'Google My Business',
                    'Google PageSpeed Insights'
                ]
            },
            {
                'step': '5.3',
                'title': 'Local SEO Optimization',
                'instructions': [
                    'Claim Google My Business listing',
                    'Optimize for local keywords',
                    'Build local citations and reviews'
                ],
                'local_seo_tasks': [
                    'Update GMB with correct business info',
                    'Add service area locations',
                    'Upload business photos',
                    'Collect and respond to reviews'
                ]
            }
        ]
    }
    
    # TROUBLESHOOTING
    guide['sections']['6_troubleshooting'] = {
        'title': '🔧 STEP 6: Common Issues & Troubleshooting',
        'description': 'Solutions for common problems and debugging',
        'common_issues': [
            {
                'problem': 'Authentication Errors (401/403)',
                'solutions': [
                    'Verify API credentials are correct',
                    'Check that access token has not expired',
                    'Ensure proper permissions are enabled',
                    'Regenerate access token if needed'
                ]
            },
            {
                'problem': 'API Rate Limiting (429)',
                'solutions': [
                    'Implement request throttling',
                    'Add retry logic with exponential backoff',
                    'Cache API responses when possible',
                    'Optimize API call frequency'
                ]
            },
            {
                'problem': 'Data Sync Issues',
                'solutions': [
                    'Check data format compatibility',
                    'Validate required fields are present',
                    'Implement error logging and recovery',
                    'Use database transactions for consistency'
                ]
            }
        ]
    }
    
    return guide

def save_setup_guide():
    """Save the complete setup guide."""
    
    guide = create_wix_setup_guide()
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"L:/limo/wix_setup/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save main guide
    guide_path = os.path.join(output_dir, 'WIX_INTEGRATION_SETUP_GUIDE.json')
    with open(guide_path, 'w', encoding='utf-8') as f:
        json.dump(guide, f, indent=2, ensure_ascii=False)
    
    # Create markdown version for easy reading
    md_path = os.path.join(output_dir, 'WIX_SETUP_GUIDE.md')
    create_markdown_guide(guide, md_path)
    
    # Create .env template
    env_template_path = os.path.join(output_dir, 'env_template.txt')
    with open(env_template_path, 'w') as f:
        f.write("""# Wix API Configuration Template
# Copy this to L:/limo/.env and fill in your actual values

WIX_APP_ID=your-app-id-here
WIX_APP_SECRET=your-app-secret-here  
WIX_ACCESS_TOKEN=your-access-token-here
WIX_SITE_ID=your-site-id-here

# Optional: Wix webhook settings
WIX_WEBHOOK_SECRET=your-webhook-secret-here

# Database settings (already configured)
DB_HOST=localhost
DB_NAME=almsdata
DB_USER=postgres
DB_PASSWORD=***REDACTED***
""")
    
    return {
        'guide_path': guide_path,
        'markdown_path': md_path,
        'env_template': env_template_path,
        'output_dir': output_dir
    }

def create_markdown_guide(guide, md_path):
    """Create a readable markdown version of the guide."""
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# {guide['title']}\n\n")
        f.write(f"*Last Updated: {guide['last_updated']}*\n\n")
        
        f.write("## 📋 Quick Overview\n\n")
        f.write("This guide will help you implement Wix API integration for Arrow Limousine in 6 steps:\n\n")
        f.write("1. **Authentication** - Set up Wix API credentials\n")
        f.write("2. **Environment** - Configure your development setup\n")
        f.write("3. **Implementation** - Build core integration features\n")
        f.write("4. **Advanced Features** - Add automation and monitoring\n")
        f.write("5. **SEO & Google** - Optimize for search engines\n")
        f.write("6. **Troubleshooting** - Fix common issues\n\n")
        
        for section_key, section in guide['sections'].items():
            f.write(f"## {section['title']}\n\n")
            f.write(f"{section['description']}\n\n")
            
            if 'steps' in section:
                for step in section['steps']:
                    f.write(f"### {step['step']} {step['title']}\n\n")
                    
                    for instruction in step['instructions']:
                        f.write(f"- {instruction}\n")
                    f.write("\n")
                    
                    if 'commands' in step:
                        f.write("**Commands to run:**\n```bash\n")
                        for cmd in step['commands']:
                            f.write(f"{cmd}\n")
                        f.write("```\n\n")
                    
                    if 'file_content' in step:
                        f.write("**File content:**\n```env\n")
                        f.write(step['file_content'])
                        f.write("\n```\n\n")
                    
                    if 'expected_result' in step:
                        f.write(f"**Expected Result:** {step['expected_result']}\n\n")
            
            if 'common_issues' in section:
                f.write("### Common Problems & Solutions\n\n")
                for issue in section['common_issues']:
                    f.write(f"**Problem:** {issue['problem']}\n\n")
                    f.write("Solutions:\n")
                    for solution in issue['solutions']:
                        f.write(f"- {solution}\n")
                    f.write("\n")

def main():
    """Main function to create the setup guide."""
    
    print("📚 CREATING WIX INTEGRATION SETUP GUIDE")
    print("=" * 40)
    print("Comprehensive step-by-step implementation instructions")
    print()
    
    # Generate and save the guide
    results = save_setup_guide()
    
    print("[OK] SETUP GUIDE CREATED")
    print(f"📁 Location: {results['output_dir']}")
    print()
    print("📄 Files created:")
    print(f"   • WIX_INTEGRATION_SETUP_GUIDE.json (complete guide)")
    print(f"   • WIX_SETUP_GUIDE.md (readable format)")
    print(f"   • env_template.txt (configuration template)")
    print()
    
    print("🎯 NEXT STEPS TO GET STARTED:")
    print("=" * 30)
    print()
    print("1. **READ THE GUIDE**")
    print(f"   Open: {results['markdown_path']}")
    print("   This has all the step-by-step instructions")
    print()
    print("2. **GET WIX API CREDENTIALS**") 
    print("   • Go to https://dev.wix.com/")
    print("   • Create new app for your Arrow Limousine site")
    print("   • Get App ID, App Secret, and Access Token")
    print()
    print("3. **SET UP ENVIRONMENT**")
    print("   • Copy env_template.txt to L:/limo/.env")
    print("   • Fill in your actual Wix API credentials")
    print("   • Install required packages: pip install requests python-dotenv")
    print()
    print("4. **TEST CONNECTION**")
    print("   • Run: python scripts/test_wix_connection.py") 
    print("   • Verify API access is working")
    print()
    print("5. **IMPLEMENT FEATURES**")
    print("   • Follow the guide step by step")
    print("   • Start with business info sync")
    print("   • Add booking integration")
    print("   • Implement SEO optimization")
    print()
    
    print("💡 WHAT THIS WILL DO FOR YOU:")
    print("=" * 32)
    print("[OK] Automatically update website content from your database")
    print("[OK] Sync booking data between Wix and your system")  
    print("[OK] Monitor website for errors and issues")
    print("[OK] Optimize for Google Search and local SEO")
    print("[OK] Manage customer reviews and testimonials")
    print("[OK] Update pricing and service availability")
    print("[OK] Generate performance and booking reports")
    print()
    
    print("🔗 USEFUL RESOURCES:")
    print("=" * 19)
    print("• Wix Developer Docs: https://dev.wix.com/docs")
    print("• Wix API Reference: https://dev.wix.com/api/rest")
    print("• Wix JavaScript SDK: https://dev.wix.com/docs/sdk") 
    print("• Google Search Console: https://search.google.com/search-console")
    print()
    
    return results

if __name__ == "__main__":
    main()