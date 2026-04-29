"""
Fix all text += ( blocks that are missing their closing ) by tracking paren depth.
Also fix other known patterns.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixes = 0

# Scan for text += ( blocks missing closing )
# The pattern: a line with "text += (" that opens a paren, followed by string
# continuation lines, where the last string line doesn't end with ")"
# After the block comes a blank line or another statement.

# Simpler approach: find all lines ending with a bare string (not ending with )
# that follow a text += ( opener and are followed by a blank or unrelated line.

i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.rstrip('\n').rstrip()
    
    # Look for text += ( that opens a multiline string
    if ('text += ("' in line or "text += ('" in line):
        # Find the end of this text += block
        # It should be a line that ends with ") or ")  or similar
        j = i
        while j < len(lines):
            jline = lines[j].rstrip('\n').rstrip()
            if jline.endswith(')'):
                break  # properly closed
            # Check if next non-blank line starts with something unexpected
            j += 1
            if j >= len(lines):
                break
            # If this line ends with a string but NOT )
            # and next line is blank OR starts a new statement
            if jline.endswith('"') or jline.endswith("'"):
                nextj = j
                while nextj < len(lines) and not lines[nextj].strip():
                    nextj += 1
                if nextj < len(lines):
                    next_stripped = lines[nextj].strip()
                    if (next_stripped.startswith('text +=')
                            or next_stripped.startswith('if ')
                            or next_stripped.startswith('text =')
                            or next_stripped.startswith('# =')
                            or next_stripped.startswith('# ')
                            or next_stripped == ''
                            or next_stripped.startswith('else:')
                            or next_stripped.startswith('return')):
                        # This block is not closed - add ) to line j-1
                        target_idx = j - 1
                        old = lines[target_idx].rstrip('\n').rstrip()
                        if not old.endswith(')'):
                            lines[target_idx] = old + ')\n'
                            print(f"Added ) to line {target_idx+1}: {lines[target_idx].rstrip()[:80]}")
                            fixes += 1
                        break
    i += 1

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"\nTotal fixes: {fixes}")

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
