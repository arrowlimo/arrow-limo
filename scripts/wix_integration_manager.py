#!/usr/bin/env python3
"""
WIX INTEGRATION MANAGER
======================

Comprehensive Wix API integration for Arrow Limousine website management.
Handles content updates, error checking, SEO optimization, and Google Search integration.

Uses provided JWT token for authentication with Wix APIs.
"""

import os
import requests
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import psycopg2
from urllib.parse import quote_plus
import time

class WixIntegrationManager:
    """Main Wix API integration manager."""
    
    def __init__(self, jwt_token: str):
        """Initialize with JWT token."""
        self.jwt_token = jwt_token
        self.base_url = "https://www.wixapis.com"
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        # Parse JWT to get site info
        self.site_info = self._parse_jwt_token()
        
    def _parse_jwt_token(self) -> Dict:
        """Parse JWT token to extract site and account information."""
        try:
            # JWT tokens have 3 parts separated by dots
            parts = self.jwt_token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT token format")
            
            # Decode the payload (second part)
            payload = parts[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            
            decoded = base64.b64decode(payload)
            token_data = json.loads(decoded)
            
            print(f"🔍 PARSED JWT TOKEN:")
            print(f"   • Token Data: {json.dumps(token_data, indent=2)}")
            
            return token_data
            
        except Exception as e:
            print(f"[FAIL] Error parsing JWT token: {str(e)}")
            return {}
    
    def get_site_info(self) -> Dict:
        """Get comprehensive site information."""
        try:
            # Business Info API
            response = requests.get(
                f"{self.base_url}/business-info/v1/business-info",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[FAIL] Site info error: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            print(f"[FAIL] Error getting site info: {str(e)}")
            return {}
    
    def get_wix_bookings(self) -> List[Dict]:
        """Get booking/reservation data from Wix."""
        try:
            # Wix Bookings API
            response = requests.get(
                f"{self.base_url}/bookings/v2/bookings",
                headers=self.headers,
                params={"limit": 100}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('bookings', [])
            else:
                print(f"[FAIL] Bookings error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"[FAIL] Error getting bookings: {str(e)}")
            return []
    
    def update_business_info(self, business_data: Dict) -> bool:
        """Update business information on Wix site."""
        try:
            response = requests.patch(
                f"{self.base_url}/business-info/v1/business-info",
                headers=self.headers,
                json=business_data
            )
            
            if response.status_code == 200:
                print(f"[OK] Business info updated successfully")
                return True
            else:
                print(f"[FAIL] Business info update error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[FAIL] Error updating business info: {str(e)}")
            return False
    
    def check_website_errors(self) -> List[Dict]:
        """Check for website errors and issues."""
        errors = []
        
        try:
            # Check site status
            site_info = self.get_site_info()
            
            # Check business hours
            business_hours = site_info.get('businessSchedule', {})
            if not business_hours:
                errors.append({
                    'type': 'business_schedule',
                    'severity': 'warning',
                    'message': 'Business hours not set'
                })
            
            # Check contact information
            contact_info = site_info.get('contactInfo', {})
            if not contact_info.get('phone'):
                errors.append({
                    'type': 'contact_info',
                    'severity': 'error',
                    'message': 'Phone number missing'
                })
            
            if not contact_info.get('email'):
                errors.append({
                    'type': 'contact_info',
                    'severity': 'error',
                    'message': 'Email address missing'
                })
            
            # Check location
            locations = site_info.get('locations', [])
            if not locations:
                errors.append({
                    'type': 'location',
                    'severity': 'warning',
                    'message': 'Business location not set'
                })
            
            return errors
            
        except Exception as e:
            errors.append({
                'type': 'system_error',
                'severity': 'error',
                'message': f"Error checking website: {str(e)}"
            })
            return errors
    
    def optimize_for_google_search(self) -> Dict:
        """Optimize website for Google Search visibility."""
        
        optimization_results = {
            'seo_updates': [],
            'content_updates': [],
            'errors': []
        }
        
        try:
            # Get current site info
            site_info = self.get_site_info()
            
            # Optimize business information for SEO
            seo_updates = {
                'businessName': 'Arrow Limousine Service - Premium Luxury Transportation',
                'businessDescription': 'Professional limousine and luxury transportation services in Saskatchewan. Airport transfers, corporate events, weddings, and special occasions. Premium fleet with experienced chauffeurs.',
                'categories': [
                    'Transportation Service',
                    'Limousine Service', 
                    'Airport Shuttle Service',
                    'Wedding Transportation',
                    'Corporate Transportation'
                ],
                'keywords': [
                    'limousine service saskatchewan',
                    'luxury transportation',
                    'airport shuttle saskatoon',
                    'wedding limousine',
                    'corporate transportation',
                    'chauffeur service',
                    'luxury car rental'
                ]
            }
            
            # Update SEO-optimized business info
            if self.update_business_info(seo_updates):
                optimization_results['seo_updates'].append('Business info optimized for search')
            
            # Check and fix common SEO issues
            seo_checks = self._perform_seo_audit()
            optimization_results['seo_updates'].extend(seo_checks)
            
            return optimization_results
            
        except Exception as e:
            optimization_results['errors'].append(f"SEO optimization error: {str(e)}")
            return optimization_results
    
    def _perform_seo_audit(self) -> List[str]:
        """Perform comprehensive SEO audit."""
        seo_updates = []
        
        try:
            # Check meta tags via Site API
            response = requests.get(
                f"{self.base_url}/site/v2/site",
                headers=self.headers
            )
            
            if response.status_code == 200:
                site_data = response.json()
                
                # Check title and description
                seo_settings = site_data.get('seoSettings', {})
                
                if not seo_settings.get('metaTitle'):
                    seo_updates.append('Meta title needs optimization')
                
                if not seo_settings.get('metaDescription'):
                    seo_updates.append('Meta description needs optimization')
                
                # Check for structured data
                if not seo_settings.get('structuredData'):
                    seo_updates.append('Structured data (Schema.org) needs implementation')
            
            return seo_updates
            
        except Exception as e:
            return [f"SEO audit error: {str(e)}"]
    
    def sync_bookings_to_database(self) -> Dict:
        """Sync Wix bookings to local PostgreSQL database."""
        
        sync_results = {
            'synced': 0,
            'errors': 0,
            'details': []
        }
        
        try:
            # Get Wix bookings
            wix_bookings = self.get_wix_bookings()
            
            if not wix_bookings:
                sync_results['details'].append('No bookings found in Wix')
                return sync_results
            
            # Connect to local database
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            for booking in wix_bookings:
                try:
                    # Extract booking data
                    booking_id = booking.get('id')
                    service_id = booking.get('serviceId')
                    start_time = booking.get('startDateTime')
                    end_time = booking.get('endDateTime')
                    status = booking.get('status')
                    
                    # Customer information
                    contact_details = booking.get('contactDetails', {})
                    customer_name = f"{contact_details.get('firstName', '')} {contact_details.get('lastName', '')}".strip()
                    customer_email = contact_details.get('email')
                    customer_phone = contact_details.get('phone')
                    
                    # Insert or update in charters table
                    cur.execute("""
                        INSERT INTO charters (
                            reserve_number, client_name, charter_date, pickup_time,
                            pickup_address, passenger_count, status, notes,
                            created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT (reserve_number) DO UPDATE SET
                            client_name = EXCLUDED.client_name,
                            status = EXCLUDED.status,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        f"WIX_{booking_id[:6]}",  # Create reserve number from Wix ID
                        customer_name,
                        start_time[:10] if start_time else None,  # Extract date
                        start_time[11:19] if start_time else None,  # Extract time
                        'From Wix Booking',  # Placeholder address
                        1,  # Default passenger count
                        status,
                        f"Wix booking ID: {booking_id}",
                        datetime.now(),
                        datetime.now()
                    ))
                    
                    # Add client if not exists
                    if customer_name and customer_email:
                        cur.execute("""
                            INSERT INTO clients (client_name, email, phone_number, created_at)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (email) DO UPDATE SET
                                client_name = EXCLUDED.client_name,
                                phone_number = EXCLUDED.phone_number
                        """, (customer_name, customer_email, customer_phone, datetime.now()))
                    
                    sync_results['synced'] += 1
                    sync_results['details'].append(f"Synced booking: {customer_name} - {start_time}")
                    
                except Exception as e:
                    sync_results['errors'] += 1
                    sync_results['details'].append(f"Error syncing booking {booking_id}: {str(e)}")
            
            conn.commit()
            cur.close()
            conn.close()
            
            return sync_results
            
        except Exception as e:
            sync_results['errors'] += 1
            sync_results['details'].append(f"Database sync error: {str(e)}")
            return sync_results
    
    def _get_db_connection(self):
        """Get PostgreSQL database connection."""
        return psycopg2.connect(
            host='localhost',
            database='almsdata',
            user='postgres',
            password='***REMOVED***'
        )
    
    def generate_website_report(self) -> Dict:
        """Generate comprehensive website status report."""
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'site_info': {},
            'errors': [],
            'seo_status': {},
            'booking_sync': {},
            'recommendations': []
        }
        
        try:
            print("🔍 GENERATING COMPREHENSIVE WEBSITE REPORT")
            print("=" * 45)
            
            # Get site information
            print("📊 Fetching site information...")
            report['site_info'] = self.get_site_info()
            
            # Check for errors
            print("🔍 Checking for website errors...")
            report['errors'] = self.check_website_errors()
            
            # SEO optimization
            print("🔍 Performing SEO analysis...")
            report['seo_status'] = self.optimize_for_google_search()
            
            # Sync bookings
            print("📅 Syncing bookings to database...")
            report['booking_sync'] = self.sync_bookings_to_database()
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(report)
            
            return report
            
        except Exception as e:
            report['errors'].append({
                'type': 'report_generation',
                'severity': 'error',
                'message': f"Error generating report: {str(e)}"
            })
            return report
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate actionable recommendations based on report."""
        
        recommendations = []
        
        # Error-based recommendations
        for error in report.get('errors', []):
            if error['type'] == 'contact_info':
                recommendations.append("Update contact information in Wix business settings")
            elif error['type'] == 'business_schedule':
                recommendations.append("Set business hours for better customer experience")
            elif error['type'] == 'location':
                recommendations.append("Add business location for local SEO benefits")
        
        # SEO recommendations
        seo_updates = report.get('seo_status', {}).get('seo_updates', [])
        if 'Meta title needs optimization' in seo_updates:
            recommendations.append("Optimize meta titles for better search ranking")
        
        if 'Structured data needs implementation' in seo_updates:
            recommendations.append("Implement Schema.org structured data for rich snippets")
        
        # Booking sync recommendations
        booking_sync = report.get('booking_sync', {})
        if booking_sync.get('errors', 0) > 0:
            recommendations.append("Review booking sync errors and fix data integration")
        
        if booking_sync.get('synced', 0) == 0:
            recommendations.append("Enable Wix booking system or check API permissions")
        
        return recommendations


def main():
    """Main function to demonstrate Wix integration capabilities."""
    
    # JWT token provided by user
    JWT_TOKEN = "IST.eyJraWQiOiJQb3pIX2FDMiIsImFsZyI6IlJTMjU2In0.eyJkYXRhIjoie1wiaWRcIjpcIjlhOTJkYTg1LTAxMzgtNDYyYy1hZGFlLTkyMjJhNGVjMzUxY1wiLFwiaWRlbnRpdHlcIjp7XCJ0eXBlXCI6XCJhcHBsaWNhdGlvblwiLFwiaWRcIjpcImZjNzUyMjJmLWI0M2ItNDExNi05ODExLTE4OGVjZTk3MDI4ZFwifSxcInRlbmFudFwiOntcInR5cGVcIjpcImFjY291bnRcIixcImlkXCI6XCIxNzljYjkxYS0xMGUzLTQ2NTktYWI5Yy05ZjE0YmUxZmUxOWFcIn19IiwiaWF0IjoxNzYxOTQ5OTcxfQ.cQRLQrnvfUXmr1919xgBo4gNxv_GqDIyOpd57hIuy-ppBVHVrgumBT2OuQLz1Pb73o1kShL9uzyX358_zXByhp6enZU3akuny6bzAW2Qti53-4wwswujpKHxHXGNB7EZrBV5-okAaDrGuzyTZA7be1lSoJkDonhwGsUPgd4ACg6xOZDy6CSmY-bELCMviP0SSsX2h2SUOsaoZ4QEFvMX28Si9ZiD4klYJ94t91J6lYk1_58jGpO7xSS1xxKn4iPTiN1evZVCnfSPEDJtir4niN74IZ9vMqbX3y0dFLtoJ-BusiAZTk86YjxaR5UlsHtcUKFPX7y2AqRx8V-UJEK0Dw"
    
    print("🎯 WIX INTEGRATION MANAGER")
    print("=" * 26)
    print("Arrow Limousine Website Management System")
    print()
    
    # Initialize Wix manager
    wix_manager = WixIntegrationManager(JWT_TOKEN)
    
    # Generate comprehensive report
    report = wix_manager.generate_website_report()
    
    # Display results
    print("\n📊 WEBSITE STATUS REPORT")
    print("=" * 24)
    
    # Site Info
    site_info = report.get('site_info', {})
    if site_info:
        print(f"🏢 Business Name: {site_info.get('businessName', 'Not set')}")
        print(f"📧 Email: {site_info.get('email', 'Not set')}")
        print(f"📞 Phone: {site_info.get('phone', 'Not set')}")
        print(f"🌍 Website: {site_info.get('website', 'Not set')}")
    
    # Errors
    errors = report.get('errors', [])
    if errors:
        print(f"\n[FAIL] WEBSITE ISSUES FOUND: {len(errors)}")
        for error in errors:
            severity_emoji = "🚨" if error['severity'] == 'error' else "[WARN]"
            print(f"   {severity_emoji} {error['message']}")
    else:
        print(f"\n[OK] NO CRITICAL ERRORS FOUND")
    
    # SEO Status
    seo_status = report.get('seo_status', {})
    seo_updates = seo_status.get('seo_updates', [])
    if seo_updates:
        print(f"\n🔍 SEO OPTIMIZATION STATUS:")
        for update in seo_updates:
            print(f"   • {update}")
    
    # Booking Sync
    booking_sync = report.get('booking_sync', {})
    if booking_sync:
        print(f"\n📅 BOOKING SYNC RESULTS:")
        print(f"   • Synced: {booking_sync.get('synced', 0)} bookings")
        print(f"   • Errors: {booking_sync.get('errors', 0)}")
    
    # Recommendations
    recommendations = report.get('recommendations', [])
    if recommendations:
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"L:/limo/reports/wix_website_report_{timestamp}.json"
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n💾 Report saved to: {report_file}")
    
    return report


if __name__ == "__main__":
    main()