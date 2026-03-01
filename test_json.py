import json, os
from pathlib import Path

files = sorted(Path(".").glob("game_case_v2_*.json"), key=os.path.getmtime, reverse=True)
print(f"Latest file: {files[0]}")
d = json.load(open(files[0], 'r', encoding='utf-8'))
for s in d['case']['suspects']:
    print(s['name'], s.get('suspicious_behavior'))
