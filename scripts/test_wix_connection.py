#!/usr/bin/env python3
"""
WIX CONNECTION TEST
==================

Simple script to test your Wix API connection and verify credentials.
Run this first to make sure everything is set up correctly.
"""

import os
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("[WARN] python-dotenv not installed. Run: pip install python-dotenv")

class WixConnectionTester:
    """Test Wix API connection and credentials."""
    
    def __init__(self):
        """Initialize with environment variables."""
        
        # Load environment variables if available
        if DOTENV_AVAILABLE:
            load_dotenv()
        
        # Get Wix credentials from environment
        self.app_id = os.getenv('WIX_APP_ID')
        self.app_secret = os.getenv('WIX_APP_SECRET') 
        self.access_token = os.getenv('WIX_ACCESS_TOKEN')
        self.site_id = os.getenv('WIX_SITE_ID')
        
        self.base_url = "https://www.wixapis.com"
        
        # Set up headers
        self.headers = {
            "Content-Type": "application/json"
        }
        
        if self.access_token:
            self.headers["Authorization"] = f"Bearer {self.access_token}"
    
    def check_environment(self) -> Dict:
        """Check if environment is set up correctly."""
        
        results = {
            'env_file_exists': False,
            'credentials_present': {},
            'missing_credentials': [],
            'recommendations': []
        }
        
        # Check if .env file exists
        env_file_path = "L:/limo/.env"
        results['env_file_exists'] = os.path.exists(env_file_path)
        
        if not results['env_file_exists']:
            results['recommendations'].append("Create .env file in L:/limo/ directory")
        
        # Check credentials
        credentials = {
            'WIX_APP_ID': self.app_id,
            'WIX_APP_SECRET': self.app_secret,
            'WIX_ACCESS_TOKEN': self.access_token,
            'WIX_SITE_ID': self.site_id
        }
        
        for cred_name, cred_value in credentials.items():
            is_present = cred_value is not None and cred_value != ""
            results['credentials_present'][cred_name] = is_present
            
            if not is_present:
                results['missing_credentials'].append(cred_name)
        
        if results['missing_credentials']:
            results['recommendations'].append("Add missing credentials to .env file")
            results['recommendations'].append("Get credentials from https://dev.wix.com/")
        
        return results
    
    def test_basic_connection(self) -> Dict:
        """Test basic connection to Wix APIs."""
        
        results = {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': None
        }
        
        try:
            # Try to get site information
            url = f"{self.base_url}/site/v2/site"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            
            if response.status_code == 200:
                results['response_data'] = response.json()
            else:
                results['error'] = f"HTTP {response.status_code}: {response.text}"
            
        except requests.exceptions.RequestException as e:
            results['error'] = f"Connection error: {str(e)}"
        except Exception as e:
            results['error'] = f"Unexpected error: {str(e)}"
        
        return results
    
    def test_business_info_access(self) -> Dict:
        """Test access to business information API."""
        
        results = {
            'success': False,
            'business_name': None,
            'contact_info': None,
            'error': None
        }
        
        try:
            url = f"{self.base_url}/business-info/v1/business-info"
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results['success'] = True
                results['business_name'] = data.get('businessName')
                results['contact_info'] = data.get('contactInfo', {})
            else:
                results['error'] = f"HTTP {response.status_code}: {response.text}"
            
        except Exception as e:
            results['error'] = f"Error: {str(e)}"
        
        return results
    
    def test_bookings_access(self) -> Dict:
        """Test access to bookings API."""
        
        results = {
            'success': False,
            'bookings_count': 0,
            'recent_bookings': [],
            'error': None
        }
        
        try:
            url = f"{self.base_url}/bookings/v2/bookings"
            params = {'limit': 5}  # Get last 5 bookings
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results['success'] = True
                bookings = data.get('bookings', [])
                results['bookings_count'] = len(bookings)
                results['recent_bookings'] = bookings
            else:
                results['error'] = f"HTTP {response.status_code}: {response.text}"
            
        except Exception as e:
            results['error'] = f"Error: {str(e)}"
        
        return results
    
    def run_comprehensive_test(self) -> Dict:
        """Run all tests and provide comprehensive report."""
        
        print("🔍 TESTING WIX API CONNECTION")
        print("=" * 30)
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'environment_check': None,
            'basic_connection': None,
            'business_info': None, 
            'bookings_access': None,
            'overall_status': 'UNKNOWN',
            'next_steps': []
        }
        
        # 1. Environment Check
        print("1️⃣ CHECKING ENVIRONMENT SETUP...")
        report['environment_check'] = self.check_environment()
        
        env_ok = (report['environment_check']['env_file_exists'] and 
                 len(report['environment_check']['missing_credentials']) == 0)
        
        if env_ok:
            print("   [OK] Environment setup complete")
        else:
            print("   [FAIL] Environment setup incomplete")
            for rec in report['environment_check']['recommendations']:
                print(f"      • {rec}")
        print()
        
        if not env_ok:
            report['overall_status'] = 'SETUP_REQUIRED'
            report['next_steps'] = report['environment_check']['recommendations']
            return report
        
        # 2. Basic Connection Test
        print("2️⃣ TESTING BASIC API CONNECTION...")
        report['basic_connection'] = self.test_basic_connection()
        
        if report['basic_connection']['success']:
            print("   [OK] Successfully connected to Wix APIs")
        else:
            print(f"   [FAIL] Connection failed: {report['basic_connection']['error']}")
        print()
        
        # 3. Business Info Test
        print("3️⃣ TESTING BUSINESS INFO ACCESS...")
        report['business_info'] = self.test_business_info_access()
        
        if report['business_info']['success']:
            print("   [OK] Business info access working")
            if report['business_info']['business_name']:
                print(f"      Business: {report['business_info']['business_name']}")
        else:
            print(f"   [FAIL] Business info access failed: {report['business_info']['error']}")
        print()
        
        # 4. Bookings Access Test
        print("4️⃣ TESTING BOOKINGS ACCESS...")
        report['bookings_access'] = self.test_bookings_access()
        
        if report['bookings_access']['success']:
            print(f"   [OK] Bookings access working ({report['bookings_access']['bookings_count']} recent bookings)")
        else:
            print(f"   [FAIL] Bookings access failed: {report['bookings_access']['error']}")
        print()
        
        # Overall Status
        all_tests_passed = (
            report['basic_connection']['success'] and
            report['business_info']['success'] and
            report['bookings_access']['success']
        )
        
        if all_tests_passed:
            report['overall_status'] = 'SUCCESS'
            report['next_steps'] = [
                "All tests passed! You're ready to implement Wix integration",
                "Run: python scripts/wix_integration_manager.py",
                "Follow the setup guide for advanced features"
            ]
        else:
            report['overall_status'] = 'PARTIAL_SUCCESS'
            report['next_steps'] = [
                "Some tests failed - check API credentials and permissions",
                "Verify your Wix app has proper permissions enabled",
                "Regenerate access token if needed"
            ]
        
        return report

