#!/usr/bin/env python3
"""Fix all remaining E501 violations in charter_form_widget.py.

Strategy: process lines top-to-bottom, building a new list of lines.
When a violation is found, output a fixed version.
"""
import re

SRC = r'l:\limo\desktop_app\charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []  # new lines list
i = 0     # current index (0-based)
changed = 0


def ind(n):
    """Return n spaces."""
    return ' ' * n


def wrap_str_continuation(line):
    """For a `text += ("..."` line, if it's too long, try shorter wrap."""
    # patterns:
    # `            text += ("CONTENT"` -> 12 + 10 + content + 1 = 23+N
    # continuation `                     "CONTENT"` -> 21 + 1 + content + 1 = 23+N
    pass


# ---------------------------------------------------------------------------
# Build a lookup dict: original 1-based line number -> replacement lines list
# This avoids re-processing shifted lines.
# We'll build it by going through known violations.
# ---------------------------------------------------------------------------

# Each entry: { line_number_1based: [replacement_line, ...] }
# Where replacement lines include their newlines.
fixes = {}


def lstrip_count(s):
    return len(s) - len(s.lstrip())


def get_indent(line):
    n = lstrip_count(line.rstrip('\n'))
    return ' ' * n


def too_long(line):
    return len(line.rstrip('\n')) > 79


def simple_wrap_at_comma(line, extra_indent=0):
    """Try to wrap a long SQL/argument line at a comma."""
    stripped = line.rstrip('\n')
    indent = lstrip_count(stripped)
    ind_str = ' ' * (indent + extra_indent)
    # find last comma before col 79
    if len(stripped) <= 79:
        return [line]
    # find a comma near position 75 to wrap at
    content = stripped[indent:]
    # Find last comma before col 79
    max_pos = 79 - indent - 1  # target split position within content
    split_at = content.rfind(',', 0, max_pos)
    if split_at < 0:
        return [line]  # can't easily wrap
    part1 = content[:split_at + 1]  # include the comma
    part2 = content[split_at + 1:].lstrip()
    result = [' ' * indent + part1 + '\n',
              ind_str + part2 + '\n']
    return result


def wrap_ternary(line):
    """Wrap `x = val if cond else default` to multi-line."""
    stripped = line.rstrip('\n')
    indent_n = lstrip_count(stripped)
    ind_str = ' ' * indent_n
    # find the assignment
    m = re.match(r'^(\s*\w[\w.()\'\" ]*?)\s*=\s*(.+)\s+if\s+(.+)\s+else\s+(.+)$',
                 stripped)
    if m:
        lhs = m.group(1)
        val = m.group(2)
        cond = m.group(3)
        default = m.group(4)
        new = [f'{ind_str}{lhs} = (\n',
               f'{ind_str}    {val}\n',
               f'{ind_str}    if {cond} else {default})\n']
        return new
    return [line]


# Now process line by line ---------------------------------------------------

