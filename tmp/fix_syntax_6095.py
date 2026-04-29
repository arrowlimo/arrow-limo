with open('desktop_app/charter_form_widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the broken cur.execute block near line 6093-6096
# Look for the pattern: cur.execute( followed by two SQL strings without closing )
for i in range(6085, 6100):
    if '"SELECT MAX(CAST(reserve_number AS INTEGER))"' in lines[i]:
        # Check if next line has the FROM clause without closing )
        next_line = lines[i+1]
        if 'FROM charters WHERE' in next_line and not next_line.rstrip().endswith(')'):
            lines[i+1] = next_line.rstrip('\n').rstrip() + ')\n'
            print(f"Fixed line {i+2}: {lines[i+1].rstrip()[:80]}")
        break

with open('desktop_app/charter_form_widget.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done')