def create_env_file_template():
    """Create .env file template if it doesn't exist."""
    
    env_path = "L:/limo/.env"
    
    if not os.path.exists(env_path):
        template_content = """# Wix API Configuration
# Get these values from https://dev.wix.com/

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
DB_PASSWORD=***REMOVED***
"""
        
        with open(env_path, 'w') as f:
            f.write(template_content)
        
        print(f"📄 Created .env template at: {env_path}")
        print("📝 Edit this file and add your actual Wix API credentials")
        return True
    
    return False

def main():
    """Main function to run connection tests."""
    
    print("🎯 WIX API CONNECTION TESTER")
    print("=" * 28)
    print("Testing Arrow Limousine Wix integration setup")
    print()
    
    # Create .env template if needed
    template_created = create_env_file_template()
    
    if template_created:
        print()
        print("[WARN] SETUP REQUIRED:")
        print("   1. Edit L:/limo/.env file")
        print("   2. Add your actual Wix API credentials")
        print("   3. Run this test again")
        print()
        print("🔗 Get credentials from: https://dev.wix.com/")
        return
    
    # Initialize tester and run tests
    tester = WixConnectionTester()
    report = tester.run_comprehensive_test()
    
    # Display final results
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 23)
    
    status_emoji = {
        'SUCCESS': '[OK]',
        'PARTIAL_SUCCESS': '[WARN]', 
        'SETUP_REQUIRED': '[FAIL]',
        'UNKNOWN': '❓'
    }
    
    emoji = status_emoji.get(report['overall_status'], '❓')
    print(f"Overall Status: {emoji} {report['overall_status']}")
    print()
    
    if report['next_steps']:
        print("🎯 NEXT STEPS:")
        for i, step in enumerate(report['next_steps'], 1):
            print(f"   {i}. {step}")
        print()
    
    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"L:/limo/reports/wix_connection_test_{timestamp}.json"
    
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"💾 Detailed report saved to: {report_path}")
    
    return report

if __name__ == "__main__":
    main()