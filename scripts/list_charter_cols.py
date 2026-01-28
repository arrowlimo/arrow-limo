import json
d = json.load(open('reports/schema_comparison_2025-12-26.json'))
c = d['tables']['charters']['pg_detail']['columns']
print("Charter table columns:")
for i, x in enumerate(c, 1):
    print(f"{i:3}. {x['name']:35} {x['type']}")
