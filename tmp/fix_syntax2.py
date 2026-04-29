with open('desktop_app/charter_form_widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Multiple targeted fixes for syntax errors introduced by the bulk script

# Fix 1: lines 6161-6164 - broken if/hasattr condition
# Current:
#   if has_charter_data and hasattr(
#           self,
#           'current_inspection_form_path')
#           and self.current_inspection_form_path:
# Fix: wrap in parens so multiline works
if ("                        'current_inspection_form_path')" in lines[6162]
        and "                        and self.current_inspection_form_path:" in lines[6163]):
    lines[6160] = "                if (has_charter_data and hasattr(\n"
    lines[6161] = "                        self,\n"
    lines[6162] = "                        'current_inspection_form_path')\n"
    lines[6163] = "                        and self.current_inspection_form_path):\n"
    print("Fixed 6161-6164")
else:
    print(f"MISMATCH 6161: {repr(lines[6160].rstrip()[:80])}")
    print(f"MISMATCH 6162: {repr(lines[6161].rstrip()[:80])}")
    print(f"MISMATCH 6163: {repr(lines[6162].rstrip()[:80])}")
    print(f"MISMATCH 6164: {repr(lines[6163].rstrip()[:80])}")

with open('desktop_app/charter_form_widget.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
