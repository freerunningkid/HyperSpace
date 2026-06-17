import re

with open(r'D:\ZCode\resources\glm\zcode.cjs', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find how deepseek gets API key
patterns = ['deepseek.*apiKey', 'apiKey.*deepseek', 'builtin:deepseek']
for p in patterns:
    idx = content.find(p)
    if idx >= 0:
        print(f'--- Found "{p}" at {idx} ---')
        print(content[max(0,idx-100):idx+300])
        print()

# Find generic provider api key storage
idx = content.find('"apiKey"')
if idx >= 0:
    ctx = content[max(0,idx-200):idx+400]
    print(f'--- apiKey context at {idx} ---')
    print(ctx[:500])
