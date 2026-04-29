import re

file_path = r'l:\limo\desktop_app\charter_form_widget.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if line contains the problematic pattern
    if ('StandardButton.Yes' in line and 'StandardButton.No' in line 
        and '|' in line and len(line.rstrip()) > 79):
        
        # Get the leading whitespace
        indent_match = re.match(r'^(\s*)', line)
        base_indent = indent_match.group(1) if indent_match else ''
        
        # Check if this line is inside a function call (multiple levels of indent)
        param_indent = base_indent + ' ' * 20  # Estimate for parameter indent
        
        # Find where the StandardButton pattern starts
        match = re.search(r'(\s*)([A-Za-z]*MessageBox\.StandardButton|[A-Za-z]*DialogButtonBox\.StandardButton)', line)
        if match:
            button_indent = match.group(1)
            
            # Replace this line with wrapped version
            before_buttons = line[:match.start(2)]
            after_pattern = re.sub(
                r'([A-Za-z]*MessageBox|[A-Za-z]*DialogButtonBox)\.StandardButton\.(Yes|Ok)\s*\|\s*([A-Za-z]*MessageBox|[A-Za-z]*DialogButtonBox)\.StandardButton\.(No|Cancel)',
                r'(\1.StandardButton.\2\n' + ' ' * (len(button_indent) + 13) + r'| \3.StandardButton.\4)',
                line[match.start(2):]
            )
            
            # Simpler approach: just split at the pipe
            parts = line.split('|')
            if len(parts) == 2:
                output_lines.append(parts[0].rstrip() + '|\n')
                indent_for_continuation = ' ' * (len(button_indent) + 13)
                output_lines.append(indent_for_continuation + parts[1].lstrip())
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)
    else:
        output_lines.append(line)
    
    i += 1

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print("✓ Fixed StandardButton indentation")
