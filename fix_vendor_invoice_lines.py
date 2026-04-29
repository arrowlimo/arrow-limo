#!/usr/bin/env python3
"""Wrap setStyleSheet and similar long method calls"""
import re

file_path = r'l:\limo\desktop_app\vendor_invoice_manager.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

output_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    stripped = line.rstrip()
    
    # Check if this is a setStyleSheet line that's too long
    if 'setStyleSheet(' in line and len(stripped) > 79:
        # Try to wrap it
        match = re.match(r'^(\s*)(.+?setStyleSheet\()(".*")(\).*)$', stripped)
        if match:
            indent = match.group(1)
            prefix = match.group(2)
            string_part = match.group(3)
            suffix = match.group(4)
            
            # Try to break string into multiple parts
            # Extract the actual string content
            string_content = string_part[1:-1]  # Remove quotes
            
            # If string has semicolons or spans, split there
            if ';' in string_content and len(string_content) > 60:
                parts = string_content.split(';')
                new_parts = []
                for part in parts:
                    new_parts.append(part.strip())
                
                # Build wrapped version
                output_lines.append(f'{indent}{prefix}')
                for idx, part in enumerate(new_parts[:-1]):
                    output_lines.append(f'{indent}    "{part};"\n')
                output_lines.append(f'{indent}    "{new_parts[-1]}"{suffix}\n')
            else:
                # Can't easily split, just add as-is
                output_lines.append(line)
        else:
            output_lines.append(line)
    else:
        output_lines.append(line)
    
    i += 1

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print("✓ Wrapped setStyleSheet calls")
