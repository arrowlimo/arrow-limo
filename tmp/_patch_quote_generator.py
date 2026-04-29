"""Patch quote_generator_widget.py E501 lines (HTML template + Python lines)."""
import ast
from pathlib import Path

p = Path("desktop_app/quote_generator_widget.py")
src = p.read_text(encoding="utf-8")

# Line 372 - HTML content break
src = src.replace(
    '                <div style="font-size: 10pt; color: #666;">Professional Transportation & Event Services</div>',
    '                <div style="font-size: 10pt; color: #666;">Professional\n'
    "                Transportation & Event Services</div>",
    1,
)

# Line 378 - HTML: Reservation # line
src = src.replace(
    "                <strong>Reservation #:</strong> {charter_data.get('reserve_number', 'N/A')}<br>",
    "                <strong>Reservation #:</strong>\n"
    "                {charter_data.get('reserve_number', 'N/A')}<br>",
    1,
)

# Line 388 - HTML table row: Client Name
src = src.replace(
    "                    <tr><td><strong>Client Name:</strong></td><td>{charter_data.get('client_name', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Client Name:</strong></td>\n"
    "                    <td>{charter_data.get('client_name', 'N/A')}</td></tr>",
    1,
)

# Line 389 - HTML table row: Account Number
src = src.replace(
    "                    <tr><td><strong>Account Number:</strong></td><td>{charter_data.get('account_number', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Account Number:</strong></td>\n"
    "                  <td>{charter_data.get('account_number', 'N/A')}</td></tr>",
    1,
)

# Line 396 - HTML table row: Pickup Address
src = src.replace(
    "                    <tr><td><strong>Pickup Address:</strong></td><td>{charter_data.get('pickup_address', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Pickup Address:</strong></td>\n"
    "                  <td>{charter_data.get('pickup_address', 'N/A')}</td></tr>",
    1,
)

# Line 397 - HTML table row: Dropoff Address
src = src.replace(
    "                    <tr><td><strong>Dropoff Address:</strong></td><td>{charter_data.get('dropoff_address', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Dropoff Address:</strong></td>\n"
    "                  <td>{charter_data.get('dropoff_address', 'N/A')}</td></tr>",
    1,
)

# Line 398 - HTML table row: Passenger Count
src = src.replace(
    "                    <tr><td><strong>Passenger Count:</strong></td><td>{charter_data.get('passenger_count', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Passenger Count:</strong></td>\n"
    "                  <td>{charter_data.get('passenger_count', 'N/A')}</td></tr>",
    1,
)

# Line 399 - HTML table row: Vehicle Type
src = src.replace(
    "                    <tr><td><strong>Vehicle Type:</strong></td><td>{charter_data.get('vehicle_description', 'N/A')}</td></tr>",
    "                    <tr><td><strong>Vehicle Type:</strong></td>\n"
    "              <td>{charter_data.get('vehicle_description', 'N/A')}</td></tr>",
    1,
)

# Line 408 - HTML: rate cell
src = src.replace(
    '                        <td class="right amount">${charter_data.get(\'rate\', 0) or 0:.2f}</td>',
    '                        <td class="right amount">\n'
    "                        ${charter_data.get('rate', 0) or 0:.2f}</td>",
    1,
)

# Line 435 - HTML: special requirements
src = src.replace(
    "                <p>{charter_data.get('special_requirements', 'None specified') or 'None specified'}</p>",
    "                <p>{charter_data.get('special_requirements',\n"
    "                'None specified') or 'None specified'}</p>",
    1,
)

# Line 440 - HTML: payment instructions (151 chars)
src = src.replace(
    "                <p>{charter_data.get('payment_instructions', 'Payment due upon completion of service') or 'Payment due upon completion of service'}</p>",
    "                <p>{charter_data.get('payment_instructions',\n"
    "                'Payment due upon completion of service')\n"
    "                or 'Payment due upon completion of service'}</p>",
    1,
)

# Line 458 - HTML: generated-on line
src = src.replace(
    "                This document was generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>",
    "                This document was generated on\n"
    "                {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>",
    1,
)

# Line 587 - Python f-string CSV filename: extract vars
src = src.replace(
    "            from datetime import datetime\n"
    "\n"
    "            file_path, _ = QFileDialog.getSaveFileName(\n"
    "                self,\n"
    '                "Export Quote to CSV",\n'
    "                f\"Quote_{charter_data.get('reserve_number', 'export')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv\",",
    "            from datetime import datetime\n"
    "\n"
    '            _ts = datetime.now().strftime("%Y%m%d_%H%M%S")\n'
    '            _rn = charter_data.get("reserve_number", "export")\n'
    "            file_path, _ = QFileDialog.getSaveFileName(\n"
    "                self,\n"
    '                "Export Quote to CSV",\n'
    '                f"Quote_{_rn}_{_ts}.csv",',
    1,
)

# Line 669 - Python f-string DOCX filename: extract timestamp
src = src.replace(
    "            file_path, _ = QFileDialog.getSaveFileName(\n"
    "                self,\n"
    '                "Export Quote to Word",\n'
    "                f\"Quote_{reserve_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx\",",
    "            _ts = datetime.now().strftime(\"%Y%m%d_%H%M%S\")\n"
    "            file_path, _ = QFileDialog.getSaveFileName(\n"
    "                self,\n"
    '                "Export Quote to Word",\n'
    '                f"Quote_{reserve_num}_{_ts}.docx",',
    1,
)

p.write_text(src, encoding="utf-8")
try:
    ast.parse(src)
    print("AST_OK  quote_generator_widget.py")
except SyntaxError as e:
    print(f"AST_FAIL quote_generator_widget.py: {e}")
