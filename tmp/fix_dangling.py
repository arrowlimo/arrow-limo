"""Fix dangling string lines that are leftovers from the bulk fix script."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and remove dangling string lines that appear after a properly-closed text += () block
# Pattern: a line that is JUST a string literal (with leading whitespace) followed by )
# but NOT part of any open expression above it
# Specifically: lines like '                     "required to confirm booking\n")\n'
# that come right after a line ending with )\n

# Strategy: find lines that:
# 1. Strip to a string literal ending with )\n or ")\n
# 2. The line ABOVE also ends with )\n (meaning previous block was closed)
# 3. This line is indented MORE than a normal statement would be

dangling_indices = []
for i in range(1, len(lines)):
    prev = lines[i-1].rstrip('\n').rstrip()
    curr = lines[i].rstrip('\n').rstrip()
    
    # Dangling: current is a string + ) with extra indent
    # Previous line also ended with )
    if (prev.endswith(')')
            and (curr.endswith('")')  or curr.endswith("')"
            ))
            and not curr.lstrip().startswith('text')
            and not curr.lstrip().startswith('if')
            and not curr.lstrip().startswith('return')
            and not curr.lstrip().startswith('else')
            and curr.lstrip().startswith('"')):
        # Double check: the strip starts with a quote
        print(f"DANGLING at line {i+1}: {curr[:80]}")
        dangling_indices.append(i)

print(f"\nFound {len(dangling_indices)} dangling lines")
print("Removing them...")

# Remove in reverse order to preserve indices
for idx in reversed(dangling_indices):
    del lines[idx]

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Check
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 5), min(len(src_lines), e.lineno + 5)):
        marker = " >>> " if j == e.lineno - 1 else "     "
        print(f"{marker}{j+1}: {src_lines[j][:100]}")
