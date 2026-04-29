"""Fix all 42 remaining E501 violations in charter_form_widget.py."""
import re, ast

SRC = 'desktop_app/charter_form_widget.py'
with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def indent_of(line):
    return ' ' * (len(line) - len(line.lstrip()))

fixes = {}

# --- 5945: docstring line 86 chars ---
# '        - NRR (Non-Refundable Retainer) is recorded as LIABILITY until used in charter\n'
# Split at a word boundary before col 80
fixes[5945] = (
    '        - NRR (Non-Refundable Retainer) is recorded as LIABILITY\n'
    '          until used in charter\n'
)

# --- 5947: docstring line 83 chars ---
# '          NOT GL Code: 4000 (Service Revenue) - only applied when charter completes\n'
fixes[5947] = (
    '          NOT GL Code: 4000 (Service Revenue) - only applied\n'
    '          when charter completes\n'
)

# --- 6127: SQL INSERT column list 128 chars ---
# '                            reserve_number, charter_date, pickup_time, passenger_count, notes, status, client_id, is_out_of_town\n'
fixes[6127] = (
    '                            reserve_number, charter_date,\n'
    '                            pickup_time, passenger_count,\n'
    '                            notes, status, client_id,\n'
    '                            is_out_of_town\n'
)

# --- 6768: continuation line 82 chars ---
# '                                    in self.customer_widget.client_combo.itemText(i)):\n'
# Already indented, just needs minor adjustment - can't be shorter without changing logic
# The line is part of a multiline if - let's check what indent is needed
fixes[6768] = (
    '                                    in self.customer_widget\n'
    '                                    .client_combo.itemText(i)):\n'
)

# --- 7139-7191: liability clause text += openings (confirmation letter) ---
# These all follow pattern: text += ("N. First part of long sentence "
# Fix: split the string content shorter

liability_fixes_conf = {
    7139: ('            text += ("1. Customer hereby verifies "\n'
           '                     "that the rental date, anticipated "\n'),
    7144: ('            text += ("2. Customer shall be liable "\n'
           '                     "for all damages to the limousine "\n'),
    7151: ('            text += ("3. Customer shall pay a service "\n'
           '                     "charge of $200.00 to clean any "\n'),
    7154: ('            text += ("4. Customer shall not open any "\n'
           '                     "emergency exits, including the "\n'),
    7157: ('            text += ("5. While the vehicle is in motion "\n'
           '                     "Customers shall refrain from "\n'),
    7160: ('            text += ("6. Arrow Limousine reserves the right, "\n'
           '                     "without any liability or "\n'),
    7167: ('            text += ("7. Arrow Limousine shall not be "\n'
           '                     "liable for any damages arising "\n'),
    7176: ('            text += ("8. Arrow Limousine shall not be "\n'
           '                     "the Bailee of any items left in "\n'),
    7181: ('            text += ("9. Customer must pay a "\n'
           '                     "NON-REFUNDABLE retainer equal to two hour "\n'),
    7185: ('            text += ("10. Customer hereby authorizes "\n'
           '                      "Arrow Limousine to charge the "\n'),
    7191: ('            text += ("By agreeing to the discounted rate, "\n'
           '                     "the Client waives any claims "\n'),
}
fixes.update(liability_fixes_conf)

# --- 7571: f-string continuation 83 chars ---
# '                            f" @ ${standby_rate:.2f}/hour = ${standby_cost:.2f}\\n")\n'
fixes[7571] = (
    '                            f" @ ${standby_rate:.2f}/hour"\n'
    '                            f" = ${standby_cost:.2f}\\n")\n'
)

# --- 7617-7669: liability clause text += openings (quote letter) ---
liability_fixes_quote = {
    7617: ('            text += ("1. Customer hereby verifies "\n'
           '                     "that the rental date, anticipated "\n'),
    7622: ('            text += ("2. Customer shall be liable "\n'
           '                     "for all damages to the limousine "\n'),
    7629: ('            text += ("3. Customer shall pay a service "\n'
           '                     "charge of $200.00 to clean any "\n'),
    7632: ('            text += ("4. Customer shall not open any "\n'
           '                     "emergency exits, including the "\n'),
    7635: ('            text += ("5. While the vehicle is in motion "\n'
           '                     "Customers shall refrain from "\n'),
    7638: ('            text += ("6. Arrow Limousine reserves the right, "\n'
           '                     "without any liability or "\n'),
    7645: ('            text += ("7. Arrow Limousine shall not be "\n'
           '                     "liable for any damages arising "\n'),
    7654: ('            text += ("8. Arrow Limousine shall not be "\n'
           '                     "the Bailee of any items left in "\n'),
    7659: ('            text += ("9. Customer must pay a "\n'
           '                     "NON-REFUNDABLE retainer equal to two hour "\n'),
    7663: ('            text += ("10. Customer hereby authorizes "\n'
           '                      "Arrow Limousine to charge the "\n'),
    7669: ('            text += ("By agreeing to the discounted rate, "\n'
           '                     "the Client waives any claims "\n'),
}
fixes.update(liability_fixes_quote)

