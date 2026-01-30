"""
PDF Charter Export Module
Consolidated PDF export for all charter data:
- Booking details
- Client information
- Dispatch/Routing
- Invoices
- Beverage orders & items
- Driver details
- Printable client-facing document

Supports both template-based PDF generation and HTML-to-PDF conversion
"""

import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import json

class PDFCharterExporter:
    """Export charter data to PDF with all related information"""
    
    def __init__(self, db_host="localhost", db_name="almsdata", db_user="postgres", db_password="***REMOVED***"):
        self.db_config = {
            'host': db_host,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
        self.conn = None
        self.cur = None
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor(cursor_factory=DictCursor)
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from database"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
    
    def get_charter_data(self, reserve_number: str) -> Dict:
        """Get all charter data by reserve number"""
        charter_data = {
            'booking': None,
            'client': None,
            'routing': [],
            'invoice': None,
            'beverages': [],
            'driver': None,
            'errors': []
        }
        
        if not self.connect():
            return charter_data
        
        try:
            # 1. Get charter booking data
            self.cur.execute("""
                SELECT 
                    charter_id, reserve_number, charter_date, 
                    pickup_time, pickup_address, dropoff_address,
                    passenger_count, vehicle, driver, rate,
                    client_display_name, total_amount_due, paid_amount,
                    status, notes, booking_notes, special_requirements,
                    pickup_time, dropoff_address,
                    beverage_service_required, accessibility_required,
                    driver_hours_worked, driver_base_pay, driver_gratuity,
                    created_at, updated_at
                FROM charters
                WHERE reserve_number = %s
                LIMIT 1
            """, (reserve_number,))
            
            booking = self.cur.fetchone()
            if booking:
                charter_data['booking'] = dict(booking)
            else:
                charter_data['errors'].append(f"Charter not found: {reserve_number}")
                self.disconnect()
                return charter_data
            
            charter_id = booking['charter_id']
            
            # 2. Get client data
            self.cur.execute("""
                SELECT 
                    client_id, account_number, company_name, client_name,
                    primary_phone, email, address_line1, city, state, zip_code,
                    balance, gratuity_percentage, is_gst_exempt, payment_terms,
                    notes
                FROM clients
                WHERE client_id = %s
                LIMIT 1
            """, (booking['client_id'],))
            
            client = self.cur.fetchone()
            if client:
                charter_data['client'] = dict(client)
            
            # 3. Get charter routes
            self.cur.execute("""
                SELECT 
                    route_id, route_sequence, pickup_location, pickup_time,
                    dropoff_location, dropoff_time, estimated_duration_minutes,
                    actual_duration_minutes, estimated_distance_km, actual_distance_km,
                    route_price, route_notes, route_status
                FROM charter_routes
                WHERE charter_id = %s
                ORDER BY route_sequence
            """, (charter_id,))
            
            routes = self.cur.fetchall()
            charter_data['routing'] = [dict(r) for r in routes]
            
            # 4. Get invoice data
            self.cur.execute("""
                SELECT 
                    invoice_tracking.id, invoice_number, invoice_date,
                    amount, status, notes
                FROM invoice_tracking
                WHERE document_id IN (
                    SELECT charter_id FROM charters WHERE reserve_number = %s
                )
                LIMIT 1
            """, (reserve_number,))
            
            invoice = self.cur.fetchone()
            if invoice:
                charter_data['invoice'] = dict(invoice)
                
                # Get invoice line items
                self.cur.execute("""
                    SELECT 
                        line_number, item_name, description, quantity,
                        unit_price, amount, is_taxable, tax_amount,
                        service_type, account_name
                    FROM invoice_line_items
                    WHERE invoice_id = %s
                    ORDER BY line_number
                """, (invoice['id'],))
                
                items = self.cur.fetchall()
                charter_data['invoice_items'] = [dict(i) for i in items]
            
            # 5. Get beverage orders
            self.cur.execute("""
                SELECT 
                    bo.order_id, bo.order_date, bo.subtotal, bo.gst, bo.total,
                    bo.status
                FROM beverage_orders bo
                WHERE bo.reserve_number = %s
            """, (reserve_number,))
            
            bev_orders = self.cur.fetchall()
            charter_data['beverage_orders'] = [dict(b) for b in bev_orders]
            
            # Get beverage items for each order
            if bev_orders:
                order_ids = [b['order_id'] for b in bev_orders]
                placeholders = ','.join(['%s'] * len(order_ids))
                self.cur.execute(f"""
                    SELECT 
                        order_id, item_name, quantity, unit_price, total,
                        our_cost, markup_pct, deposit_amount, gst_amount
                    FROM beverage_order_items
                    WHERE order_id IN ({placeholders})
                    ORDER BY order_id, item_line_id
                """, order_ids)
                
                bev_items = self.cur.fetchall()
                charter_data['beverage_items'] = [dict(b) for b in bev_items]
            
            # 6. Get charter beverages (from charter_beverages table)
            self.cur.execute("""
                SELECT 
                    id, item_name, quantity, unit_price_charged, unit_our_cost,
                    deposit_per_unit, line_amount_charged, line_cost, notes
                FROM charter_beverages
                WHERE charter_id = %s
            """, (charter_id,))
            
            ch_bev = self.cur.fetchall()
            charter_data['charter_beverages'] = [dict(b) for b in ch_bev]
            
            # 7. Get driver details
            self.cur.execute("""
                SELECT 
                    employee_id, full_name, phone, cell_phone, email,
                    driver_code, employee_number, position, hire_date,
                    hourly_rate, license_number, status
                FROM employees
                WHERE full_name = %s OR employee_number = %s
                LIMIT 1
            """, (booking['driver'], booking['driver']))
            
            driver = self.cur.fetchone()
            if driver:
                charter_data['driver'] = dict(driver)
        
        except Exception as e:
            charter_data['errors'].append(f"Data retrieval error: {str(e)}")
        
        finally:
            self.disconnect()
        
        return charter_data
    
    def generate_pdf(self, reserve_number: str, output_path: str = None) -> str:
        """Generate PDF charter export"""
        
        if output_path is None:
            output_path = f"charter_{reserve_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Get all data
        data = self.get_charter_data(reserve_number)
        
        if not data['booking']:
            print(f"❌ No booking found for {reserve_number}")
            return None
        
        # Create PDF
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        # ===== TITLE =====
        elements.append(Paragraph("CHARTER SERVICE INVOICE", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # ===== BOOKING DETAILS =====
        if data['booking']:
            elements.append(Paragraph("BOOKING DETAILS", heading_style))
            booking = data['booking']
            
            booking_data = [
                ["Reserve #:", str(booking.get('reserve_number', 'N/A')), "Date:", booking.get('charter_date', 'N/A')],
                ["Client:", str(booking.get('client_display_name', 'N/A')), "Status:", str(booking.get('status', 'N/A')).upper()],
                ["Pickup:", booking.get('pickup_address', 'N/A'), "Time:", str(booking.get('pickup_time', 'N/A'))],
                ["Dropoff:", booking.get('dropoff_address', 'N/A'), "Vehicle:", str(booking.get('vehicle', 'N/A'))],
                ["Passengers:", str(booking.get('passenger_count', 0)), "Driver:", str(booking.get('driver', 'N/A'))],
                ["Rate:", f"${booking.get('rate', 0):.2f}", "Hours Worked:", f"{booking.get('driver_hours_worked', 0):.1f}"],
            ]
            
            booking_table = Table(booking_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
            booking_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(booking_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== CLIENT DETAILS =====
        if data['client']:
            elements.append(Paragraph("CLIENT INFORMATION", heading_style))
            client = data['client']
            
            client_data = [
                ["Account #:", str(client.get('account_number', 'N/A')), "Company:", str(client.get('company_name', 'N/A'))],
                ["Contact:", str(client.get('client_name', 'N/A')), "Phone:", str(client.get('primary_phone', 'N/A'))],
                ["Email:", str(client.get('email', 'N/A')), "Address:", f"{client.get('address_line1', '')}, {client.get('city', '')}"],
                ["Terms:", str(client.get('payment_terms', 'N/A')), "GST Exempt:", "Yes" if client.get('is_gst_exempt') else "No"],
            ]
            
            client_table = Table(client_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
            client_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(client_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== ROUTING DETAILS =====
        if data['routing']:
            elements.append(Paragraph("ROUTING SCHEDULE", heading_style))
            
            route_data = [["#", "Pickup Location", "Time", "Dropoff Location", "Time", "Distance", "Status"]]
            for route in data['routing']:
                route_data.append([
                    str(route.get('route_sequence', '')),
                    str(route.get('pickup_location', '')),
                    str(route.get('pickup_time', '')),
                    str(route.get('dropoff_location', '')),
                    str(route.get('dropoff_time', '')),
                    f"{route.get('actual_distance_km', 0):.1f} km",
                    str(route.get('route_status', 'pending')).upper(),
                ])
            
            route_table = Table(route_data, colWidths=[0.3*inch, 1.5*inch, 0.7*inch, 1.5*inch, 0.7*inch, 0.7*inch, 0.8*inch])
            route_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(route_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== BEVERAGE ITEMS =====
        beverages = data.get('charter_beverages', []) or data.get('beverage_items', [])
        if beverages:
            elements.append(Paragraph("BEVERAGE SERVICE", heading_style))
            
            bev_data = [["Item", "Qty", "Unit Price", "Deposit", "Total"]]
            total_bev = Decimal('0.00')
            
            for bev in beverages:
                qty = bev.get('quantity', 0)
                price = Decimal(str(bev.get('unit_price_charged', bev.get('unit_price', 0)) or 0))
                deposit = Decimal(str(bev.get('deposit_per_unit', bev.get('deposit_amount', 0)) or 0))
                line_total = Decimal(str(bev.get('line_amount_charged', bev.get('total', 0)) or 0))
                
                bev_data.append([
                    str(bev.get('item_name', '')),
                    str(qty),
                    f"${price:.2f}",
                    f"${deposit:.2f}",
                    f"${line_total:.2f}",
                ])
                total_bev += line_total
            
            bev_data.append(["", "", "", "TOTAL:", f"${total_bev:.2f}"])
            
            bev_table = Table(bev_data, colWidths=[2.5*inch, 0.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            bev_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d3d3d3')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(bev_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== DRIVER DETAILS =====
        if data['driver']:
            elements.append(Paragraph("DRIVER INFORMATION", heading_style))
            driver = data['driver']
            
            driver_data = [
                ["Driver:", str(driver.get('full_name', 'N/A')), "Code:", str(driver.get('driver_code', 'N/A'))],
                ["Phone:", str(driver.get('phone', driver.get('cell_phone', 'N/A'))), "Email:", str(driver.get('email', 'N/A'))],
                ["Hire Date:", str(driver.get('hire_date', 'N/A')), "Rate:", f"${driver.get('hourly_rate', 0):.2f}/hr"],
            ]
            
            driver_table = Table(driver_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
            driver_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(driver_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ===== FINANCIAL SUMMARY =====
        if data['booking']:
            elements.append(Paragraph("FINANCIAL SUMMARY", heading_style))
            booking = data['booking']
            
            subtotal = Decimal(str(booking.get('rate', 0) or 0))
            driver_pay = Decimal(str(booking.get('driver_base_pay', 0) or 0))
            gratuity = Decimal(str(booking.get('driver_gratuity', 0) or 0))
            total_due = Decimal(str(booking.get('total_amount_due', 0) or 0))
            paid = Decimal(str(booking.get('paid_amount', 0) or 0))
            balance = total_due - paid
            
            financial_data = [
                ["Charter Rate:", f"${subtotal:.2f}"],
                ["Driver Base Pay:", f"${driver_pay:.2f}"],
                ["Driver Gratuity:", f"${gratuity:.2f}"],
                ["", ""],
                ["TOTAL DUE:", f"${total_due:.2f}"],
                ["PAID:", f"${paid:.2f}"],
                ["BALANCE:", f"${balance:.2f}"],
            ]
            
            financial_table = Table(financial_data, colWidths=[2.5*inch, 1.5*inch])
            financial_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 4), (-1, 6), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 4), (-1, 6), colors.HexColor('#e0e0e0')),
                ('GRID', (0, 0), (-1, 3), 0.5, colors.lightgrey),
                ('GRID', (0, 4), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(financial_table)
        
        # Build PDF
        try:
            doc.build(elements)
            print(f"✅ PDF created: {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ PDF generation failed: {e}")
            return None


# Quick test
if __name__ == "__main__":
    exporter = PDFCharterExporter()
    
    # Test with a sample reserve number (adjust as needed)
    test_reserve = "023541"
    print(f"\n[TEST] Testing PDF export for {test_reserve}...")
    
    result = exporter.generate_pdf(test_reserve, f"test_charter_{test_reserve}.pdf")
    if result:
        print(f"[SUCCESS] Export successful: {result}")
    else:
        print("[FAILED] Export failed")
