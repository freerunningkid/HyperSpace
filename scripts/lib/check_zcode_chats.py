import sqlite3, json
db = sqlite3.connect('C:\\Users\\KID\\.zcode\\cli\\db\\db.sqlite')
db.text_factory = str

# Part table schema
cols = db.execute('PRAGMA table_info("part")').fetchall()
print('part columns:', [(c[1], c[2]) for c in cols])

# Latest 5 parts
rows = db.execute('SELECT * FROM part ORDER BY id DESC LIMIT 5').fetchall()
for r in rows:
    d = dict(zip([c[1] for c in cols], r))
    print()
    for k, v in d.items():
        if v is not None:
            s = str(v)
            if len(s) > 200:
                s = s[:200] + '...'
            print(f'  {k}: {s}')

# Also check session table for the current session
print('\n=== Session ===')
cols = [c[1] for c in db.execute('PRAGMA table_info("session")').fetchall()]
print('session columns:', cols)
db.close()
