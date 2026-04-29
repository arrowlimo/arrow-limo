with open('desktop_app/charter_form_widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixes = 0

# Find all lines that end a multiline function call but are missing closing )
# Strategy: scan for patterns where the fix script split lines and dropped )

# Fix: QMessageBox.information lines 6186-6190 - missing closing )
for i in range(6180, 6195):
    if ('f"Charter ID: {self.charter_id}"' in lines[i]
            and not lines[i].rstrip().endswith(')')):
        prev = lines[i-1].rstrip()
        if 'f"Reserve #:' in prev:
            lines[i] = lines[i].rstrip('\n').rstrip() + ')\n'
            print(f"Fixed line {i+1}: {lines[i].rstrip()[:80]}")
            fixes += 1
            break

# Scan broadly for any multiline f-string continuation blocks that have
# a blank line after without closing paren
# Look for pattern: f"..." followed by blank line, where there's an unclosed (
# Actually let's just keep fixing one by one with ast

with open('desktop_app/charter_form_widget.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f'Total fixes: {fixes}')
