"""
Add setDisplayFormat("MM/dd/yyyy") to all QDateEdit widgets in desktop_app
"""
import os
import re

desktop_app_path = r"L:\limo\desktop_app"

# Pattern to find QDateEdit creation without setDisplayFormat
qdate_pattern = re.compile(r'(\s+)(\w+)\s*=\s*QDateEdit\(\)\s*\n')

files_updated = []

for filename in os.listdir(desktop_app_path):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(desktop_app_path, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Find all QDateEdit creations
        matches = list(qdate_pattern.finditer(content))
        
        if not matches:
            continue
        
        # Check each match to see if it already has setDisplayFormat on next line
        for match in reversed(matches):  # Reverse to maintain positions
            indent = match.group(1)
            var_name = match.group(2)
            pos = match.end()
            
            # Look ahead to see if setDisplayFormat is already there
            next_lines = content[pos:pos+200]
            if f'{var_name}.setDisplayFormat' in next_lines:
                continue  # Already has format
            
            # Insert setDisplayFormat
            insert_text = f'{indent}{var_name}.setDisplayFormat("MM/dd/yyyy")\n'
            content = content[:pos] + insert_text + content[pos:]
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            files_updated.append(filename)
            print(f"✅ Updated: {filename}")
    
    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")

print(f"\n✅ Updated {len(files_updated)} files")
for f in files_updated:
    print(f"  - {f}")
