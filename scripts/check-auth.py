import json

with open("/root/.local/share/opencode/auth.json") as f:
    d = json.load(f)

for name, info in d.items():
    if isinstance(info, dict) and "key" in info:
        k = info["key"]
        print(f"Provider: {name}")
        print(f"  Key length: {len(k)}")
        print(f"  Key start:  {k[:20]}")
        print(f"  Key end:    {k[-10:]}")
        print(f"  Has CR/LF:  {chr(10) in k or chr(13) in k}")
        print(f"  All ASCII:  {all(ord(c) < 128 for c in k)}")
        print()