# --- 7767: SQL COALESCE line 81 chars ---
# '                COALESCE(cl.company_name, cl.client_name, \'Unknown\') AS customer,\n'
fixes[7767] = (
    '                COALESCE(cl.company_name,\n'
    "                         cl.client_name, 'Unknown') AS customer,\n"
)

# --- 9287: tuple unpacking 82 chars ---
# 'first_seq, first_code, first_time, first_addr, first_notes = events[0]\n'
fixes[9287] = (
    '            (first_seq, first_code, first_time,\n'
    '             first_addr, first_notes) = events[0]\n'
)

# --- 9291: tuple unpacking 82 chars ---
# 'last_seq, last_code, last_time, last_addr, last_notes = events[-1]\n'
fixes[9291] = (
    '                (last_seq, last_code, last_time,\n'
    '                 last_addr, last_notes) = events[-1]\n'
)

# --- 9297: row_idx assignment with comment 92 chars ---
fixes[9297] = (
    '                row_idx = (\n'
    '                    self.route_table.rowCount() - 2)  # before last parent\n'
)

# --- 9345: ternary 90 chars ---
# "rate = self.dp_hourly_rate.value() if hasattr(self, 'dp_hourly_rate') else 0.0\n"
fixes[9345] = (
    "            rate = (\n"
    "                self.dp_hourly_rate.value()\n"
    "                if hasattr(self, 'dp_hourly_rate') else 0.0)\n"
)

# --- 9397: docstring line 82 chars ---
# '        """Populate the payments_table from charter_payments (fallback: payments).\n'
fixes[9397] = (
    '        """Populate the payments_table from charter_payments\n'
    '        (fallback: payments).\n'
)

# --- 9411: SQL SELECT line 82 chars (inside triple string) ---
# "SELECT amount, payment_method, payment_date, COALESCE(client_name, '')\n"
fixes[9411] = (
    "                SELECT amount, payment_method, payment_date,\n"
    "                       COALESCE(client_name, '')\n"
)

# --- 9486: tuple unpack call 84 chars ---
# 'base_desc, meta_type, meta_value = self._parse_description_metadata(\n'
fixes[9486] = (
    '                (base_desc, meta_type,\n'
    '                 meta_value) = self._parse_description_metadata(\n'
)

# --- 9501: long condition 102 chars ---
# '    charge_type == "service" or "service fee" in desc_lower or "charter charge" in desc_lower\n'
fixes[9501] = (
    '                    charge_type == "service"\n'
    '                    or "service fee" in desc_lower\n'
    '                    or "charter charge" in desc_lower\n'
)

# --- 9515: long if condition 109 chars ---
# '        if gratuity_amount is not None and gratuity_percent is None and charter_base_amount not in (\n'
fixes[9515] = (
    '            if (gratuity_amount is not None\n'
    '                    and gratuity_percent is None\n'
    '                    and charter_base_amount not in (\n'
)

# --- 9567: for loop with many vars 122 chars ---
# 'for bev_id, item_name, qty, unit_price, unit_cost, deposit, line_total_charged, line_cost, notes in beverages:\n'
fixes[9567] = (
    '            for (bev_id, item_name, qty, unit_price, unit_cost,\n'
    '                 deposit, line_total_charged, line_cost, notes) in beverages:\n'
)

# --- 9587: dict entry 102 chars ---
# "'gst_amount': GSTCalculator.calculate_gst(total_charged)[0] if total_charged else 0.0,\n"
fixes[9587] = (
    "                'gst_amount': (\n"
    "                    GSTCalculator.calculate_gst(total_charged)[0]\n"
    "                    if total_charged else 0.0),\n"
)

# --- 9588: dict entry 102 chars ---
# "'net_amount': GSTCalculator.calculate_gst(total_charged)[1] if total_charged else 0.0}\n"
fixes[9588] = (
    "                'net_amount': (\n"
    "                    GSTCalculator.calculate_gst(total_charged)[1]\n"
    "                    if total_charged else 0.0)}\n"
)

# --- 9598: f-string print 144 chars ---
fixes[9598] = (
    '                    print(\n'
    '                        f"{item[\'item_name\']:<40}"\n'
    '                        f" {item[\'quantity\']:<5}"\n'
    "                        f\" ${item['unit_price_charged']:<11.2f}\"\n"
    "                        f\" ${item['line_amount_charged']:<11.2f}\")\n"
)

# --- 9605: print statement 89 chars ---
fixes[9605] = (
    "            print(\n"
    "                \"💡 Tip: Click 'Edit Beverages' button\"\n"
    '                " to modify quantities or items\\n")\n'
)

# Apply fixes in reverse order (to preserve line numbers)
applied = 0
for lineno in sorted(fixes.keys(), reverse=True):
    idx = lineno - 1
    if idx < len(lines):
        old = lines[idx]
        new = fixes[lineno]
        lines[idx] = new
        applied += 1
    else:
        print(f"LINE {lineno} OUT OF RANGE (file has {len(lines)} lines)")

print(f"Applied {applied} fixes")

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Verify
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 4), min(len(src_lines), e.lineno + 4)):
        marker = " >>> " if j == e.lineno - 1 else "     "
        print(f"{marker}{j+1}: {src_lines[j][:100]}")
