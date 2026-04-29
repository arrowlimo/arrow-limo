"""Find unclosed triple-quote near line 4994 and all other locations."""
with open('desktop_app/charter_form_widget.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all lines with """ in reverse from line 4994
print("Lines with triple-quotes near line 4994:")
for i in range(4993, 4460, -1):
    if '"""' in lines[i]:
        print(f'{i+1}: {repr(lines[i][:80])}')
