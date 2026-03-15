"""
Fix all split f-strings in main.py by joining them into single lines
"""
import re

file_path = r"l:\limo\DEPLOYMENT_PACKAGE\app\desktop_app\main.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix split f-strings where { is at end of line
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if line has f" and ends with { and optional whitespace
    if re.search(r'f"[^"]*\{\s*$', line):
        # This is a split f-string, need to join with next line(s)
        combined = line.rstrip()
        i += 1
        
        # Keep joining lines until we find the closing quote
        quote_count = combined.count('"') - combined.count('\\"')
        while i < len(lines) and quote_count % 2 != 0:
            next_line = lines[i].lstrip()
            combined += next_line.rstrip()
            quote_count = combined.count('"') - combined.count('\\"')
            i += 1
        
        # Clean up excessive whitespace in the combined string
        # but preserve the correct number of closing parens
        combined = re.sub(r'\s+', ' ', combined)
        combined += '\n'
        fixed_lines.append(combined)
    else:
        fixed_lines.append(line)
        i += 1

# Write fixed content
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print(f"Fixed split f-strings in {file_path}")
