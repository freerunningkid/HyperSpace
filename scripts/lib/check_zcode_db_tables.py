import sqlite3, json

db = sqlite3.connect(r'C:\Users\KID\.zcode\cli\db\db.sqlite')
db.row_factory = sqlite3.Row

tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print('Tables:', tables)

# Check message/part/session tables
for t in ['message', 'part', 'session']:
    if t in tables:
        cols = [d[1] for d in db.execute(f'PRAGMA table_info({t})').fetchall()]
        print(f'\n=== {t} ===')
        print(f'  Columns: {cols}')
        rows = db.execute(f'SELECT * FROM {t} ORDER BY rowid DESC LIMIT 2').fetchall()
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if v is not None:
                    print(f'  {k}: {str(v)[:150]}')
            print()

db.close()
