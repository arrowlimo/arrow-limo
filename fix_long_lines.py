#!/usr/bin/env python3
"""Wrap long text += strings to comply with PEP8 79-char limit"""
import re

file_path = r'l:\limo\desktop_app\charter_form_widget.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
new_lines = []

for line in lines:
    stripped = line.rstrip()
    
    # Check if line is a text += statement with long string
    if 'text +=' in line and len(stripped) > 79:
        # Extract indent
        indent_match = re.match(r'^(\s*)', line)
        indent = indent_match.group(1) if indent_match else ''
        
        # Look for text += "..." pattern
        match = re.match(r'^(\s*)text \+= "(.*)"$', stripped)
        if match:
            string_content = match.group(2)
            
            # Split at specific break points
            # Split on word boundaries to stay under ~65 chars per line
            if len(string_content) > 79:
                # Remove ending \n\n if present
                has_newline = string_content.endswith('\\n\\n')
                if has_newline:
                    string_content = string_content[:-4]
                
                # Split on spaces
                words = string_content.split(' ')
                chunks = []
                current = []
                current_len = 0
                
                for word in words:
                    word_len = len(word) + 1  # +1 for space
                    # If adding this word would exceed 65 chars, start new chunk
                    if current_len + word_len > 65 and current:
                        chunks.append(' '.join(current))
                        current = [word]
                        current_len = word_len
                    else:
                        current.append(word)
                        current_len += word_len
                
                # Add remaining
                if current:
                    chunks.append(' '.join(current))
                
                # Build wrapped version
                if len(chunks) > 1:
                    new_lines.append(f'{indent}text += ("{chunks[0]} "')
                    for chunk in chunks[1:-1]:
                        new_lines.append(f'{indent}         "{chunk} "')
                    final = chunks[-1]
                    if has_newline:
                        new_lines.append(f'{indent}         "{final}\\n\\n")')
                    else:
                        new_lines.append(f'{indent}         "{final}")')
                else:
                    # Single chunk, too long for one line - just add
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

# Write back
new_content = '\n'.join(new_lines)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✓ Wrapped long text strings")
