import json, time

path = r'C:\Users\KID\AppData\Roaming\reasonix\projects\D--Reasonix\sessions\desktop-202606021252-1.jsonl'

# Cutoff: 19:00 Beijing time = 11:00 UTC = 1781694000000 ms
# Actually let's use the file timestamp approach - filter by message position
# since we know roughly where 19:00 starts

# Let's just read all lines and look for timestamp-like fields
count = 0
total_in = 0
total_out = 0
total_cost = 0.0

with open(path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except:
            continue
        
        # Look for token or cost info in the message
        content = obj.get('content', '')
        if isinstance(content, str):
            # Look for cost/token patterns from the status output
            if '本次费用' in content:
                import re
                # Extract: 本次 tokens: N,N  or 本次费用 ¥X
                m = re.search(r'本次 tokens\s+([\d,]+)', content)
                if m:
                    total_in += int(m.group(1).replace(',', ''))
                m = re.search(r'本次费用\s+¥?([\d.]+)', content)
                if m:
                    total_cost += float(m.group(1))
                count += 1

print(f'请求次数: {count}')
print(f'总计 tokens: {total_in:,}')
print(f'总计费用: ¥{total_cost:.4f}')
