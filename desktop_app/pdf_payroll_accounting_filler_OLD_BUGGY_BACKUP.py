"""
PDF Form Filler - Payroll & Accounting Functions
Generates professional PDF documents for:
- Payroll: T4 slips, pay stubs, paycheques, WCB statements
- Accounting: Invoices, receipts, expense reports, GL exports, vendor statements
"""

import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
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

class PayrollAccountingPDFFiller:
    """Generate PDF forms for payroll and accounting functions"""
    
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
            print(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from database"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
    
    # ===== PAYROLL FUNCTIONS =====
    
    def generate_paystub(self, employee_id: int, year: int, month: int, output_path: str = None) -> Optional[str]:
        """Generate pay stub PDF for employee"""
        
        if output_path is None:
            output_path = f"paystub_{employee_id}_{year}_{month:02d}.pdf"
        
        if not self.connect():
            return None
        
        try:
            # Get employee data
            self.cur.execute("""
                SELECT full_name, employee_number, phone, email, position
                FROM employees WHERE employee_id = %s
            """, (employee_id,))
            employee = self.cur.fetchone()
            if not employee:
                print(f"Employee {employee_id} not found")
                return None
            
            # Get payroll data
            self.cur.execute("""
                SELECT gross_pay, cpp, ei, tax, total_deductions, net_pay,
                       hours_worked, pay_date
                FROM driver_payroll
                WHERE employee_id = %s AND year = %s AND month = %s
                LIMIT 1
            """, (employee_id, year, month))
            
            payroll = self.cur.fetchone()
            if not payroll:
                print(f"No payroll data for employee {employee_id} in {year}-{month:02d}")
                return None
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=14,
                textColor=colors.HexColor('#1f4788'), alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("PAY STUB", title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Employee info
            emp_data = [
                ["Employee:", employee['full_name'], "Period:", f"{year}-{month:02d}"],
                ["Employee #:", employee['employee_number'], "Pay Date:", str(payroll['pay_date'])],
                ["Position:", employee['position'], "Hours:", f"{payroll['hours_worked']:.1f}"],
            ]
            emp_table = Table(emp_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
            emp_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(emp_table)
            elements.append(Spacer(1, 0.2*inch))
            
            # Earnings & Deductions
            gross = Decimal(str(payroll['gross_pay'] or 0))
            cpp = Decimal(str(payroll['cpp'] or 0))
            ei = Decimal(str(payroll['ei'] or 0))
            tax = Decimal(str(payroll['tax'] or 0))
            net = Decimal(str(payroll['net_pay'] or 0))
            
            fin_data = [
                ["", "Amount"],
                ["Gross Pay:", f"${gross:,.2f}"],
                ["", ""],
                ["Deductions:", ""],
                ["CPP:", f"-${cpp:,.2f}"],
                ["EI:", f"-${ei:,.2f}"],
                ["Income Tax:", f"-${tax:,.2f}"],
                ["Total Deductions:", f"-${(cpp + ei + tax):,.2f}"],
                ["", ""],
                ["NET PAY:", f"${net:,.2f}"],
            ]
            
            fin_table = Table(fin_data, colWidths=[2.5*inch, 1.5*inch])
            fin_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d3d3d3')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(fin_table)
            
            # Build PDF
            doc.build(elements)
            print(f"Pay stub created: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error generating pay stub: {e}")
            return None
        
        finally:
            self.disconnect()
    
    def generate_t4_slip(self, employee_id: int, tax_year: int, output_path: str = None) -> Optional[str]:
        """Generate T4 tax slip PDF"""
        
        if output_path is None:
            output_path = f"t4_slip_{employee_id}_{tax_year}.pdf"
        
        if not self.connect():
            return None
        
        try:
            # Get employee data
            self.cur.execute("""
                SELECT full_name, t4_sin, street_address, city, province, postal_code
                FROM employees WHERE employee_id = %s
            """, (employee_id,))
            employee = self.cur.fetchone()
            if not employee:
                return None
            
            # Get T4 data from payroll
            self.cur.execute("""
                SELECT 
                    SUM(gross_pay) as total_income,
                    SUM(cpp) as total_cpp,
                    SUM(ei) as total_ei,
                    SUM(tax) as total_tax,
                    SUM(t4_box_14) as box_14,
                    SUM(t4_box_16) as box_16,
                    SUM(t4_box_18) as box_18,
                    SUM(t4_box_22) as box_22,
                    SUM(t4_box_24) as box_24,
                    SUM(t4_box_26) as box_26,
                    SUM(t4_box_44) as box_44,
                    SUM(t4_box_46) as box_46,
                    SUM(t4_box_52) as box_52
                FROM driver_payroll
                WHERE employee_id = %s AND year = %s
            """, (employee_id, tax_year))
            
            t4_data = self.cur.fetchone()
            if not t4_data:
                return None
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=14,
                textColor=colors.HexColor('#1f4788'), alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("STATEMENT OF REMUNERATION PAID (T4)", title_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Employee info
            emp_data = [
                ["Employee Name:", employee['full_name'], "SIN:", employee['t4_sin']],
                ["Address:", f"{employee['street_address']}, {employee['city']}, {employee['province']} {employee['postal_code']}", "", ""],
                ["Tax Year:", str(tax_year), "", ""],
            ]
            emp_table = Table(emp_data, colWidths=[1*inch, 2.5*inch, 1*inch, 1.5*inch])
            emp_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(emp_table)
            elements.append(Spacer(1, 0.15*inch))
            
            # T4 Boxes
            box_data = [
                ["Box", "Description", "Amount"],
                ["14", "Employment Income", f"${t4_data['box_14'] or 0:,.2f}"],
                ["16", "Employee CPP Contributions", f"${t4_data['box_16'] or 0:,.2f}"],
                ["18", "Employee EI Premiums", f"${t4_data['box_18'] or 0:,.2f}"],
                ["22", "Income Tax Deducted", f"${t4_data['box_22'] or 0:,.2f}"],
                ["24", "EI Insurable Earnings", f"${t4_data['box_24'] or 0:,.2f}"],
                ["26", "CPP Pensionable Earnings", f"${t4_data['box_26'] or 0:,.2f}"],
                ["44", "Employment Commissions", f"${t4_data['box_44'] or 0:,.2f}"],
                ["46", "Deferred Salary/Leave of Absence", f"${t4_data['box_46'] or 0:,.2f}"],
                ["52", "Other Income", f"${t4_data['box_52'] or 0:,.2f}"],
            ]
            
            box_table = Table(box_data, colWidths=[0.5*inch, 3*inch, 1.5*inch])
            box_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(box_table)
            
            doc.build(elements)
            print(f"T4 slip created: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error generating T4 slip: {e}")
            return None
        
        finally:
            self.disconnect()
    
    # ===== ACCOUNTING FUNCTIONS =====
    
    def generate_invoice_pdf(self, invoice_id: int, output_path: str = None) -> Optional[str]:
        """Generate invoice PDF"""
        
        if output_path is None:
            output_path = f"invoice_{invoice_id}.pdf"
        
        if not self.connect():
            return None
        
        try:
            # Get invoice header
            self.cur.execute("""
                SELECT invoice_number, invoice_date, amount, status
                FROM invoice_tracking WHERE id = %s
            """, (invoice_id,))
            invoice = self.cur.fetchone()
            if not invoice:
                return None
            
            # Get invoice items
            self.cur.execute("""
                SELECT line_number, item_name, description, quantity,
                       unit_price, amount, is_taxable, tax_amount
                FROM invoice_line_items WHERE invoice_id = %s
                ORDER BY line_number
            """, (invoice_id,))
            items = self.cur.fetchall()
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=14,
                textColor=colors.HexColor('#1f4788'), alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("INVOICE", title_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Invoice header
            header_data = [
                ["Invoice #:", str(invoice['invoice_number']), "Date:", str(invoice['invoice_date'])],
                ["Status:", str(invoice['status']).upper(), "Amount:", f"${invoice['amount']:,.2f}"],
            ]
            header_table = Table(header_data, colWidths=[1*inch, 2*inch, 1*inch, 2*inch])
            header_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 0.2*inch))
            
            # Line items
            items_data = [["Line", "Item", "Qty", "Unit Price", "Amount", "Tax"]]
            subtotal = Decimal('0')
            total_tax = Decimal('0')
            
            for item in items:
                amt = Decimal(str(item['amount'] or 0))
                tax = Decimal(str(item['tax_amount'] or 0))
                items_data.append([
                    str(item['line_number']),
                    str(item['item_name']),
                    str(item['quantity']),
                    f"${item['unit_price']:,.2f}",
                    f"${amt:,.2f}",
                    f"${tax:,.2f}",
                ])
                subtotal += amt
                total_tax += tax
            
            items_data.append(["", "", "", "Subtotal:", f"${subtotal:,.2f}", ""])
            items_data.append(["", "", "", "Tax:", f"${total_tax:,.2f}", ""])
            items_data.append(["", "", "", "TOTAL:", f"${subtotal + total_tax:,.2f}", ""])
            
            items_table = Table(items_data, colWidths=[0.4*inch, 2*inch, 0.5*inch, 1*inch, 1*inch, 0.8*inch])
            items_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 1), (5, -1), 'RIGHT'),
                ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#d3d3d3')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(items_table)
            
            doc.build(elements)
            print(f"Invoice PDF created: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error generating invoice: {e}")
            return None
        
        finally:
            self.disconnect()
    
    def generate_expense_report(self, start_date: date, end_date: date, output_path: str = None) -> Optional[str]:
        """Generate expense report for date range"""
        
        if output_path is None:
            output_path = f"expense_report_{start_date}_{end_date}.pdf"
        
        if not self.connect():
            return None
        
        try:
            # Get receipts
            self.cur.execute("""
                SELECT receipt_date, vendor_name, description, gross_amount, gst_amount,
                       category, payment_method
                FROM receipts
                WHERE receipt_date >= %s AND receipt_date <= %s
                ORDER BY receipt_date
            """, (start_date, end_date))
            
            receipts = self.cur.fetchall()
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=14,
                textColor=colors.HexColor('#1f4788'), alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph("EXPENSE REPORT", title_style))
            elements.append(Spacer(1, 0.15*inch))
            
            # Date range
            date_info = f"Period: {start_date} to {end_date}"
            elements.append(Paragraph(date_info, styles['Normal']))
            elements.append(Spacer(1, 0.15*inch))
            
            # Expenses table
            exp_data = [["Date", "Vendor", "Description", "Amount", "GST", "Category"]]
            total_amt = Decimal('0')
            total_gst = Decimal('0')
            
            for receipt in receipts:
                amt = Decimal(str(receipt['gross_amount'] or 0))
                gst = Decimal(str(receipt['gst_amount'] or 0))
                exp_data.append([
                    str(receipt['receipt_date']),
                    str(receipt['vendor_name'][:20]),
                    str(receipt['description'][:30]),
                    f"${amt:,.2f}",
                    f"${gst:,.2f}",
                    str(receipt['category']),
                ])
                total_amt += amt
                total_gst += gst
            
            exp_data.append(["", "", "TOTAL:", f"${total_amt:,.2f}", f"${total_gst:,.2f}", ""])
            
            exp_table = Table(exp_data, colWidths=[0.9*inch, 1.2*inch, 1.5*inch, 0.9*inch, 0.7*inch, 1*inch])
            exp_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (3, 0), (5, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d3d3d3')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f0f0')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(exp_table)
            
            doc.build(elements)
            print(f"Expense report created: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error generating expense report: {e}")
            return None
        
        finally:
            self.disconnect()
    
    def generate_vendor_statement(self, vendor_name: str, output_path: str = None) -> Optional[str]:
        """Generate vendor statement PDF"""
        
        if output_path is None:
            output_path = f"vendor_statement_{vendor_name.replace(' ', '_')}.pdf"
        
        if not self.connect():
            return None
        
        try:
            # Get invoices from vendor
            self.cur.execute("""
                SELECT invoice_number, invoice_date, amount, tax_amount,
                       status, payment_date, payment_method
                FROM payables
                WHERE vendor_name = %s
                ORDER BY invoice_date DESC
            """, (vendor_name,))
            
            invoices = self.cur.fetchall()
            
            if not invoices:
                print(f"No invoices for vendor: {vendor_name}")
                return None
            
            # Create PDF
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=14,
                textColor=colors.HexColor('#1f4788'), alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            elements.append(Paragraph(f"VENDOR STATEMENT: {vendor_name.upper()}", title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Invoices table
            inv_data = [["Invoice #", "Date", "Amount", "Tax", "Status", "Paid Date"]]
            total_amt = Decimal('0')
            total_tax = Decimal('0')
            
            for invoice in invoices:
                amt = Decimal(str(invoice['amount'] or 0))
                tax = Decimal(str(invoice['tax_amount'] or 0))
                inv_data.append([
                    str(invoice['invoice_number']),
                    str(invoice['invoice_date']),
                    f"${amt:,.2f}",
                    f"${tax:,.2f}",
                    str(invoice['status']).upper(),
                    str(invoice['payment_date'] or 'Pending'),
                ])
                total_amt += amt
                total_tax += tax
            
            inv_data.append(["", "", f"${total_amt:,.2f}", f"${total_tax:,.2f}", "", ""])
            
            inv_table = Table(inv_data, colWidths=[1.2*inch, 1*inch, 1*inch, 0.9*inch, 1*inch, 1.2*inch])
            inv_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (4, -1), 'RIGHT'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d3d3d3')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(inv_table)
            
            doc.build(elements)
            print(f"Vendor statement created: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error generating vendor statement: {e}")
            return None
        
        finally:
            self.disconnect()


# Test
if __name__ == "__main__":
    filler = PayrollAccountingPDFFiller()
    
    # Test functions
    print("[TEST] Pay stub generation")
    result = filler.generate_paystub(1, 2025, 12, "test_paystub.pdf")
    print(f"Result: {result}\n")
    
    print("[TEST] T4 slip generation")
    result = filler.generate_t4_slip(1, 2025, "test_t4.pdf")
    print(f"Result: {result}\n")
