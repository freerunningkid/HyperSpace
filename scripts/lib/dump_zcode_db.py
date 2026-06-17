import sqlite3, json

db = sqlite3.connect(r'C:\Users\KID\.zcode\cli\db\db.sqlite')
cursor = db.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [t[0] for t in cursor.fetchall()])

# Dump all tables content
for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    table = t[0]
    print(f"\n=== {table} ===")
    try:
        cursor.execute(f'SELECT * FROM "{table}" LIMIT 20')
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        for r in rows:
            d = dict(zip(cols, r))
            for k, v in d.items():
                if isinstance(v, bytes):
                    try:
                        v = v.decode('utf-8')
                    except:
                        v = f'[bytes: {len(v)}]'
                if v is not None:
                    print(f"  {k}: {str(v)[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

db.close()