while i < len(lines):
    line = lines[i]
    stripped = line.rstrip('\n')
    ln = i + 1  # 1-based

    if not too_long(line):
        out.append(line)
        i += 1
        continue

    indent_n = lstrip_count(stripped)
    ind_str = ' ' * indent_n
    content = stripped[indent_n:]

    handled = False

    # -------------------------------------------------------------------
    # Pattern: nrr_amount = self.nrr_received.value() if hasattr(...)
    # -------------------------------------------------------------------
    if re.match(r"\s+nrr_amount = self\.nrr_received\.value\(\) if hasattr\(self,",
                stripped):
        out.append(f'{ind_str}nrr_amount = (\n')
        out.append(f'{ind_str}    self.nrr_received.value()\n')
        out.append(f'{ind_str}    if hasattr(self, \'nrr_received\') else 0.0)\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: if self.charter_status_combo.currentText() == "Cancelled"
    # -------------------------------------------------------------------
    elif re.match(r'\s+if self\.charter_status_combo\.currentText\(\) == "Cancelled"',
                  stripped):
        out.append(f'{ind_str}if (self.charter_status_combo.currentText()\n')
        out.append(f'{ind_str}        == "Cancelled" and nrr_amount > 0):\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "Drop-off cannot be before pickup. Adjust the date/time..."
    # -------------------------------------------------------------------
    elif '"Drop-off cannot be before pickup. Adjust the date/time (multi-day allowed).")' in stripped:
        # This is a continuation line inside QMessageBox.warning(...)
        out.append(f'{ind_str}"Drop-off cannot be before pickup. "\n')
        out.append(f'{ind_str}"Adjust the date/time (multi-day allowed).")\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: self, "Success", f"Charter #...
    # -------------------------------------------------------------------
    elif re.match(r'\s+self, "Success", f"Charter #', stripped):
        m = re.match(r'(\s+)(self, "Success", f"Charter #(.+)")\)', stripped)
        if m:
            sp = m.group(1)
            rest = m.group(3)
            out.append(f'{sp}self, "Success",\n')
            out.append(f'{sp}f"Charter #{rest}")\n')
            handled = True

    # -------------------------------------------------------------------
    # Pattern: long SQL SELECT ... FROM charters WHERE reserve_number
    # -------------------------------------------------------------------
    elif 'SELECT MAX(CAST(reserve_number AS INTEGER)) FROM charters WHERE' in stripped:
        out.append(f'{ind_str}"SELECT MAX(CAST(reserve_number AS INTEGER))"\n')
        out.append(f"{ind_str}\" FROM charters WHERE reserve_number ~ '^\\\\d+$'\"\n")
        handled = True

    # -------------------------------------------------------------------
    # Pattern: reserve_number, charter_date, pickup_time, passenger_count,
    #           notes, status, client_id, is_out_of_town, charter_data
    # Two versions: with and without is_out_of_town
    # -------------------------------------------------------------------
    elif ('reserve_number, charter_date, pickup_time, passenger_count, notes, status, '
          'client_id, is_out_of_town, charter_data') in stripped:
        out.append(
            f'{ind_str}reserve_number, charter_date, pickup_time,\n')
        out.append(
            f'{ind_str}passenger_count, notes, status,\n')
        out.append(
            f'{ind_str}client_id, is_out_of_town, charter_data\n')
        handled = True

    elif ('reserve_number, charter_date, pickup_time, passenger_count, notes, status, '
          'client_id, charter_data') in stripped:
        out.append(
            f'{ind_str}reserve_number, charter_date, pickup_time,\n')
        out.append(
            f'{ind_str}passenger_count, notes, status,\n')
        out.append(
            f'{ind_str}client_id, charter_data\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: self.charter_id, reserve_num, self._escrow_nrr_applied, cur)
    # -------------------------------------------------------------------
    elif re.match(r'\s+self\.charter_id, reserve_num, self\._escrow_nrr_applied, cur\)',
                  stripped):
        out.append(f'{ind_str}self.charter_id, reserve_num,\n')
        out.append(f'{ind_str}self._escrow_nrr_applied, cur)\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: 'current_inspection_form_path') and self.current_inspection...
    # -------------------------------------------------------------------
    elif ("'current_inspection_form_path') and self.current_inspection_form_path:"
          in stripped):
        out.append(f"{ind_str}'current_inspection_form_path')\n")
        out.append(f"{ind_str}and self.current_inspection_form_path:\n")
        handled = True

    # -------------------------------------------------------------------
    # Pattern: self.current_inspection_form_path, os.path.dirname(__file__))
    # -------------------------------------------------------------------
    elif ('self.current_inspection_form_path, os.path.dirname(__file__))'
          in stripped):
        out.append(f'{ind_str}self.current_inspection_form_path,\n')
        out.append(f'{ind_str}os.path.dirname(__file__))\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: jsonb_set(charter_data, '{inspection_form_path}', %s::jsonb)
    # -------------------------------------------------------------------
    elif "jsonb_set(charter_data, '{inspection_form_path}', %s::jsonb)" in stripped:
        out.append(
            f"{ind_str}\"jsonb_set(charter_data, \"\n"
            f"{ind_str}\"{{'inspection_form_path'}}, %s::jsonb)\"\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: very long QMessageBox "New charter created!" message
    # -------------------------------------------------------------------
    elif 'f"New charter created!' in stripped and len(stripped) > 79:
        # Find the f-string content and break it
        m = re.match(r'(\s+)(f"New charter created!.+)', stripped)
        if m:
            sp = m.group(1)
            # Build shorter version
            out.append(f'{sp}f"New charter created!\\n\\n"\n')
            out.append(f'{sp}f"Reserve #: {{reserve_num}}\\n"\n')
            out.append(f'{sp}f"Charter ID: {{self.charter_id}}"\n')
            handled = True

    # -------------------------------------------------------------------
    # Pattern: f"Failed to save charter:\n\n{e.diag...}"
    # -------------------------------------------------------------------
    elif 'Failed to save charter:' in stripped and 'hasattr(e,' in stripped:
        out.append(f'{ind_str}f"Failed to save charter:\\n\\n"\n')
        out.append(f"{ind_str}f\"{{e.diag.message_primary if hasattr(e, 'diag') else str(e)}}\"\n")
        handled = True

    # -------------------------------------------------------------------
    # Pattern: GL INSERT column list
    # (charter_id, reserve_number, gl_code, account_name, amount, entry_type,
    # -------------------------------------------------------------------
    elif re.match(r'\s+\(charter_id, reserve_number, gl_code, account_name, amount, entry_type,',
                  stripped):
        out.append(f'{ind_str}(charter_id, reserve_number, gl_code,\n')
        out.append(f'{ind_str} account_name, amount, entry_type,\n')
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f'NRR applied from escrow (cancelled reserve #{from_reserve}'
    # -------------------------------------------------------------------
    elif "f'NRR applied from escrow (cancelled reserve #{from_reserve}" in stripped:
        out.append(
            f"{ind_str}f'NRR applied from escrow '\n"
            f"{ind_str}f'(cancelled reserve #{{from_reserve}})'))\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"✅ GL coded escrow NRR: ... from cancelled reserve
    # -------------------------------------------------------------------
    elif '✅ GL coded escrow NRR:' in stripped:
        out.append(
            f'{ind_str}f"✅ GL coded escrow NRR: ${{nrr_amount:.2f}}"\n'
            f'{ind_str}f" from cancelled reserve #{{from_reserve}}")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "SELECT reserve_number FROM charters WHERE charter_id = %s"
    # -------------------------------------------------------------------
    elif '"SELECT reserve_number FROM charters WHERE charter_id = %s",' in stripped:
        out.append(
            f'{ind_str}"SELECT reserve_number FROM charters"\n'
            f'{ind_str}f" WHERE charter_id = %s", (charter_id,))\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: appt.Subject = f"Reserve {reserve_number} - ...
    # -------------------------------------------------------------------
    elif "appt.Subject = f\"Reserve {reserve_number} - {customer_name" in stripped:
        out.append(
            f"{ind_str}appt.Subject = (\n"
            f"{ind_str}    f\"Reserve {{reserve_number}} - \"\n"
            f"{ind_str}    f\"{{customer_name or 'Charter'}}\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SQL SELECT with c.passenger_count, c.notes, c.status...
    # -------------------------------------------------------------------
    elif ('c.passenger_count, c.notes, c.status, c.client_id, c.charter_data'
          in stripped):
        out.append(
            f'{ind_str}c.passenger_count, c.notes,\n'
            f'{ind_str}c.status, c.client_id, c.charter_data\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: reserve_number, charter_date, pickup_time, ... = row (unpack)
    # -------------------------------------------------------------------
    elif re.match(
        r'\s+reserve_number, charter_date, pickup_time, passenger_count, notes, status, client_id, charter_data_json = row',
        stripped
    ):
        out.append(
            f'{ind_str}(reserve_number, charter_date, pickup_time,\n'
            f'{ind_str} passenger_count, notes, status,\n'
            f'{ind_str} client_id, charter_data_json) = row\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: charter_data_json, dict) else json.loads(charter_data_json)
    # (appears twice)
    # -------------------------------------------------------------------
    elif 'charter_data_json, dict) else json.loads(charter_data_json)' in stripped:
        # This is a continuation of: isinstance(
        #    charter_data_json, dict) else json.loads(charter_data_json)
        out.append(
            f'{ind_str}charter_data_json, dict)\n'
            f'{ind_str}else json.loads(charter_data_json)\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: self.pickup_datetime.dateTime().addSecs(2 * 60 * 60))
    # -------------------------------------------------------------------
    elif 'self.pickup_datetime.dateTime().addSecs(2 * 60 * 60))' in stripped:
        out.append(
            f'{ind_str}self.pickup_datetime.dateTime()\n'
            f'{ind_str}.addSecs(2 * 60 * 60))\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: driver_hourly_rate, driver_gratuity, approved_gratuity
    # -------------------------------------------------------------------
    elif re.match(r'\s+driver_hourly_rate, driver_gratuity, approved_gratuity',
                  stripped):
        out.append(
            f'{ind_str}driver_hourly_rate,\n'
            f'{ind_str}driver_gratuity, approved_gratuity\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SELECT client_id, client_name, primary_phone, email, address_line1, city
    # -------------------------------------------------------------------
    elif 'SELECT client_id, client_name, primary_phone, email, address_line1, city' in stripped:
        out.append(
            f'{ind_str}SELECT client_id, client_name,\n'
            f'{ind_str}primary_phone, email, address_line1, city\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SELECT client_id, company_name, primary_phone, email, address_line1
    # -------------------------------------------------------------------
    elif 'SELECT client_id, company_name, primary_phone, email, address_line1' in stripped:
        out.append(
            f'{ind_str}SELECT client_id, company_name,\n'
            f'{ind_str}primary_phone, email, address_line1\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: if str(client_id) in self.customer_widget.client_combo.itemData(
    # -------------------------------------------------------------------
    elif re.match(r'\s+if str\(client_id\) in self\.customer_widget\.client_combo\.itemData\(',
                  stripped):
        out.append(
            f'{ind_str}if (str(client_id)\n'
            f'{ind_str}        in self.customer_widget.client_combo.itemData(\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: i, Qt.ItemDataRole.UserRole) or client_name in ...itemText(i)
    # -------------------------------------------------------------------
    elif ('i, Qt.ItemDataRole.UserRole) or client_name in '
          'self.customer_widget.client_combo.itemText(i):') in stripped:
        out.append(
            f'{ind_str}        i, Qt.ItemDataRole.UserRole)\n'
            f'{ind_str}        or client_name\n'
            f'{ind_str}        in self.customer_widget.client_combo.itemText(i)):\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: """Check if client has NRR in escrow ...""" docstring
    # -------------------------------------------------------------------
    elif '"""Check if client has NRR in escrow and offer to apply to new charter"""' in stripped:
        out.append(
            f'{ind_str}"""Check if client has NRR in escrow and\n'
            f'{ind_str}offer to apply to new charter"""\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"Customer {client_name} has ${nrr_amount:.2f} NRR in escrow\n"
    # -------------------------------------------------------------------
    elif 'f"Customer {client_name} has ${nrr_amount:.2f} NRR in escrow\\n"' in stripped:
        out.append(
            f'{ind_str}f"Customer {{client_name}} has "\n'
            f'{ind_str}f"${{nrr_amount:.2f}} NRR in escrow\\n"\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"✅ Applied ${nrr_amount:.2f} from escrow (reserve #{from_reserve})\n"
    # -------------------------------------------------------------------
    elif '✅ Applied ${nrr_amount:.2f} from escrow' in stripped:
        out.append(
            f'{ind_str}f"✅ Applied ${{nrr_amount:.2f}} from escrow"\n'
            f'{ind_str}f" (reserve #{{from_reserve}})\\n"\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "This will be GL coded as a payment when you save the new charter."
    # -------------------------------------------------------------------
    elif '"This will be GL coded as a payment when you save the new charter.")' in stripped:
        out.append(
            f'{ind_str}"This will be GL coded as a payment"\n'
            f'{ind_str}"when you save the new charter.")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "MM/dd/yyyy") if hasattr(self, "charter_date_to")
    # -------------------------------------------------------------------
    elif ('"MM/dd/yyyy") if hasattr(self, "charter_date_to") else charter_date_from'
          in stripped):
        out.append(
            f'{ind_str}"MM/dd/yyyy")\n'
            f'{ind_str}if hasattr(self, "charter_date_to")\n'
            f'{ind_str}else charter_date_from\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: assigned_vehicle = self.vehicle_combo.currentText() if hasattr(self,
    # -------------------------------------------------------------------
    elif re.match(r'\s+assigned_vehicle = self\.vehicle_combo\.currentText\(\) if hasattr\(self,',
                  stripped):
        out.append(f'{ind_str}assigned_vehicle = (\n')
        out.append(f'{ind_str}    self.vehicle_combo.currentText()\n')
        out.append(f'{ind_str}    if hasattr(self,\n')
        # consume next line too
        next_line = lines[i + 1] if i + 1 < len(lines) else ''
        if '"vehicle_combo") else ""' in next_line:
            out.append(f'{ind_str}    "vehicle_combo") else "")\n')
            i += 1  # skip next line
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "driver_combo") else "" continuation
    # -------------------------------------------------------------------
    elif re.match(r'\s+"driver_combo"\) else ""', stripped):
        # This is a continuation - the previous line should have been fixed
        # Check if previous output line already handled this
        out.append(
            f'{ind_str}    if hasattr(self, "driver_combo") else "")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: (f"Beverage: {item_name} x{qty}", "bev", line_amount))
    # -------------------------------------------------------------------
    elif '(f"Beverage: {item_name} x{qty}", "bev", line_amount))' in stripped:
        out.append(
            f'{ind_str}(f"Beverage: {{item_name}} x{{qty}}",\n'
            f'{ind_str} "bev", line_amount))\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: client_notes = self.client_notes_input.toPlainText().strip() if hasattr(self,
    # -------------------------------------------------------------------
    elif re.match(r'\s+client_notes = self\.client_notes_input\.toPlainText\(\)\.strip\(\) if hasattr\(self,',
                  stripped):
        out.append(f'{ind_str}client_notes = (\n')
        out.append(f'{ind_str}    self.client_notes_input.toPlainText().strip()\n')
        # consume next line
        next_line = lines[i + 1] if i + 1 < len(lines) else ''
        nstripped = next_line.strip()
        if nstripped.startswith("'client_notes_input')"):
            out.append(f"{ind_str}    if hasattr(self, 'client_notes_input')\n")
            # get the else part
            m2 = re.search(r"else (.+)$", nstripped)
            if m2:
                out.append(f'{ind_str}    else {m2.group(1)})\n')
            i += 1
        handled = True

    # -------------------------------------------------------------------
    # Pattern: stop_time = time_item.text().strip() if time_item and...
    # -------------------------------------------------------------------
    elif 'stop_time = time_item.text().strip() if time_item and time_item.text() else ""' in stripped:
        out.append(
            f'{ind_str}stop_time = (\n'
            f'{ind_str}    time_item.text().strip()\n'
            f'{ind_str}    if time_item and time_item.text() else "")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"{desc:<66.66} {item_type:<8.8} ${amount:>12.2f}\n"
    # -------------------------------------------------------------------
    elif 'text += f"{desc:<66.66}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"{{desc:<66.66}} {{item_type:<8.8}}"\n'
            f'{ind_str}    f" ${{amount:>12.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Subtotal (before GST): ...
    # -------------------------------------------------------------------
    elif "text += f\"Subtotal (before GST): " in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"Subtotal (before GST): {{'':< 46}} \"\n"
            f'{ind_str}    f"${{subtotal_before_gst:>12.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"NRR Received (booking fee): ...
    # -------------------------------------------------------------------
    elif 'text += f"NRR Received (booking fee):' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"NRR Received (booking fee): {{'':< 38}} \"\n"
            f'{ind_str}    f"${{nrr_amount:>12.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Other Payments Received: ...
    # -------------------------------------------------------------------
    elif 'text += f"Other Payments Received:' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"Other Payments Received: {{'':< 40}} \"\n"
            f'{ind_str}    f"${{payments_total:>12.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: reserve_num = self.customer_widget.reserve_input.text() or "QUOTE-NEW"
    # -------------------------------------------------------------------
    elif 'reserve_num = self.customer_widget.reserve_input.text() or "QUOTE-NEW"' in stripped:
        out.append(
            f'{ind_str}reserve_num = (\n'
            f'{ind_str}    self.customer_widget.reserve_input.text()\n'
            f'{ind_str}    or "QUOTE-NEW")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: vehicle_type_display = vehicle_type if vehicle_type else "Luxury SUV"
    # -------------------------------------------------------------------
    elif 'vehicle_type_display = vehicle_type if vehicle_type else "Luxury SUV"' in stripped:
        out.append(
            f'{ind_str}vehicle_type_display = vehicle_type or "Luxury SUV"\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text = f"{datetime.now().strftime('%m/%d/%Y')}\t...\tYour Quote Number is {reserve_num}.\n"
    # -------------------------------------------------------------------
    elif "datetime.now().strftime('%m/%d/%Y')" in stripped and 'Your Quote Number is' in stripped:
        out.append(
            f"{ind_str}text = (\n"
            f"{ind_str}    f\"{{datetime.now().strftime('%m/%d/%Y')}}\"\n"
            f'{ind_str}    f"\\t\\t\\t\\t\\tYour Quote Number is {{reserve_num}}.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "\t...\t\tPlease reference this number when contacting us.\n\n"
    # -------------------------------------------------------------------
    elif 'Please reference this number when contacting us.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "\\t\\t\\t\\t\\t\\t\\t"\n'
            f'{ind_str}    "Please reference this number when contacting us.\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "Thank you for your interest in Arrow Limousine & Sedan Services Ltd.\n\n"
    # -------------------------------------------------------------------
    elif ('text += "Thank you for your interest in Arrow Limousine & Sedan Services Ltd.'
          in stripped):
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "Thank you for your interest in "\n'
            f'{ind_str}    "Arrow Limousine & Sedan Services Ltd.\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += ("We are pleased to provide you with the following pricing options "
    # -------------------------------------------------------------------
    elif ('text += ("We are pleased to provide you with the following pricing options'
          in stripped):
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "We are pleased to provide you with "\n'
            f'{ind_str}    "the following pricing options "\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Date for Service: {self.charter_date.getDate()...
    # -------------------------------------------------------------------
    elif "text += f\"Date for Service: {self.charter_date.getDate()." in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"Date for Service: \"\n"
            f"{ind_str}    f\"{{self.charter_date.getDate().toString('MM/dd/yyyy')}}\\n\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: 'out_of_town_checkbox') and self.out_of_town_checkbox.isChecked()
    # -------------------------------------------------------------------
    elif ("'out_of_town_checkbox') and self.out_of_town_checkbox.isChecked():"
          in stripped):
        out.append(
            f"{ind_str}'out_of_town_checkbox')\n"
            f"{ind_str}and self.out_of_town_checkbox.isChecked()):\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"This option charges ${hourly_rate:.2f} for each hour of service.\n"
    # -------------------------------------------------------------------
    elif ('text += f"This option charges ${hourly_rate:.2f} for each hour of service'
          in stripped):
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"This option charges ${{hourly_rate:.2f}}"\n'
            f'{ind_str}    f" for each hour of service.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Minimum {estimated_hours} hours. Extra time billed at same hourly rate
    # -------------------------------------------------------------------
    elif 'text += f"Minimum {estimated_hours} hours.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Minimum {{estimated_hours}} hours. "\n'
            f'{ind_str}    f"Extra time billed at same hourly rate.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Package: {package_hours} hours for ${package_rate:.2f}\n"
    # -------------------------------------------------------------------
    elif 'text += f"Package: {package_hours} hours for ${package_rate:.2f}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Package: {{package_hours}} hours"\n'
            f'{ind_str}    f" for ${{package_rate:.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Extra Time: {extra_hours} hours @ ${extra_time_rate:.2f}/hour = $
    # -------------------------------------------------------------------
    elif 'text += f"Extra Time: {extra_hours} hours @' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Extra Time: {{extra_hours}} hours"\n'
            f'{ind_str}    f" @ ${{extra_time_rate:.2f}}/hour"\n'
            f'{ind_str}    f" = ${{extra_cost:.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"This package includes {package_hours} hours of service.\n"
    # -------------------------------------------------------------------
    elif 'text += f"This package includes {package_hours} hours of service' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"This package includes {{package_hours}}"\n'
            f'{ind_str}    f" hours of service.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Additional time beyond {package_hours} hours: ${extra_time_rate:.2f}/h
    # -------------------------------------------------------------------
    elif 'text += f"Additional time beyond {package_hours}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Additional time beyond {{package_hours}} hours: "\n'
            f'{ind_str}    f"${{extra_time_rate:.2f}}/hour.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Free Time: {split_run_before} hours before + ...
    # -------------------------------------------------------------------
    elif 'text += f"Free Time: {split_run_before} hours before' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Free Time: {{split_run_before}} hours before"\n'
            f'{ind_str}    f" + {{split_run_after}} hours after event\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Driver Standby/Waiting: {standby_hours} hours @ ...
    # -------------------------------------------------------------------
    elif 'text += f"Driver Standby/Waiting: {standby_hours}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Driver Standby/Waiting: {{standby_hours}} hours"\n'
            f'{ind_str}    f" @ ${{standby_rate:.2f}}/hour = ${{standby_cost:.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "Service within free time - no standby charge\n"  (col 80)
    # -------------------------------------------------------------------
    elif 'text += "Service within free time - no standby charge' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "Service within free time"\n'
            f'{ind_str}    " - no standby charge\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Ideal for events: {split_run_before}hr pickup + event + ...
    # -------------------------------------------------------------------
    elif 'text += f"Ideal for events: {split_run_before}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Ideal for events: {{split_run_before}}hr pickup"\n'
            f'{ind_str}    f" + event + {{split_run_after}}hr return\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Driver waits during event. Standby time charged at ...
    # -------------------------------------------------------------------
    elif 'text += f"Driver waits during event. Standby time charged at' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"Driver waits during event. "\n'
            f'{ind_str}    f"Standby time charged at ${{standby_rate:.2f}}/hr.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += ("• A NON-REFUNDABLE deposit equal to two hour vehicle rate is "
    # -------------------------------------------------------------------
    elif 'text += ("• A NON-REFUNDABLE deposit equal to two hour vehicle rate is' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• A NON-REFUNDABLE deposit equal to"\n'
            f'{ind_str}    " two hour vehicle rate is required.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += ("• We recommend 15% gratuity (automatically applied unless "
    # -------------------------------------------------------------------
    elif 'text += ("• We recommend 15% gratuity' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• We recommend 15% gratuity"\n'
            f'{ind_str}    " (automatically applied unless declined).\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "• Cancellations must be made 24 hours prior to service time\n\n"
    # -------------------------------------------------------------------
    elif 'text += "• Cancellations must be made 24 hours prior to service time' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• Cancellations must be made 24 hours"\n'
            f'{ind_str}    " prior to service time\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "To book, please contact us with your preferred option.\n\n"
    # -------------------------------------------------------------------
    elif 'text += "To book, please contact us with your preferred option.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "To book, please contact us"\n'
            f'{ind_str}    " with your preferred option.\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "Thank you for considering Arrow Limousine & Sedan Services Ltd.\n"
    # -------------------------------------------------------------------
    elif 'text += "Thank you for considering Arrow Limousine & Sedan Services Ltd.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "Thank you for considering "\n'
            f'{ind_str}    "Arrow Limousine & Sedan Services Ltd.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: """Generate printable airport pickup sign with Arrow Limousine branding"""
    # -------------------------------------------------------------------
    elif '"""Generate printable airport pickup sign with Arrow Limousine branding"""' in stripped:
        out.append(
            f'{ind_str}"""Generate printable airport pickup sign\n'
            f'{ind_str}with Arrow Limousine branding"""\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: Long SQL SELECT in beverage / run sheet queries
    # (c.charter_id, c.reserve_number, COALESCE...)
    # -------------------------------------------------------------------
    elif ("SELECT c.charter_id, c.reserve_number, COALESCE(" in stripped):
        out.append(
            f"{ind_str}SELECT c.charter_id, c.reserve_number,\n"
            f"{ind_str}COALESCE(cl.company_name, cl.client_name, 'Unknown') AS customer,\n"
        )
        handled = True

    elif ("c.primary_phone, c.email, c.charter_date, c.pickup_time, c.total_amount_due,"
          in stripped):
        out.append(
            f"{ind_str}c.primary_phone, c.email,\n"
            f"{ind_str}c.charter_date, c.pickup_time,\n"
            f"{ind_str}c.total_amount_due,\n"
        )
        handled = True

    elif ('charter_id, reserve, customer, phone, email, charter_date, pickup_time, '
          'total_due, paid,') in stripped:
        out.append(
            f'{ind_str}(charter_id, reserve, customer, phone, email,\n'
            f'{ind_str} charter_date, pickup_time, total_due, paid,\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"{'Subtotal (before GST)':<60} ...
    # -------------------------------------------------------------------
    elif "text += f\"{" in stripped and "'Subtotal (before GST)'" in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"{{' Subtotal (before GST)':<60}}\"\n"
            f'{ind_str}    f" {{\'\'<6}} ${{subtotal:>18.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "• Accepted methods: Cash, Check, Credit Card, Bank Transfer\n"
    # -------------------------------------------------------------------
    elif 'text += "• Accepted methods: Cash, Check, Credit Card, Bank Transfer' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• Accepted methods: Cash, Check,"\n'
            f'{ind_str}    " Credit Card, Bank Transfer\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "• Late payment may result in service holds on future bookings\n"
    # -------------------------------------------------------------------
    elif 'text += "• Late payment may result in service holds' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• Late payment may result in"\n'
            f'{ind_str}    " service holds on future bookings\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "• Cancellations must be made 24 hours in advance for refund\n\n"
    # -------------------------------------------------------------------
    elif 'text += "• Cancellations must be made 24 hours in advance for refund' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "• Cancellations must be made 24 hours"\n'
            f'{ind_str}    " in advance for refund\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "For questions, contact: info@arrowlimo.ca...
    # -------------------------------------------------------------------
    elif 'text += "For questions, contact: info@arrowlimo.ca' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "For questions, contact: "\n'
            f'{ind_str}    "info@arrowlimo.ca or (780) 555-1234\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SELECT id, item_name, quantity, unit_price_charged, unit_our_cost,
    # -------------------------------------------------------------------
    elif 'SELECT id, item_name, quantity, unit_price_charged, unit_our_cost,' in stripped:
        out.append(
            f'{ind_str}SELECT id, item_name, quantity,\n'
            f'{ind_str}unit_price_charged, unit_our_cost,\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: deposit_per_unit, line_amount_charged, line_cost, notes (continuation)
    # -------------------------------------------------------------------
    elif re.match(r'\s+deposit_per_unit, line_amount_charged, line_cost, notes$', stripped):
        out.append(
            f'{ind_str}deposit_per_unit,\n'
            f'{ind_str}line_amount_charged, line_cost, notes\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: unit_price_charged, unit_our_cost, deposit_per_unit, notes, created_at, updated
    # -------------------------------------------------------------------
    elif 'unit_price_charged, unit_our_cost, deposit_per_unit, notes, created_at, updated' in stripped:
        out.append(
            f'{ind_str}unit_price_charged, unit_our_cost,\n'
            f'{ind_str}deposit_per_unit, notes, created_at, updated_at\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: not self.separate_beverage_checkbox.isChecked() or not self.beverage_cart_data
    # -------------------------------------------------------------------
    elif ('not self.separate_beverage_checkbox.isChecked() or '
          'not self.beverage_cart_data:') in stripped:
        out.append(
            f'{ind_str}not self.separate_beverage_checkbox.isChecked()\n'
            f'{ind_str}or not self.beverage_cart_data):\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: """Print client beverage list with itemized pricing, GST, and totals."""
    # -------------------------------------------------------------------
    elif '"""Print client beverage list with itemized pricing, GST, and totals."""' in stripped:
        out.append(
            f'{ind_str}"""Print client beverage list with\n'
            f'{ind_str}itemized pricing, GST, and totals."""\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: """Print driver manifest with checkboxes and line totals for load verification."""
    # -------------------------------------------------------------------
    elif '"""Print driver manifest with checkboxes and line totals for load verification."""' in stripped:
        out.append(
            f'{ind_str}"""Print driver manifest with checkboxes\n'
            f'{ind_str}and line totals for load verification."""\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Deposit included: ${totals['deposit_total']:.2f}\n"
    # -------------------------------------------------------------------
    elif "text += f\"Deposit included:" in stripped and "deposit_total" in stripped:
        out.append(
            f"{ind_str}text += (\n"
            f"{ind_str}    f\"Deposit included:       \"\n"
            f"{ind_str}    f\"${{totals['deposit_total']:.2f}}\\n\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "\nDriver Name (Print): _________________________________\n"
    # -------------------------------------------------------------------
    elif 'text += "\\nDriver Name (Print):' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "\\nDriver Name (Print): "\n'
            f'{ind_str}    "_________________________________\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: """Normalize beverage cart rows from either in-memory cart or DB snapshot payloads."""
    # -------------------------------------------------------------------
    elif '"""Normalize beverage cart rows from either in-memory cart or DB snapshot payloads."""' in stripped:
        out.append(
            f'{ind_str}"""Normalize beverage cart rows from\n'
            f'{ind_str}either in-memory cart or DB snapshot payloads."""\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"${row['unit_price']:>9.2f} ${row['line_gst']:>9.2f} ${row['line_total']:>11.2f}\n"
    # -------------------------------------------------------------------
    elif "row['unit_price']" in stripped and "row['line_gst']" in stripped:
        out.append(
            f"{ind_str}f\"${{row['unit_price']:>9.2f}}\"\n"
            f"{ind_str}f\" ${{row['line_gst']:>9.2f}}\"\n"
            f"{ind_str}f\" ${{row['line_total']:>11.2f}}\\n\"\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"Deposit/Recycle: ${totals['deposit_total']:>11.2f}\n"
    # -------------------------------------------------------------------
    elif "text += f\"Deposit/Recycle:" in stripped and "deposit_total" in stripped:
        out.append(
            f"{ind_str}text += (\n"
            f"{ind_str}    f\"Deposit/Recycle:      \"\n"
            f"{ind_str}    f\"${{totals['deposit_total']:>11.2f}}\\n\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html = "<html><body><table border='1' cellpadding='10' style='width:100%;'>"
    # -------------------------------------------------------------------
    elif "html = \"<html><body><table border='1' cellpadding='10'" in stripped:
        out.append(
            f"{ind_str}html = (\n"
            f"{ind_str}    \"<html><body>\"\n"
            f"{ind_str}    \"<table border='1' cellpadding='10' style='width:100%;'>\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html += "<tr><th>Item</th><th>Qty</th><th>Price</th><th>GST</th><th>Total</th></tr>"
    # -------------------------------------------------------------------
    elif 'html += "<tr><th>Item</th><th>Qty</th>' in stripped:
        out.append(
            f'{ind_str}html += (\n'
            f'{ind_str}    "<tr><th>Item</th><th>Qty</th>"\n'
            f'{ind_str}    "<th>Price</th><th>GST</th><th>Total</th></tr>")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html += f"<tr><td colspan='3'><b>Deposit/Recycle Fees</b></td>...
    # -------------------------------------------------------------------
    elif "html += f\"<tr><td colspan='3'><b>Deposit/Recycle" in stripped:
        out.append(
            f"{ind_str}html += (\n"
            f"{ind_str}    f\"<tr><td colspan='3'><b>Deposit/Recycle Fees</b></td>\"\n"
            f"{ind_str}    f\"<td>-</td><td>${{deposit:.2f}}</td></tr>\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html += f"<tr><td colspan='3'><b>Subtotal</b></td>...
    # -------------------------------------------------------------------
    elif "html += f\"<tr><td colspan='3'><b>Subtotal</b>" in stripped:
        out.append(
            f"{ind_str}html += (\n"
            f"{ind_str}    f\"<tr><td colspan='3'><b>Subtotal</b></td>\"\n"
            f"{ind_str}    f\"<td><b>${{total_gst:.2f}}</b></td>\"\n"
            f"{ind_str}    f\"<td><b>${{total:.2f}}</b></td></tr>\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html = second occurrence (driver checklist)
    # -------------------------------------------------------------------
    elif "html = \"<html><body><table border='1'" in stripped and 'width:' not in stripped:
        out.append(
            f"{ind_str}html = (\n"
            f"{ind_str}    \"<html><body>\"\n"
            f"{ind_str}    \"<table border='1' cellpadding='5'>\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html += "<td><input type='checkbox' style='width:20px; height:20px;'></td>"
    # -------------------------------------------------------------------
    elif "html += \"<td><input type='checkbox'" in stripped:
        out.append(
            f"{ind_str}html += (\n"
            f"{ind_str}    \"<td><input type='checkbox'\"\n"
            f"{ind_str}    \" style='width:20px; height:20px;'></td>\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: html += "<p><i>Driver: Check off each item as it is loaded into the vehicle.</i></p>"
    # -------------------------------------------------------------------
    elif 'html += "<p><i>Driver: Check off each item' in stripped:
        out.append(
            f'{ind_str}html += (\n'
            f'{ind_str}    "<p><i>Driver: Check off each item"\n'
            f'{ind_str}    " as it is loaded into the vehicle.</i></p>")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"{'☐':<2} {'Item':<40} ...
    # -------------------------------------------------------------------
    elif "text += f\"{" in stripped and "'☐'" in stripped and "'Item'" in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"{{' ☐':<2}} {{' Item':<40}}\"\n"
            f"{ind_str}    f\" {{' Qty':<6}} {{' Cost Each':<12}}\"\n"
            f"{ind_str}    f\" {{' Total':<10}}\\n\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"☐  {item_name:<37} {qty:<6} ${unit_cost:<11.2f} ${line_cost:<9.2f}\n"
    # -------------------------------------------------------------------
    elif 'text += f"☐  {item_name:<37}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"☐  {{item_name:<37}} {{qty:<6}}"\n'
            f'{ind_str}    f" ${{unit_cost:<11.2f}} ${{line_cost:<9.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "Driver Signature: ________________...
    # -------------------------------------------------------------------
    elif 'text += "Driver Signature: ________________' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "Driver Signature: ________________"\n'
            f'{ind_str}    "  Date: ________  Time: ________\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "\nNote: Prices locked from charter creation. Edits...
    # -------------------------------------------------------------------
    elif 'text += "\\nNote: Prices locked from charter creation.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "\\nNote: Prices locked from charter creation."\n'
            f'{ind_str}    " Edits to quantities/prices\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "are reflected in this cart but do NOT affect master beverage_products.\n"
    # -------------------------------------------------------------------
    elif 'text += "are reflected in this cart but do NOT affect master beverage_products.' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "are reflected in this cart but do NOT"\n'
            f'{ind_str}    " affect master beverage_products.\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SELECT item_name, quantity, unit_price_charged, line_amount_charged, deposit_per_uni
    # -------------------------------------------------------------------
    elif ('SELECT item_name, quantity, unit_price_charged, line_amount_charged, deposit_per_uni'
          in stripped):
        out.append(
            f'{ind_str}SELECT item_name, quantity,\n'
            f'{ind_str}unit_price_charged,\n'
            f'{ind_str}line_amount_charged, deposit_per_unit\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"{'Item':<45} {'Qty':<6} {'Price Each':<10} {'Total':<10}\n"
    # -------------------------------------------------------------------
    elif "text += f\"{" in stripped and "'Item'" in stripped and "'Qty'" in stripped and "'Price Each'" in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f"{ind_str}    f\"{{' Item':<45}} {{' Qty':<6}}\"\n"
            f"{ind_str}    f\" {{' Price Each':<10}} {{' Total':<10}}\\n\")\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += f"{item_name:<45} {qty:<6} ${unit_price:<9.2f} ${line_amount:<9.2f}\n"
    # -------------------------------------------------------------------
    elif 'text += f"{item_name:<45}' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    f"{{item_name:<45}} {{qty:<6}}"\n'
            f'{ind_str}    f" ${{unit_price:<9.2f}} ${{line_amount:<9.2f}}\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "   ✓ Verified at load time: ________  Initials: ____\n\n"
    # -------------------------------------------------------------------
    elif 'text += "   ✓ Verified at load time:' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "   ✓ Verified at load time: ________"\n'
            f'{ind_str}    "  Initials: ____\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "I confirm that all beverage items listed above have been loaded\n"
    # -------------------------------------------------------------------
    elif 'text += "I confirm that all beverage items listed above have been loaded' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "I confirm that all beverage items"\n'
            f'{ind_str}    " listed above have been loaded\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: text += "Date: ____________________  Time: ____________________\n\n"
    # -------------------------------------------------------------------
    elif 'text += "Date: ____________________  Time: ____________________' in stripped:
        out.append(
            f'{ind_str}text += (\n'
            f'{ind_str}    "Date: ____________________"\n'
            f'{ind_str}    "  Time: ____________________\\n\\n")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "Word export requires python-docx.\n\nInstall with: pip install python-docx\n\nFalling back..."
    # -------------------------------------------------------------------
    elif 'Word export requires python-docx' in stripped:
        out.append(
            f'{ind_str}"Word export requires python-docx.\\n\\n"\n'
            f'{ind_str}"Install with: pip install python-docx\\n\\n"\n'
            f'{ind_str}"Falling back to text export.")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "DELETE FROM charter_routes WHERE charter_id = %s", (self.charter_id,))
    # -------------------------------------------------------------------
    elif '"DELETE FROM charter_routes WHERE charter_id = %s"' in stripped:
        out.append(
            f'{ind_str}"DELETE FROM charter_routes"\n'
            f'{ind_str}" WHERE charter_id = %s",\n'
            f'{ind_str}(self.charter_id,))\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: (self.charter_id, row_idx + 1, pickup_loc, pickup_time, dropoff_loc, dropoff_tim
    # -------------------------------------------------------------------
    elif re.match(r'\s+\(self\.charter_id, row_idx \+ 1, pickup_loc, pickup_time, dropoff_loc',
                  stripped):
        out.append(
            f'{ind_str}(self.charter_id, row_idx + 1,\n'
            f'{ind_str} pickup_loc, pickup_time,\n'
            f'{ind_str} dropoff_loc, dropoff_time,\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"✅ Saved {self.route_table.rowCount()} routes for charter {self.charter_id}"
    # -------------------------------------------------------------------
    elif '✅ Saved' in stripped and 'routes for charter' in stripped:
        out.append(
            f'{ind_str}f"✅ Saved {{self.route_table.rowCount()}}"\n'
            f'{ind_str}f" routes for charter {{self.charter_id}}")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: "DELETE FROM charter_charges WHERE charter_id = %s", (self.charter_id,))
    # -------------------------------------------------------------------
    elif '"DELETE FROM charter_charges WHERE charter_id = %s"' in stripped:
        out.append(
            f'{ind_str}"DELETE FROM charter_charges"\n'
            f'{ind_str}" WHERE charter_id = %s",\n'
            f'{ind_str}(self.charter_id,))\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: reserve_number = self.customer_widget.reserve_input.text() or None
    # -------------------------------------------------------------------
    elif re.match(r'\s+reserve_number = self\.customer_widget\.reserve_input\.text\(\) or None',
                  stripped):
        out.append(
            f'{ind_str}reserve_number = (\n'
            f'{ind_str}    self.customer_widget.reserve_input.text()\n'
            f'{ind_str}    or None)\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: sequence, charge_type, category, last_updated, last_updated_by)
    # -------------------------------------------------------------------
    elif re.match(r'\s+sequence, charge_type, category, last_updated, last_updated_by\)',
                  stripped):
        out.append(
            f'{ind_str}sequence, charge_type, category,\n'
            f'{ind_str}last_updated, last_updated_by)\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: FROM charter_charges WHERE charter_id = %s AND charge_type = 'tax'
    # -------------------------------------------------------------------
    elif ("FROM charter_charges WHERE charter_id = %s AND charge_type = 'tax'"
          in stripped):
        out.append(
            f"{ind_str}FROM charter_charges\n"
            f"{ind_str}WHERE charter_id = %s\n"
            f"{ind_str}AND charge_type = 'tax'\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: FROM charter_charges WHERE charter_id = %s AND charge_type = 'gratuity'
    # -------------------------------------------------------------------
    elif ("FROM charter_charges WHERE charter_id = %s AND charge_type = 'gratuity'"
          in stripped):
        out.append(
            f"{ind_str}FROM charter_charges\n"
            f"{ind_str}WHERE charter_id = %s\n"
            f"{ind_str}AND charge_type = 'gratuity'\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: FROM charter_charges WHERE charter_id = %s AND charge_type = 'gratuity'))
    # -------------------------------------------------------------------
    elif ("FROM charter_charges WHERE charter_id = %s AND charge_type = 'gratuity'))"
          in stripped):
        out.append(
            f"{ind_str}FROM charter_charges\n"
            f"{ind_str}WHERE charter_id = %s\n"
            f"{ind_str}AND charge_type = 'gratuity'))\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: self.charter_id,  # driver_total_expense fallback gratuity subquery
    # -------------------------------------------------------------------
    elif ('self.charter_id,  # driver_total_expense fallback gratuity subquery'
          in stripped):
        out.append(
            f'{ind_str}self.charter_id,\n'
            f'{ind_str}# driver_total_expense fallback gratuity subquery\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"✅ Saved {self.charges_table.rowCount()} charges for charter {self.charter_id}"
    # -------------------------------------------------------------------
    elif '✅ Saved' in stripped and 'charges for charter' in stripped:
        out.append(
            f'{ind_str}f"✅ Saved {{self.charges_table.rowCount()}}"\n'
            f'{ind_str}f" charges for charter {{self.charter_id}}")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: row_idx, 2).text().replace('$', '').replace(',', ''))
    # -------------------------------------------------------------------
    elif ("row_idx, 2).text().replace('$', '').replace(',', ''))"
          in stripped):
        out.append(
            f"{ind_str}row_idx, 2).text().replace(\n"
            f"{ind_str}    '$', '').replace(',', ''))\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: prev_billed_text = self.dp_gratuity.text().replace('$', '').replace(',', '')
    # -------------------------------------------------------------------
    elif ("prev_billed_text = self.dp_gratuity.text().replace('$', '').replace(',', '')"
          in stripped):
        out.append(
            f"{ind_str}prev_billed_text = (\n"
            f"{ind_str}    self.dp_gratuity.text()\n"
            f"{ind_str}    .replace('$', '').replace(',', ''))\n"
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: COALESCE(cr.address, cr.pickup_location, cr.dropoff_location) AS address,
    # -------------------------------------------------------------------
    elif 'COALESCE(cr.address, cr.pickup_location, cr.dropoff_location) AS address,' in stripped:
        out.append(
            f'{ind_str}COALESCE(cr.address,\n'
            f'{ind_str}    cr.pickup_location,\n'
            f'{ind_str}    cr.dropoff_location) AS address,\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: dropoff_time_select = "dropoff_time" if has_dropoff_time else "workshift_end::ti
    # -------------------------------------------------------------------
    elif 'dropoff_time_select = "dropoff_time" if has_dropoff_time else' in stripped:
        out.append(
            f'{ind_str}dropoff_time_select = (\n'
            f'{ind_str}    "dropoff_time"\n'
            f'{ind_str}    if has_dropoff_time\n'
            f'{ind_str}    else "workshift_end::time")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: SELECT pickup_address, dropoff_address, pickup_time, {dropoff_time_select}
    # -------------------------------------------------------------------
    elif 'SELECT pickup_address, dropoff_address, pickup_time, {dropoff_time_select}' in stripped:
        out.append(
            f'{ind_str}SELECT pickup_address, dropoff_address,\n'
            f'{ind_str}pickup_time, {{dropoff_time_select}}\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: pickup_addr, dropoff_addr, pickup_time, dropoff_time = row
    # -------------------------------------------------------------------
    elif re.match(r'\s+pickup_addr, dropoff_addr, pickup_time, dropoff_time = row',
                  stripped):
        out.append(
            f'{ind_str}(pickup_addr, dropoff_addr,\n'
            f'{ind_str} pickup_time, dropoff_time) = row\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: dropoff_addr, str) and dropoff_addr.startswith("1899-12-30")
    # -------------------------------------------------------------------
    elif 'dropoff_addr, str) and dropoff_addr.startswith("1899-12-30"):' in stripped:
        out.append(
            f'{ind_str}dropoff_addr, str)\n'
            f'{ind_str}and dropoff_addr.startswith("1899-12-30")):\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: f"✅ Loaded pickup/dropoff from charter for {charter_id}"
    # -------------------------------------------------------------------
    elif '✅ Loaded pickup/dropoff from charter for' in stripped:
        out.append(
            f'{ind_str}f"✅ Loaded pickup/dropoff"\n'
            f'{ind_str}f" from charter for {{charter_id}}")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Pattern: time_str = f"{stop_time.hour:02d}:{stop_time.minute:02d}"
    # -------------------------------------------------------------------
    elif 'time_str = f"{stop_time.hour:02d}:{stop_time.minute:02d}"' in stripped:
        out.append(
            f'{ind_str}time_str = (\n'
            f'{ind_str}    f"{{stop_time.hour:02d}}:"\n'
            f'{ind_str}    f"{{stop_time.minute:02d}}")\n'
        )
        handled = True

    # -------------------------------------------------------------------
    # Liability clause long string continuations - wrapped at 21 spaces
    # These are lines like:
    #   `            text += ("CONTENT"` (22 + content + 1)
    #   `                     "CONTENT"` (21 + 1 + content + 1)
    # Fix: change indentation of continuation from 21 to 16 spaces,
    # and if still > 79, split the string content
    # -------------------------------------------------------------------
    elif (re.match(r'                     "', stripped)
          and len(stripped) > 79
          and not stripped.startswith('                      ')):
        # This is a 21-space continuation. Change to shorter pieces.
        # Content is everything between the quotes
        quote_content = stripped[22:]  # after `                     "`
        if quote_content.endswith('"'):
            quote_content = quote_content[:-1]
        elif quote_content.endswith('")'):
            quote_content = quote_content[:-2]
            closing = ')'
        else:
            closing = ''
        # If content > 57 chars, split at word boundary
        sp16 = ' ' * 16
        if len(quote_content) <= 57:
            out.append(f'{sp16}"{quote_content}"\n')
        else:
            # find split at word boundary ≤ 57
            split_at = quote_content.rfind(' ', 0, 57)
            if split_at < 0:
                split_at = 57
            part1 = quote_content[:split_at + 1]
            part2 = quote_content[split_at + 1:]
            out.append(f'{sp16}"{part1}"\n')
            out.append(f'{sp16}"{part2}"\n')
        handled = True

    # -------------------------------------------------------------------
    # Catch-all: skip lines we haven't handled yet
    # -------------------------------------------------------------------

    if not handled:
        out.append(line)

    i += 1
    if handled:
        changed += 1

# Write output
with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(out)

print(f"Changed {changed} lines/blocks")
print("Done")
